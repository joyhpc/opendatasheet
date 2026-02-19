"""
OpenDatasheet Pipeline v0.1 — Phase 1 技术验证
L0: PyMuPDF 页面分类 + 文本提取
L1: Gemini 3 Pro 结构化参数提取
L2: Pydantic 物理规则校验

Sirius 🌟 | 2026-02-19
"""
import fitz
import json
import re
import os
import sys
import time
import hashlib
import fcntl
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from google import genai

# ============================================
# Config
# ============================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDhJ4wpmDGI139p-bC4dmB_A2MIFAlT1R4")
GEMINI_MODEL = "gemini-3-flash-preview"  # Gemini 3 Flash — 速度+成本优势
DATA_DIR = Path(__file__).parent / "data" / "raw" / "datasheet_PDF"
OUTPUT_DIR = Path(__file__).parent / "data" / "extracted"

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ============================================
# L0: PyMuPDF 页面分类
# ============================================

# 关键页面检测正则
ELECTRICAL_PATTERNS = [
    re.compile(r'(?i)electrical\s+characteristics?'),
    re.compile(r'(?i)absolute\s+maximum\s+ratings?'),
    re.compile(r'(?i)recommended\s+operating\s+conditions?'),
    re.compile(r'(?i)dc\s+characteristics?'),
    re.compile(r'(?i)ac\s+characteristics?'),
    re.compile(r'(?i)thermal\s+(characteristics?|information)'),
]

PIN_PATTERNS = [
    re.compile(r'(?i)pin\s+(description|configuration|function|assignment|definition)'),
    re.compile(r'(?i)pin\s+name'),
    re.compile(r'(?i)terminal\s+function'),
]

ORDERING_PATTERNS = [
    re.compile(r'(?i)ordering\s+information'),
    re.compile(r'(?i)package\s+information'),
    re.compile(r'(?i)marking\s+information'),
]


@dataclass
class PageInfo:
    """单页分析结果"""
    page_num: int  # 0-indexed
    text_length: int
    category: str  # electrical / pin / ordering / cover / other
    matched_patterns: list = field(default_factory=list)
    text_preview: str = ""


def classify_pages(pdf_path: str) -> list[PageInfo]:
    """L0: 用 PyMuPDF 提取文本并分类每一页"""
    doc = fitz.open(pdf_path)
    pages = []

    for i in range(len(doc)):
        text = doc[i].get_text()
        text_len = len(text)

        # 分类
        category = "other"
        matched = []

        # 封面检测 (第一页且包含厂商名)
        if i == 0:
            category = "cover"

        # 电气特性
        for pat in ELECTRICAL_PATTERNS:
            if pat.search(text):
                category = "electrical"
                matched.append(pat.pattern)

        # 引脚定义
        for pat in PIN_PATTERNS:
            if pat.search(text):
                if category != "electrical":  # 电气特性优先
                    category = "pin"
                matched.append(pat.pattern)

        # 订购信息
        for pat in ORDERING_PATTERNS:
            if pat.search(text):
                if category not in ("electrical", "pin"):
                    category = "ordering"
                matched.append(pat.pattern)

        # 纯图片页 (文本极少)
        if text_len < 100:
            category = "image_only"

        pages.append(PageInfo(
            page_num=i,
            text_length=text_len,
            category=category,
            matched_patterns=matched,
            text_preview=text[:200].replace('\n', ' ')
        ))

    doc.close()
    return pages


def extract_target_pages_text(pdf_path: str, pages: list[PageInfo]) -> str:
    """提取目标页面的完整文本 (电气特性 + 引脚)，实现跨页虚拟拼接"""
    doc = fitz.open(pdf_path)
    target_categories = {"electrical", "pin", "cover"}
    
    sections = []
    for p in pages:
        if p.category in target_categories:
            text = doc[p.page_num].get_text()
            sections.append(f"--- Page {p.page_num + 1} ({p.category}) ---\n{text}")

    doc.close()
    return "\n\n".join(sections)


# ============================================
# L1: Gemini 结构化提取
# ============================================

EXTRACTION_PROMPT = """You are an expert electronic component datasheet parser. Extract structured parameters from the following datasheet text.

RULES:
1. Extract ALL electrical parameters with min/typ/max values and units
2. Extract pin definitions if present
3. Map parameter names to canonical names (e.g., "Quiescent Current" → "Iq", "Input Voltage Range" → "Vin")
4. Include test conditions for each parameter
5. If a value is not specified, use null
6. Output ONLY valid JSON, no markdown, no explanation

OUTPUT JSON SCHEMA:
{
  "component": {
    "mpn": "string (part number)",
    "manufacturer": "string",
    "category": "string (LDO/Buck/OpAmp/Switch/Logic/ADC/DAC/Interface/Other)",
    "description": "string (one line)"
  },
  "absolute_maximum_ratings": [
    {
      "parameter": "string (canonical name)",
      "raw_name": "string (original name from datasheet)",
      "symbol": "string",
      "min": null or number,
      "typ": null or number,
      "max": null or number,
      "unit": "string",
      "conditions": "string or null"
    }
  ],
  "electrical_characteristics": [
    {
      "parameter": "string (canonical name)",
      "raw_name": "string (original name from datasheet)",
      "symbol": "string",
      "min": null or number,
      "typ": null or number,
      "max": null or number,
      "unit": "string",
      "conditions": "string or null"
    }
  ],
  "pin_definitions": [
    {
      "pin_number": "string or number",
      "pin_name": "string",
      "type": "string (Power/Input/Output/IO/NC/GND)",
      "description": "string"
    }
  ]
}

DATASHEET TEXT:
"""


