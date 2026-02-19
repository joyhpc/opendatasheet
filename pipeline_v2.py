"""
OpenDatasheet Pipeline v0.2 — 混合模式 (Text + Vision)
L0: PyMuPDF 页面分类 + 文本提取
L1a: Gemini Vision — 电气特性页面发图片 (解决非标表格)
L1b: Gemini Text — 其他页面走文本 (pin definitions 等)
L2: Pydantic 物理规则校验
L3: 自动化交叉验证 (PDF 原文 vs 提取结果)

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
from google.genai import types

# ============================================
# Config
# ============================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDhJ4wpmDGI139p-bC4dmB_A2MIFAlT1R4")
GEMINI_MODEL = "gemini-3-flash-preview"
DATA_DIR = Path(__file__).parent / "data" / "raw" / "datasheet_PDF"
OUTPUT_DIR = Path(__file__).parent / "data" / "extracted_v2"
DPI = 200  # 渲染分辨率

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ============================================
# L0: PyMuPDF 页面分类 (复用 v0.1)
# ============================================
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
    page_num: int
    text_length: int
    category: str
    matched_patterns: list = field(default_factory=list)
    text_preview: str = ""


def classify_pages(pdf_path: str) -> list[PageInfo]:
    doc = fitz.open(pdf_path)
    pages = []
    for i in range(len(doc)):
        text = doc[i].get_text()
        text_len = len(text)
        category = "other"
        matched = []
        if i == 0:
            category = "cover"
        for pat in ELECTRICAL_PATTERNS:
            if pat.search(text):
                category = "electrical"
                matched.append(pat.pattern)
        for pat in PIN_PATTERNS:
            if pat.search(text):
                if category != "electrical":
                    category = "pin"
                matched.append(pat.pattern)
        for pat in ORDERING_PATTERNS:
            if pat.search(text):
                if category not in ("electrical", "pin"):
                    category = "ordering"
                matched.append(pat.pattern)
        if text_len < 100:
            category = "image_only"
        pages.append(PageInfo(
            page_num=i, text_length=text_len, category=category,
            matched_patterns=matched, text_preview=text[:200].replace('\n', ' ')
        ))
    doc.close()
    return pages


# ============================================
# L1a: Vision 提取 (电气特性页面)
# ============================================

VISION_PROMPT = """You are an expert electronic component datasheet parser. These images show pages from an electronic component datasheet.

CRITICAL RULES:
1. Extract ALL electrical parameters with min/typ/max values and units
2. Many datasheets have DUAL-ROW format: each parameter has TWO rows of min/typ/max
   - One row for 25°C specs, another for full temperature range
   - You MUST extract BOTH rows as separate entries
3. If the datasheet covers MULTIPLE VARIANTS (e.g., different output voltages),
   extract parameters for ALL variants separately
4. Include test conditions for each parameter
5. If a value is not specified, use null
6. Extract pin definitions if visible
7. Output ONLY valid JSON, no markdown, no code fences

OUTPUT JSON SCHEMA:
{
  "component": {
    "mpn": "string (main part number)",
    "manufacturer": "string",
    "category": "string (LDO/Buck/OpAmp/Switch/Logic/ADC/DAC/Interface/Other)",
    "description": "string (one line)"
  },
  "absolute_maximum_ratings": [
    {"parameter": "string", "raw_name": "string", "symbol": "string", "min": null or number, "typ": null or number, "max": null or number, "unit": "string", "conditions": "string or null"}
  ],
  "electrical_characteristics": [
    {"parameter": "string", "raw_name": "string", "symbol": "string", "min": null or number, "typ": null or number, "max": null or number, "unit": "string", "conditions": "string or null", "device": "string (variant if applicable)", "temp_range": "25C or full or null"}
  ],
  "pin_definitions": [
    {"pin_number": "string or number", "pin_name": "string", "type": "string", "description": "string"}
  ]
}"""


def render_pages_to_images(pdf_path: str, page_nums: list[int]) -> list[bytes]:
    """渲染指定页面为 PNG 图片"""
    doc = fitz.open(pdf_path)
    images = []
    for i in page_nums:
        pix = doc[i].get_pixmap(dpi=DPI)
        images.append(pix.tobytes('png'))
    doc.close()
    return images


def extract_with_vision(images: list[bytes], pdf_name: str, max_retries: int = 2) -> dict:
    """L1a: 用 Gemini Vision 从页面图片提取参数"""
    contents = [VISION_PROMPT]
    for img in images:
        contents.append(types.Part.from_bytes(data=img, mime_type='image/png'))

    for attempt in range(max_retries + 1):
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config={"temperature": 0.1},
            )
            raw = response.text
            # 清理 markdown 包裹
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            # 找 JSON 边界
            start = raw.find('{')
            end = raw.rfind('}')
            if start >= 0 and end > start:
                raw = raw[start:end+1]
            result = json.loads(raw.strip())
            if isinstance(result, list):
                result = result[0] if result else {"error": "Empty list"}
            if not isinstance(result, dict):
                return {"error": f"Unexpected type: {type(result).__name__}"}
            return result
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                time.sleep(3)
                continue
            return {"error": f"JSON parse failed: {str(e)}", "raw": raw[:500] if 'raw' in dir() else ""}
        except Exception as e:
            if attempt < max_retries and ("503" in str(e) or "429" in str(e) or "504" in str(e)):
                time.sleep(10)
                continue
            return {"error": str(e)}


# ============================================
# L2: 物理规则校验 (复用 v0.1)
# ============================================

@dataclass
class ValidationResult:
    param: str
    rule: str
    passed: bool
    message: str


def validate_extraction(data: dict) -> list[ValidationResult]:
    results = []
    for section in ["absolute_maximum_ratings", "electrical_characteristics"]:
        params = data.get(section, [])
        for p in params:
            name = p.get("parameter", "")
            min_v = p.get("min")
            typ_v = p.get("typ")
            max_v = p.get("max")
            vals = [v for v in [min_v, typ_v, max_v] if v is not None]
            if len(vals) >= 2:
                if vals != sorted(vals):
                    results.append(ValidationResult(
                        param=name, rule="monotonicity", passed=False,
                        message=f"min/typ/max not monotonic: {min_v}/{typ_v}/{max_v}"
                    ))
                else:
                    results.append(ValidationResult(
                        param=name, rule="monotonicity", passed=True, message="OK"
                    ))
            unit = p.get("unit", "")
            if unit and not re.match(r'^[µμunmpkMGT]?[AVWΩHzFsS°C%dB/()RMS]+$', unit):
                results.append(ValidationResult(
                    param=name, rule="unit_valid", passed=False,
                    message=f"Suspicious unit: {unit}"
                ))
    return results


# ============================================
# L3: 自动化交叉验证
# ============================================

def cross_validate(pdf_path: str, extraction: dict, pages: list[PageInfo]) -> dict:
    """用 PDF 原始文本交叉验证提取结果"""
    doc = fitz.open(pdf_path)

    # 收集电气特性页面的所有数字 (支持千分位逗号)
    target_cats = {"electrical", "pin", "cover"}
    pdf_numbers = set()
    pdf_lines = []
    for p in pages:
        if p.category in target_cats:
            text = doc[p.page_num].get_text()
            for line in text.split('\n'):
                line = line.strip()
                if line:
                    pdf_lines.append(line)
            nums = re.findall(r'-?\d[\d,]*\.?\d*', text)
            for n in nums:
                try:
                    pdf_numbers.add(float(n.replace(',', '')))
                except:
                    pass
    doc.close()

    # 检查每个提取的数值是否在 PDF 中存在
    extracted_numbers = set()
    for section in ['electrical_characteristics', 'absolute_maximum_ratings']:
        for p in extraction.get(section, []):
            for key in ['min', 'typ', 'max']:
                v = p.get(key)
                if v is not None:
                    extracted_numbers.add(float(v))

    values_in_pdf = extracted_numbers & pdf_numbers
    values_not_in_pdf = extracted_numbers - pdf_numbers
    value_coverage = len(values_in_pdf) / len(extracted_numbers) * 100 if extracted_numbers else 0

    # 行邻近验证: 每个参数的 min/typ/max 是否在 PDF 相邻行中共现
    params_verified = 0
    params_suspicious = 0
    suspicious_params = []
    total_params = 0

    for section in ['electrical_characteristics', 'absolute_maximum_ratings']:
        for p in extraction.get(section, []):
            total_params += 1
            vals = []
            for key in ['min', 'typ', 'max']:
                v = p.get(key)
                if v is not None:
                    vals.append(float(v))
            if not vals:
                params_verified += 1
                continue

            found = False
            for i, line in enumerate(pdf_lines):
                line_nums = set()
                for j in range(max(0, i-3), min(len(pdf_lines), i+4)):
                    nums = re.findall(r'-?\d[\d,]*\.?\d*', pdf_lines[j])
                    for n in nums:
                        try:
                            line_nums.add(float(n.replace(',', '')))
                        except:
                            pass
                if all(v in line_nums for v in vals):
                    found = True
                    break

            if found:
                params_verified += 1
            else:
                params_suspicious += 1
                suspicious_params.append({
                    "parameter": p.get("parameter", "?"),
                    "device": p.get("device", ""),
                    "values": vals,
                })

    return {
        "total_extracted_values": len(extracted_numbers),
        "values_found_in_pdf": len(values_in_pdf),
        "values_not_in_pdf": sorted(list(values_not_in_pdf)),
        "value_coverage_pct": round(value_coverage, 1),
        "total_params": total_params,
        "params_verified": params_verified,
        "params_suspicious": params_suspicious,
        "suspicious_params": suspicious_params,
    }


# ============================================
# Main Pipeline
# ============================================

def process_single_pdf(pdf_path: str, verbose: bool = True) -> dict:
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
    cover_pages = [p for p in pages if p.category == "cover"]

    # Vision 目标页面: electrical + pin + cover
    vision_page_nums = sorted(set(
        [p.page_num for p in electrical_pages] +
        [p.page_num for p in pin_pages] +
        [p.page_num for p in cover_pages]
    ))

    if verbose:
        print(f"\nL0 Page Classification ({l0_time:.3f}s):")
        print(f"  Total pages: {len(pages)}")
        print(f"  Electrical: {len(electrical_pages)} pages")
        print(f"  Pin defs:   {len(pin_pages)} pages")
        print(f"  Vision targets: {len(vision_page_nums)} pages → {vision_page_nums}")
        for p in pages:
            marker = "★" if p.page_num in vision_page_nums else " "
            print(f"  {marker} P{p.page_num+1:2d} [{p.category:12s}] {p.text_length:5d} chars")

    # L1a: Vision 提取
    t1 = time.time()
    images = render_pages_to_images(pdf_path, vision_page_nums)
    if verbose:
        total_img_size = sum(len(img) for img in images)
        print(f"\n  Rendered {len(images)} pages → {total_img_size/1024:.0f} KB")

    extraction = extract_with_vision(images, pdf_name)
    l1_time = time.time() - t1

    if verbose:
        if "error" in extraction:
            print(f"\nL1 Vision Extraction FAILED ({l1_time:.1f}s): {extraction['error']}")
        else:
            comp = extraction.get("component", {})
            amr = extraction.get("absolute_maximum_ratings", [])
            ec = extraction.get("electrical_characteristics", [])
            pins = extraction.get("pin_definitions", [])
            print(f"\nL1 Vision Extraction ({l1_time:.1f}s):")
            print(f"  Component: {comp.get('mpn', '?')} ({comp.get('manufacturer', '?')})")
            print(f"  Category:  {comp.get('category', '?')}")
            print(f"  Abs Max Ratings:  {len(amr)} params")
            print(f"  Elec Chars:       {len(ec)} params")
            print(f"  Pin Definitions:  {len(pins)} pins")
            # 变体和温度覆盖统计
            devices = set(p.get('device', '') for p in ec if p.get('device'))
            temps = set(p.get('temp_range', '') for p in ec if p.get('temp_range'))
            if devices:
                print(f"  Devices:  {sorted(devices)}")
            if temps:
                print(f"  Temp ranges: {sorted(temps)}")

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

    # L3: 交叉验证
    cross_val = {}
    if "error" not in extraction:
        cross_val = cross_validate(pdf_path, extraction, pages)
        if verbose:
            print(f"\nL3 Cross-Validation:")
            print(f"  Value coverage: {cross_val['values_found_in_pdf']}/{cross_val['total_extracted_values']} ({cross_val['value_coverage_pct']}%)")
            print(f"  Param alignment: {cross_val['params_verified']}/{cross_val['total_params']} verified")
            if cross_val['params_suspicious'] > 0:
                print(f"  ⚠️ Suspicious: {cross_val['params_suspicious']}")
                for sp in cross_val['suspicious_params'][:5]:
                    print(f"    - {sp['parameter']} ({sp['device']}): {sp['values']}")

    result = {
        "pdf_name": pdf_name,
        "model": GEMINI_MODEL,
        "mode": "vision",
        "checksum": hashlib.md5(open(pdf_path, 'rb').read()).hexdigest(),
        "total_pages": len(pages),
        "vision_pages": vision_page_nums,
        "page_classification": [asdict(p) for p in pages],
        "extraction": extraction,
        "validation": [asdict(v) for v in validations],
        "cross_validation": cross_val,
        "timing": {
            "l0_classify_s": round(l0_time, 3),
            "l1_extract_s": round(l1_time, 3),
        }
    }
    return result


def run_batch(limit: int = 5):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    lock_path = OUTPUT_DIR / ".pipeline.lock"
    lock_fd = open(lock_path, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("ERROR: Another pipeline instance is already running!")
        sys.exit(1)
    lock_fd.write(f"pid={os.getpid()} started={time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
    lock_fd.flush()

    pdf_files = sorted([f for f in DATA_DIR.iterdir() if f.suffix.lower() == '.pdf'])
    if limit:
        pdf_files = pdf_files[:limit]

    print(f"OpenDatasheet Pipeline v0.2 (Vision Mode)")
    print(f"Model: {GEMINI_MODEL}")
    print(f"PDFs to process: {len(pdf_files)}")

    all_results = []
    total_params = 0
    total_failures = 0
    total_suspicious = 0

    for pdf_path in pdf_files:
        out_name = pdf_path.stem + ".json"
        out_path = OUTPUT_DIR / out_name
        if out_path.exists() and out_path.stat().st_size > 100:
            print(f"\n⏭ Skipping (already done): {pdf_path.name}")
            with open(out_path, 'r') as f:
                result = json.load(f)
            all_results.append(result)
            ext = result.get("extraction", {})
            if isinstance(ext, dict) and "error" not in ext:
                total_params += len(ext.get("absolute_maximum_ratings", []))
                total_params += len(ext.get("electrical_characteristics", []))
            total_failures += len([v for v in result.get("validation", []) if not v.get("passed", True)])
            total_suspicious += result.get("cross_validation", {}).get("params_suspicious", 0)
            continue

        result = process_single_pdf(str(pdf_path))
        all_results.append(result)

        ext = result.get("extraction", {})
        if isinstance(ext, dict) and "error" not in ext:
            total_params += len(ext.get("absolute_maximum_ratings", []))
            total_params += len(ext.get("electrical_characteristics", []))
        total_failures += len([v for v in result.get("validation", []) if not v.get("passed", True)])
        total_suspicious += result.get("cross_validation", {}).get("params_suspicious", 0)

        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        time.sleep(5)

    # Summary
    print(f"\n{'='*60}")
    print(f"BATCH SUMMARY (v0.2 Vision)")
    print(f"{'='*60}")
    print(f"PDFs processed: {len(all_results)}")
    print(f"Total parameters extracted: {total_params}")
    print(f"Validation failures: {total_failures}")
    print(f"Cross-validation suspicious: {total_suspicious}")

    summary_path = OUTPUT_DIR / "_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump({
            "pipeline_version": "0.2",
            "mode": "vision",
            "model": GEMINI_MODEL,
            "total_pdfs": len(all_results),
            "total_params": total_params,
            "total_validation_failures": total_failures,
            "total_cross_validation_suspicious": total_suspicious,
            "results": [{
                "pdf": r["pdf_name"],
                "mpn": r.get("extraction", {}).get("component", {}).get("mpn", "?") if isinstance(r.get("extraction"), dict) else "?",
                "category": r.get("extraction", {}).get("component", {}).get("category", "?") if isinstance(r.get("extraction"), dict) else "?",
                "params": (len(r.get("extraction", {}).get("electrical_characteristics", [])) +
                          len(r.get("extraction", {}).get("absolute_maximum_ratings", []))) if isinstance(r.get("extraction"), dict) else 0,
                "pins": len(r.get("extraction", {}).get("pin_definitions", [])) if isinstance(r.get("extraction"), dict) else 0,
                "validation_failures": len([v for v in r.get("validation", []) if not v.get("passed", True)]),
                "cross_val_coverage": r.get("cross_validation", {}).get("value_coverage_pct", 0),
                "cross_val_suspicious": r.get("cross_validation", {}).get("params_suspicious", 0),
                "time_s": r.get("timing", {}).get("l1_extract_s", 0),
            } for r in all_results]
        }, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {OUTPUT_DIR}")
    return all_results


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run_batch(limit=limit)