def extract_with_gemini(text: str, pdf_name: str, max_retries: int = 2) -> dict:
    """L1: 用 Gemini 提取结构化参数，带重试"""
    prompt = EXTRACTION_PROMPT + text[:30000]

    for attempt in range(max_retries + 1):
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={
                    "temperature": 0.1,
                    "http_options": {"timeout": 120000},  # 120s timeout
                },
            )
            raw = response.text
            # 清理可能的 markdown 包裹
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            result = json.loads(raw.strip())
            # Gemini 有时返回 list 而不是 dict，取第一个元素
            if isinstance(result, list):
                result = result[0] if result else {"error": "Empty list returned"}
            if not isinstance(result, dict):
                return {"error": f"Unexpected type: {type(result).__name__}"}
            return result
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                time.sleep(2)
                continue
            return {"error": f"JSON parse failed after {max_retries+1} attempts: {str(e)}", "raw": raw[:500] if 'raw' in dir() else ""}
        except Exception as e:
            if attempt < max_retries and ("503" in str(e) or "429" in str(e)):
                time.sleep(5)
                continue
            return {"error": str(e)}


# ============================================
# L2: 物理规则校验
# ============================================

@dataclass
class ValidationResult:
    param: str
    rule: str
    passed: bool
    message: str


def validate_extraction(data: dict) -> list[ValidationResult]:
    """L2: 基础物理规则校验"""
    results = []

    for section in ["absolute_maximum_ratings", "electrical_characteristics"]:
        params = data.get(section, [])
        for p in params:
            name = p.get("parameter", "")
            min_v = p.get("min")
            typ_v = p.get("typ")
            max_v = p.get("max")

            # Rule 1: min <= typ <= max (单调性)
            vals = [v for v in [min_v, typ_v, max_v] if v is not None]
            if len(vals) >= 2:
                if vals != sorted(vals):
                    results.append(ValidationResult(
                        param=name,
                        rule="monotonicity",
                        passed=False,
                        message=f"min/typ/max not monotonic: {min_v}/{typ_v}/{max_v}"
                    ))
                else:
                    results.append(ValidationResult(
                        param=name,
                        rule="monotonicity",
                        passed=True,
                        message="OK"
                    ))

            # Rule 2: 单位合理性
            unit = p.get("unit", "")
            if unit and not re.match(r'^[µμunmpkMGT]?[AVWΩHzFsS°C%dB/]+$', unit):
                results.append(ValidationResult(
                    param=name,
                    rule="unit_valid",
                    passed=False,
                    message=f"Suspicious unit: {unit}"
                ))

    return results


# ============================================
# Main Pipeline
# ============================================

def process_single_pdf(pdf_path: str, verbose: bool = True) -> dict:
    """处理单个 PDF 的完整管线"""
    pdf_name = os.path.basename(pdf_path)
    if verbose:
        print(f"\n{'='*60}")
        print(f"Processing: {pdf_name}")
        print(f"{'='*60}")

    # L0: 页面分类
    t0 = time.time()
    pages = classify_pages(pdf_path)
    l0_time = time.time() - t0

    electrical_pages = [p for p in pages if p.category == "electrical"]
    pin_pages = [p for p in pages if p.category == "pin"]

    if verbose:
        print(f"\nL0 Page Classification ({l0_time:.3f}s):")
        print(f"  Total pages: {len(pages)}")
        print(f"  Electrical: {len(electrical_pages)} pages")
        print(f"  Pin defs:   {len(pin_pages)} pages")
        for p in pages:
            marker = "★" if p.category in ("electrical", "pin") else " "
            print(f"  {marker} P{p.page_num+1:2d} [{p.category:12s}] {p.text_length:5d} chars")

    # 提取目标页面文本
    target_text = extract_target_pages_text(pdf_path, pages)
    if verbose:
        print(f"\n  Target text length: {len(target_text)} chars")

    # L1: Gemini 提取
    t1 = time.time()
    extraction = extract_with_gemini(target_text, pdf_name)
    l1_time = time.time() - t1

    if verbose:
        if "error" in extraction:
            print(f"\nL1 Extraction FAILED ({l1_time:.1f}s): {extraction['error']}")
        else:
            comp = extraction.get("component", {})
            amr = extraction.get("absolute_maximum_ratings", [])
            ec = extraction.get("electrical_characteristics", [])
            pins = extraction.get("pin_definitions", [])
            print(f"\nL1 Gemini Extraction ({l1_time:.1f}s):")
            print(f"  Component: {comp.get('mpn', '?')} ({comp.get('manufacturer', '?')})")
            print(f"  Category:  {comp.get('category', '?')}")
            print(f"  Abs Max Ratings:  {len(amr)} params")
            print(f"  Elec Chars:       {len(ec)} params")
            print(f"  Pin Definitions:  {len(pins)} pins")

    # L2: 校验
    validations = []
    if "error" not in extraction:
        validations = validate_extraction(extraction)
        failures = [v for v in validations if not v.passed]
        if verbose:
            print(f"\nL2 Validation:")
            print(f"  Total checks: {len(validations)}")
            print(f"  Passed: {len(validations) - len(failures)}")
            print(f"  Failed: {len(failures)}")
            for f in failures:
                print(f"  ❌ {f.param}: {f.message}")

    # 组装结果
    result = {
        "pdf_name": pdf_name,
        "model": GEMINI_MODEL,
        "checksum": hashlib.md5(open(pdf_path, 'rb').read()).hexdigest(),
        "total_pages": len(pages),
        "page_classification": [asdict(p) for p in pages],
        "extraction": extraction,
        "validation": [asdict(v) for v in validations],
        "timing": {
            "l0_classify_s": round(l0_time, 3),
            "l1_extract_s": round(l1_time, 3),
        }
    }

    return result


def run_batch(limit: int = 5):
    """批量处理"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 进程锁：防止多实例同时运行
    lock_path = OUTPUT_DIR / ".pipeline.lock"
    lock_fd = open(lock_path, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("ERROR: Another pipeline instance is already running!")
        print(f"Lock file: {lock_path}")
        print("If stale, delete the lock file and retry.")
        sys.exit(1)

    lock_fd.write(f"pid={os.getpid()} started={time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
    lock_fd.flush()

    pdf_files = sorted([f for f in DATA_DIR.iterdir() if f.suffix.lower() == '.pdf'])
    if limit:
        pdf_files = pdf_files[:limit]

    print(f"OpenDatasheet Pipeline v0.1")
    print(f"Model: {GEMINI_MODEL}")
    print(f"PDFs to process: {len(pdf_files)}")

    all_results = []
    total_params = 0
    total_failures = 0

    for pdf_path in pdf_files:
        # 断点续跑：跳过已完成的文件
        out_name = pdf_path.stem + ".json"
        out_path = OUTPUT_DIR / out_name
        if out_path.exists() and out_path.stat().st_size > 100:
            print(f"\n⏭ Skipping (already done): {pdf_path.name}")
            # 加载已有结果统计
            with open(out_path, 'r') as f:
                result = json.load(f)
            all_results.append(result)
            ext = result.get("extraction", {})
            if isinstance(ext, dict) and "error" not in ext:
                total_params += len(ext.get("absolute_maximum_ratings", []))
                total_params += len(ext.get("electrical_characteristics", []))
            total_failures += len([v for v in result.get("validation", []) if not v.get("passed", True)])
            continue

        result = process_single_pdf(str(pdf_path))
        all_results.append(result)

        # 统计
        ext = result.get("extraction", {})
        if "error" not in ext:
            total_params += len(ext.get("absolute_maximum_ratings", []))
            total_params += len(ext.get("electrical_characteristics", []))
        total_failures += len([v for v in result.get("validation", []) if not v["passed"]])

        # 保存单个结果
        out_name = pdf_path.stem + ".json"
        with open(OUTPUT_DIR / out_name, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # Rate limit (Gemini free tier - 15 RPM)
        time.sleep(5)

    # 汇总
    print(f"\n{'='*60}")
    print(f"BATCH SUMMARY")
    print(f"{'='*60}")
    print(f"PDFs processed: {len(all_results)}")
    print(f"Total parameters extracted: {total_params}")
    print(f"Validation failures: {total_failures}")

    # 保存汇总
    summary_path = OUTPUT_DIR / "_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump({
            "total_pdfs": len(all_results),
            "total_params": total_params,
            "total_validation_failures": total_failures,
            "results": [{
                "pdf": r["pdf_name"],
                "mpn": r.get("extraction", {}).get("component", {}).get("mpn", "?"),
                "category": r.get("extraction", {}).get("component", {}).get("category", "?"),
                "params": len(r.get("extraction", {}).get("electrical_characteristics", [])) +
                          len(r.get("extraction", {}).get("absolute_maximum_ratings", [])),
                "pins": len(r.get("extraction", {}).get("pin_definitions", [])),
                "failures": len([v for v in r.get("validation", []) if not v["passed"]]),
                "time_s": r.get("timing", {}).get("l1_extract_s", 0),
            } for r in all_results]
        }, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {OUTPUT_DIR}")
    return all_results


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run_batch(limit=limit)
