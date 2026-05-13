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
import math
import hashlib
import signal
import concurrent.futures
import argparse
import httpx
from pathlib import Path
from design_info_utils import APPLICATION_PATTERNS, detect_design_page_kind, extract_design_context

from extractors import EXTRACTOR_REGISTRY
from runtime._locking import try_exclusive_lock


class GeminiTimeout(Exception):
    """Raised when a Gemini API call exceeds the allowed time."""
    pass


def _timeout_handler(signum, frame):
    raise GeminiTimeout("Gemini API call timed out after 180s")
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Union

from google import genai


# ============================================
# Q1: 双轨推断模型 — 负压/负电流单调性验证
# ============================================

def get_supported_modes(min_val, typ_val, max_val):
    """推断单行数据支持的排版模式：ALGEBRAIC (代数) 或 MAGNITUDE (幅值)"""
    vals = [v for v in [min_val, typ_val, max_val] if v is not None]
    if len(vals) <= 1:
        modes = ['ALGEBRAIC']
        if not vals or vals[0] <= 0:
            modes.append('MAGNITUDE')
        return modes
    modes = []
    if all(vals[i] <= vals[i+1] for i in range(len(vals)-1)):
        modes.append('ALGEBRAIC')
    if all(vals[i] >= vals[i+1] for i in range(len(vals)-1)) and all(v <= 0 for v in vals):
        modes.append('MAGNITUDE')
    return modes


def get_physical_interval(min_val, max_val, mode):
    """将字面 min/max 映射为物理数轴上真实的代数区间 [L, U]"""
    if mode == 'ALGEBRAIC':
        L = min_val if min_val is not None else -math.inf
        U = max_val if max_val is not None else math.inf
        return L, U
    elif mode == 'MAGNITUDE':
        L = max_val if max_val is not None else -math.inf
        U = min_val if min_val is not None else 0.0
        return L, U


# ============================================
# Q2: DatasheetValueValidator — 负数文本匹配
# ============================================

class DatasheetValueValidator:
    """从 PDF 原始文本中提取所有数值（含负号变体处理），用于交叉验证"""

    def __init__(self, rel_tol: float = 1e-5, abs_tol: float = 1e-8):
        self.rel_tol = rel_tol
        self.abs_tol = abs_tol
        self.minus_chars = '-\u2010\u2011\u2012\u2013\u2014\u2212'
        self.base_num_pattern = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+'
        mc_escaped = self.minus_chars.replace('-', r'\-')
        self.exp_pattern = fr'(?:[eE]\s*[+{mc_escaped}]?\s*\d+)?'
        self.regex = re.compile(fr'({self.base_num_pattern}{self.exp_pattern})')

    def extract_floats_from_text(self, raw_text: str) -> List[float]:
        """将 PDF 原始文本中的所有数值转化为浮点数，智能推断极性"""
        parsed_numbers = []
        mc_escaped = self.minus_chars.replace('-', r'\-')

        for match in self.regex.finditer(raw_text):
            num_str = match.group(1)
            clean_num = num_str.replace(',', '').replace(' ', '')
            for mc in self.minus_chars:
                clean_num = clean_num.replace(mc, '-')
            try:
                val = float(clean_num)
            except ValueError:
                continue

            start_idx = match.start()
            preceding = raw_text[:start_idx]
            preceding_stripped = preceding.rstrip()
            signs = [1.0]

            if preceding_stripped:
                last_char = preceding_stripped[-1]
                if last_char == '±':
                    signs = [1.0, -1.0]
                elif last_char in self.minus_chars:
                    if re.search(fr'\+/?\s*[{mc_escaped}]$', preceding_stripped):
                        signs = [1.0, -1.0]
                    # Multi-dash (2+) = table separator / "no data" marker, not negative sign
                    elif len(preceding_stripped) >= 2 and preceding_stripped[-2] in self.minus_chars:
                        signs = [1.0]
                    else:
                        before_minus_exact = preceding_stripped[:-1]
                        before_minus_stripped = before_minus_exact.rstrip()
                        whitespace_before = before_minus_exact[len(before_minus_stripped):]
                        whitespace_after = preceding[len(preceding_stripped):]
                        space_before = len(whitespace_before)
                        space_after = len(whitespace_after)

                        # Datasheet heuristic: if the minus is on a different line
                        # (separated by \n) and appears standalone, it's a "no data"
                        # placeholder, not a negative sign
                        if '\n' in whitespace_after:
                            # Check if the minus sign is standalone on its line
                            last_line = preceding_stripped.split('\n')[-1].strip()
                            if last_line in set(self.minus_chars) or re.match(fr'^[{mc_escaped}]$', last_line):
                                signs = [1.0]  # standalone dash = no data marker
                                for s in signs:
                                    final_val = val * s
                                    if final_val == -0.0:
                                        final_val = 0.0
                                    parsed_numbers.append(final_val)
                                continue

                        has_digit = False
                        words = before_minus_stripped.split()
                        if words:
                            last_word = words[-1]
                            if any(c.isdigit() for c in last_word):
                                has_digit = True
                            elif len(words) >= 2 and any(c.isdigit() for c in words[-2]):
                                if last_word.isalpha() and len(last_word) <= 3 and last_word.lower() not in ["to", "and", "or"]:
                                    has_digit = True
                            if last_word.endswith(':') or last_word.endswith('=') or last_word.endswith(','):
                                has_digit = False
                        if has_digit:
                            if space_before >= 2 or '\n' in whitespace_before or '\t' in whitespace_before:
                                is_range = False
                            elif space_before == space_after:
                                is_range = True
                            elif space_before > space_after:
                                is_range = False
                            else:
                                is_range = True
                        else:
                            is_range = False
                        if not is_range:
                            signs = [-1.0]
                elif last_char == '+':
                    signs = [1.0]

            for s in signs:
                final_val = val * s
                if final_val == -0.0:
                    final_val = 0.0
                parsed_numbers.append(final_val)

        return parsed_numbers

    def is_value_in_text(self, target_value: Union[float, int, str], raw_text: str) -> bool:
        """验证目标数值是否存在于原文中（语义级浮点比对）"""
        try:
            if isinstance(target_value, str):
                target_value = target_value.replace(',', '')
            target_float = float(target_value)
        except (ValueError, TypeError):
            return False
        extracted_numbers = self.extract_floats_from_text(raw_text)
        for num in extracted_numbers:
            if math.isclose(target_float, num, rel_tol=self.rel_tol, abs_tol=self.abs_tol):
                return True
        return False

# ============================================
# Config
# ============================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3-flash-preview"
DATA_DIR = Path(__file__).parent / "data" / "raw" / "datasheet_PDF"
OUTPUT_DIR = Path(__file__).parent / "data" / "extracted_v2"
DPI = 200  # 渲染分辨率

_httpx_client = httpx.Client(
    timeout=httpx.Timeout(connect=30.0, read=120.0, write=60.0, pool=30.0)
)


def get_gemini_client() -> genai.Client:
    """Return a configured Gemini client or raise a clear configuration error."""
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "Missing GEMINI_API_KEY environment variable. "
            "Export it before running pipeline_v2.py, for example: "
            "export GEMINI_API_KEY='<your-api-key>'"
        )
    return genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={"httpx_client": _httpx_client, "timeout": 300_000},
    )

API_TIMEOUT = 180  # seconds — hard kill via thread timeout

def gemini_generate(model, contents, config=None):
    """Direct call to gemini_client.models.generate_content — httpx timeout handles hangs."""
    return get_gemini_client().models.generate_content(
        model=model, contents=contents, config=config or {}
    )

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
    re.compile(r'(?i)pin\s+(description|configuration|function|assignment|definition|connection|diagram)'),
    re.compile(r'(?i)pin\s+connections?'),
    re.compile(r'(?i)pin[-\s]?out'),
    re.compile(r'(?i)pin\s+name'),
    re.compile(r'(?i)terminal\s+function'),
]

ORDERING_PATTERNS = [
    re.compile(r'(?i)ordering\s+information'),
    re.compile(r'(?i)package\s+information'),
    re.compile(r'(?i)marking\s+information'),
]

# FPGA-specific: pages that mention pin names but are NOT pin definition pages
FPGA_PIN_FALSE_POSITIVE_PATTERNS = [
    re.compile(r'(?i)pin[-\s]?to[-\s]?pin\s+(output|input|delay|parameter)'),
    re.compile(r'(?i)configuration\s+switching\s+characteristics'),
    re.compile(r'(?i)revision\s+(history|summary)'),
    re.compile(r'(?i)boundary[-\s]?scan\s+port'),
]

# FPGA-specific: power supply pin group pages (useful for FPGA "pin" extraction)
FPGA_SUPPLY_PIN_PATTERNS = [
    re.compile(r'(?i)power\s+supply\s+(requirements?|pins?|rails?)'),
    re.compile(r'(?i)supply\s+voltage\s+(summary|table)'),
    re.compile(r'(?i)quiescent\s+supply\s+current'),
]

# Detect FPGA datasheet from cover/early pages
FPGA_DETECT_PATTERNS = [
    re.compile(r'(?i)\b(FPGA|CPLD|SoC|MPSoC|RFSoC|ACAP)\b'),
    re.compile(r'(?i)\b(UltraScale|Versal|Spartan|Artix|Kintex|Virtex|Zynq)\b'),
    re.compile(r'(?i)\bXC[A-Z]{1,2}\d+[A-Z]*\b'),  # Xilinx part numbers like XCKU3P, XCAU15P
    re.compile(r'(?i)\b(Cyclone|Stratix|Arria|MAX\s*10|Agilex)\b'),  # Intel/Altera
    re.compile(r'(?i)\b(ECP5|MachXO|CrossLink|Certus)\b'),  # Lattice
]


@dataclass
class PageInfo:
    page_num: int
    text_length: int
    category: str
    matched_patterns: list = field(default_factory=list)
    text_preview: str = ""


def detect_fpga_datasheet(pdf_path: str) -> bool:
    """Detect if this is an FPGA datasheet by scanning first 3 pages."""
    doc = fitz.open(pdf_path)
    is_fpga = False
    fpga_hits = 0
    for i in range(min(3, len(doc))):
        text = doc[i].get_text()
        for pat in FPGA_DETECT_PATTERNS:
            if pat.search(text):
                fpga_hits += 1
    doc.close()
    # Need at least 2 hits to confirm (avoid false positives from random mentions)
    return fpga_hits >= 2


def classify_pages(pdf_path: str, is_fpga: bool = False) -> list[PageInfo]:
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
                    # FPGA: check for false positive pin pages
                    if is_fpga:
                        is_false_positive = any(fp.search(text) for fp in FPGA_PIN_FALSE_POSITIVE_PATTERNS)
                        if is_false_positive:
                            # Reclassify as electrical (these are switching characteristics)
                            if category != "electrical":
                                category = "electrical"
                            matched.append("FPGA_PIN_FALSE_POSITIVE")
                        else:
                            category = "pin"
                    else:
                        category = "pin"
                matched.append(pat.pattern)
        # FPGA: detect power supply pin group pages
        if is_fpga:
            for pat in FPGA_SUPPLY_PIN_PATTERNS:
                if pat.search(text):
                    if category not in ("electrical",):
                        category = "fpga_supply"
                    matched.append(pat.pattern)
        for pat in ORDERING_PATTERNS:
            if pat.search(text):
                if category not in ("electrical", "pin", "fpga_supply"):
                    category = "ordering"
                matched.append(pat.pattern)
        for pat in APPLICATION_PATTERNS:
            if pat.search(text):
                if category not in ("electrical", "pin", "fpga_supply", "ordering"):
                    category = "application"
                matched.append(pat.pattern)
        if text_len < 100:
            category = "image_only"
        pages.append(PageInfo(
            page_num=i, text_length=text_len, category=category,
            matched_patterns=matched, text_preview=text[:200].replace('\n', ' ')
        ))
    doc.close()
    return pages


def render_pages_to_images(pdf_path: str, page_nums: list[int]) -> list[bytes]:
    """渲染指定页面为 PNG 图片"""
    doc = fitz.open(pdf_path)
    images = []
    for i in page_nums:
        pix = doc[i].get_pixmap(dpi=DPI)
        images.append(pix.tobytes('png'))
    doc.close()
    return images


# ============================================
# Pin transform / validation helpers (legacy flat output compatibility)
# ============================================

# Enum sets for validation
VALID_DIRECTIONS = {"INPUT", "OUTPUT", "BIDIRECTIONAL", "POWER_IN", "POWER_OUT", "PASSIVE", "NC"}
VALID_SIGNAL_TYPES = {"DIGITAL", "ANALOG", "POWER", "NONE"}
VALID_UNUSED_TREATMENTS = {"FLOAT", "GND", "VCC", "PULL_UP", "PULL_DOWN", "CUSTOM", None}


def transform_pins_to_package_indexed(logical_pins: list) -> dict:
    """将 logical_pins 列表转换为按封装拆分、pin number 做 key 的索引结构。

    输入: logical_pins 列表 (Gemini 原始输出)
    输出: {"packages": {"封装名": {"pin_number_str": {name, direction, signal_type, description, unused_treatment}}}}

    冲突处理: 同一物理 pin 被多个逻辑 pin 占用时，保留第一个，description 追加注明。
    """
    packages = {}  # {pkg_name: {pin_str: {attrs}}}

    for lp in logical_pins:
        name = lp.get("name", "")
        direction = lp.get("direction", "")
        signal_type = lp.get("signal_type", "")
        description = lp.get("description", "")
        unused_treatment = lp.get("unused_treatment")
        pkg_map = lp.get("packages", {})

        if not isinstance(pkg_map, dict):
            continue

        for pkg_name, pin_nums in pkg_map.items():
            if pkg_name not in packages:
                packages[pkg_name] = {}
            if not isinstance(pin_nums, list):
                continue
            for pn in pin_nums:
                pn_str = str(pn)
                entry = {
                    "name": name,
                    "direction": direction,
                    "signal_type": signal_type,
                    "description": description,
                    "unused_treatment": unused_treatment,
                }
                if pn_str in packages[pkg_name]:
                    # 冲突：追加注明到已有 entry 的 description
                    existing = packages[pkg_name][pn_str]
                    existing["description"] += f" (also: {name} — {description})"
                else:
                    packages[pkg_name][pn_str] = entry

    return {"packages": packages}


def validate_pins(pin_data: dict) -> list[dict]:
    """验证 pin 提取结果的合法性，返回 issues 列表"""
    issues = []
    pins = pin_data.get("logical_pins", [])

    if not pins:
        issues.append({"level": "error", "message": "No logical_pins found"})
        return issues

    seen_names = set()
    # 收集每个 package 内的 pin number 映射，用于检测重复
    package_pin_map = {}  # {package_name: {pin_number: [pin_names]}}

    for i, pin in enumerate(pins):
        prefix = f"pin[{i}]"

        # name 不能为空
        name = pin.get("name", "")
        if not name or not str(name).strip():
            issues.append({"level": "error", "message": f"{prefix}: empty name"})
            continue

        name = str(name).strip()

        # 检查重复 pin name
        if name in seen_names:
            issues.append({"level": "warning", "message": f"{prefix}: duplicate pin name '{name}'"})
        seen_names.add(name)

        # direction 枚举检查
        direction = pin.get("direction", "")
        if direction not in VALID_DIRECTIONS:
            issues.append({"level": "error", "message": f"{prefix} '{name}': invalid direction '{direction}', must be one of {sorted(VALID_DIRECTIONS)}"})

        # signal_type 枚举检查
        signal_type = pin.get("signal_type", "")
        if signal_type not in VALID_SIGNAL_TYPES:
            issues.append({"level": "error", "message": f"{prefix} '{name}': invalid signal_type '{signal_type}', must be one of {sorted(VALID_SIGNAL_TYPES)}"})

        # unused_treatment 枚举检查
        unused = pin.get("unused_treatment")
        if unused not in VALID_UNUSED_TREATMENTS:
            issues.append({"level": "error", "message": f"{prefix} '{name}': invalid unused_treatment '{unused}', must be one of {sorted(str(v) for v in VALID_UNUSED_TREATMENTS)}"})

        # packages 结构检查
        packages = pin.get("packages")
        if not isinstance(packages, dict):
            issues.append({"level": "error", "message": f"{prefix} '{name}': packages must be a dict, got {type(packages).__name__}"})
        elif not packages:
            issues.append({"level": "error", "message": f"{prefix} '{name}': packages dict is empty"})
        else:
            for pkg_name, pin_nums in packages.items():
                if not isinstance(pin_nums, list):
                    issues.append({"level": "error", "message": f"{prefix} '{name}': packages['{pkg_name}'] must be a list, got {type(pin_nums).__name__}"})
                else:
                    # 检查同一 package 内是否有 pin number 冲突
                    if pkg_name not in package_pin_map:
                        package_pin_map[pkg_name] = {}
                    for pn in pin_nums:
                        pn_key = str(pn)
                        if pn_key not in package_pin_map[pkg_name]:
                            package_pin_map[pkg_name][pn_key] = []
                        package_pin_map[pkg_name][pn_key].append(name)

    # 检查同一 package 内同一 pin number 被多个逻辑 pin 占用
    for pkg_name, pn_map in package_pin_map.items():
        for pn, names in pn_map.items():
            if len(names) > 1:
                issues.append({"level": "warning", "message": f"package '{pkg_name}' pin {pn} claimed by multiple logical pins: {names}"})

    return issues


VALID_FPGA_PIN_GROUPS = {"POWER_SUPPLY", "CONFIGURATION", "TRANSCEIVER", "SYSTEM_MONITOR", "CLOCK", "OTHER"}


def validate_fpga_pins(pin_data: dict) -> list[dict]:
    """Validate FPGA pin extraction results. Packages are expected to be empty."""
    issues = []
    pins = pin_data.get("logical_pins", [])

    if not pins:
        issues.append({"level": "warning", "message": "No logical_pins found (may be normal for some FPGA datasheets)"})
        return issues

    seen_names = set()
    for i, pin in enumerate(pins):
        prefix = f"pin[{i}]"
        name = pin.get("name", "")
        if not name or not str(name).strip():
            issues.append({"level": "error", "message": f"{prefix}: empty name"})
            continue
        name = str(name).strip()

        if name in seen_names:
            issues.append({"level": "warning", "message": f"{prefix}: duplicate pin name '{name}'"})
        seen_names.add(name)

        direction = pin.get("direction", "")
        if direction not in VALID_DIRECTIONS:
            issues.append({"level": "error", "message": f"{prefix} '{name}': invalid direction '{direction}'"})

        signal_type = pin.get("signal_type", "")
        if signal_type not in VALID_SIGNAL_TYPES:
            issues.append({"level": "error", "message": f"{prefix} '{name}': invalid signal_type '{signal_type}'"})

        pin_group = pin.get("pin_group", "")
        if pin_group not in VALID_FPGA_PIN_GROUPS:
            issues.append({"level": "warning", "message": f"{prefix} '{name}': unknown pin_group '{pin_group}'"})

        # FPGA: packages should be empty dict — that's expected, not an error
        packages = pin.get("packages", {})
        if packages and isinstance(packages, dict) and any(v for v in packages.values()):
            issues.append({"level": "warning", "message": f"{prefix} '{name}': unexpected non-empty packages (FPGA DC/AC datasheets don't have pin mapping)"})

    # Check minimum expected pin groups for FPGA
    found_groups = set(p.get("pin_group", "") for p in pins)
    if "POWER_SUPPLY" not in found_groups:
        issues.append({"level": "warning", "message": "No POWER_SUPPLY pins found — expected for FPGA datasheets"})
    if "CONFIGURATION" not in found_groups:
        issues.append({"level": "warning", "message": "No CONFIGURATION pins found — expected for FPGA datasheets"})

    return issues


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
                # Q1: 双轨推断 — ALGEBRAIC 或 MAGNITUDE 任一通过即合法
                modes = get_supported_modes(min_v, typ_v, max_v)
                if modes:
                    results.append(ValidationResult(
                        param=name, rule="monotonicity", passed=True,
                        message=f"OK (modes: {','.join(modes)})"
                    ))
                else:
                    results.append(ValidationResult(
                        param=name, rule="monotonicity", passed=False,
                        message=f"min/typ/max not monotonic: {min_v}/{typ_v}/{max_v}"
                    ))
            unit = p.get("unit", "")
            if unit and not re.match(r'^[µμunmpkMGT]?[AVWΩHzFsS°C%dB/()RMS]+$', unit):
                results.append(ValidationResult(
                    param=name, rule="unit_valid", passed=False,
                    message=f"Suspicious unit: {unit}"
                ))
    return results


# ============================================
# L5: 物理规则引擎 (领域知识驱动)
# ============================================

def validate_physics(data: dict) -> list[ValidationResult]:
    """L5: 领域知识驱动的物理规则验证"""
    results = []
    ec = data.get("electrical_characteristics", [])

    # --- Rule 1: 温度包络定律 ---
    # 对于同一参数+同一变体，full temp 的 max >= 25C 的 max，full temp 的 min <= 25C 的 min
    param_groups = {}  # key = (parameter, device/applies_to) -> {temp_range: {min, typ, max}}
    for p in ec:
        param_name = p.get("parameter", "")
        device = p.get("device") or str(p.get("applies_to", ""))
        temp = p.get("temp_range", "")
        if not temp or not param_name:
            continue
        key = (param_name, device)
        if key not in param_groups:
            param_groups[key] = {}
        param_groups[key][temp] = {
            "min": p.get("min"),
            "typ": p.get("typ"),
            "max": p.get("max"),
        }

    for (param_name, device), temps in param_groups.items():
        if "25C" in temps and "full" in temps:
            t25 = temps["25C"]
            tfull = temps["full"]

            # Q1: 双轨推断 — 先确定模式，再映射到物理区间做包容性判断
            modes_25 = get_supported_modes(t25["min"], t25["typ"], t25["max"])
            modes_full = get_supported_modes(tfull["min"], tfull["typ"], tfull["max"])
            common_modes = set(modes_25) & set(modes_full)

            if not common_modes:
                results.append(ValidationResult(
                    param=f"{param_name} ({device})",
                    rule="temp_envelope",
                    passed=False,
                    message=f"25C and full temp data have conflicting conventions (modes_25={modes_25}, modes_full={modes_full})"
                ))
                continue

            eps = 1e-9
            envelope_ok = False
            for mode in common_modes:
                L_25, U_25 = get_physical_interval(t25["min"], t25["max"], mode)
                L_ft, U_ft = get_physical_interval(tfull["min"], tfull["max"], mode)

                # Only compare bounds where both sides have actual data
                lower_ok = True
                upper_ok = True
                if math.isfinite(L_25) and math.isfinite(L_ft):
                    lower_ok = L_ft <= L_25 + eps
                if math.isfinite(U_25) and math.isfinite(U_ft):
                    upper_ok = U_ft >= U_25 - eps

                if lower_ok and upper_ok:
                    envelope_ok = True
                    break

            if envelope_ok:
                results.append(ValidationResult(
                    param=f"{param_name} ({device})",
                    rule="temp_envelope",
                    passed=True,
                    message=f"OK (mode: {mode})"
                ))
            else:
                results.append(ValidationResult(
                    param=f"{param_name} ({device})",
                    rule="temp_envelope",
                    passed=False,
                    message=f"full temp physical interval does not contain 25C interval"
                ))

    # --- Rule 2: LDO 特定约束 ---
    category = data.get("component", {}).get("category", "").upper()
    if category == "LDO":
        for p in ec:
            name = p.get("parameter", "").lower()
            # Iq 通常 < 50mA for LDO
            if "quiescent" in name or name in ("iq",):
                unit = p.get("unit", "").lower()
                typ_v = p.get("typ")
                if typ_v is not None:
                    # 归一化到 mA
                    if "ua" in unit or "µa" in unit or "μa" in unit:
                        typ_ma = typ_v / 1000
                    elif "ma" in unit:
                        typ_ma = typ_v
                    elif "a" in unit and "m" not in unit and "µ" not in unit:
                        typ_ma = typ_v * 1000
                    else:
                        typ_ma = typ_v  # assume mA
                    if typ_ma > 50:
                        results.append(ValidationResult(
                            param=p.get("parameter", "Iq"),
                            rule="ldo_iq_range",
                            passed=False,
                            message=f"Iq typ={typ_v}{unit} ({typ_ma:.1f}mA) seems too high for LDO"
                        ))

    return results


# ============================================
# L3: 自动化交叉验证
# ============================================

def cross_validate(pdf_path: str, extraction: dict, pages: list[PageInfo]) -> dict:
    """用 PDF 原始文本交叉验证提取结果 (Q2: 使用 DatasheetValueValidator)"""
    doc = fitz.open(pdf_path)
    validator = DatasheetValueValidator()

    # 收集电气特性页面的原始文本和数值池
    target_cats = {"electrical", "pin", "cover"}
    pdf_lines = []
    all_raw_text = ""
    for p in pages:
        if p.category in target_cats:
            text = doc[p.page_num].get_text()
            all_raw_text += text + "\n"
            for line in text.split('\n'):
                line = line.strip()
                if line:
                    pdf_lines.append(line)
    doc.close()

    # Q2: 用 DatasheetValueValidator 构建全量数值池（处理负号变体）
    pdf_numbers_list = validator.extract_floats_from_text(all_raw_text)
    pdf_numbers = set(pdf_numbers_list)

    # 检查每个提取的数值是否在 PDF 数值池中存在
    extracted_numbers = set()
    for section in ['electrical_characteristics', 'absolute_maximum_ratings']:
        for p in extraction.get(section, []):
            for key in ['min', 'typ', 'max']:
                v = p.get(key)
                if v is not None:
                    extracted_numbers.add(float(v))

    # Q2: 使用 math.isclose 进行语义级比对
    values_in_pdf = set()
    values_not_in_pdf = set()
    for ev in extracted_numbers:
        found = False
        for pv in pdf_numbers:
            if math.isclose(ev, pv, rel_tol=1e-5, abs_tol=1e-8):
                found = True
                break
        if found:
            values_in_pdf.add(ev)
        else:
            values_not_in_pdf.add(ev)

    value_coverage = len(values_in_pdf) / len(extracted_numbers) * 100 if extracted_numbers else 0

    # 行邻近验证: 每个参数的 min/typ/max 是否在 PDF 相邻行中共现
    params_verified = 0
    params_suspicious = 0
    suspicious_params = []
    total_params = 0

    # 为每行也构建数值池（用 validator 处理负号）
    line_number_cache = {}
    for i, line in enumerate(pdf_lines):
        line_number_cache[i] = validator.extract_floats_from_text(line)

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
            for i in range(len(pdf_lines)):
                # 收集相邻行的数值池
                line_nums = []
                for j in range(max(0, i-3), min(len(pdf_lines), i+4)):
                    line_nums.extend(line_number_cache.get(j, []))

                # Q2: 用 math.isclose 比对每个值
                if all(
                    any(math.isclose(v, ln, rel_tol=1e-5, abs_tol=1e-8) for ln in line_nums)
                    for v in vals
                ):
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


def extract_design_pages_from_pdf(pdf_path: str, pages: list[PageInfo]) -> dict:
    """Extract schematic-design hints from application/layout pages using PDF text."""
    if not pages:
        return {
            "design_page_candidates": [],
            "recommended_external_components": [],
            "design_equation_hints": [],
            "layout_hints": [],
            "supply_recommendations": [],
            "topology_hints": [],
        }

    doc = fitz.open(pdf_path)
    text_pages = []
    for page in pages:
        text = doc[page.page_num].get_text()
        kind = detect_design_page_kind(text) or detect_design_page_kind(page.text_preview)
        if kind:
            text_pages.append({"page_num": page.page_num, "kind": kind, "text": text})
    doc.close()
    return extract_design_context(text_pages)


# ============================================
# Main Pipeline
# ============================================

def process_single_pdf(pdf_path: str, verbose: bool = True) -> dict:
    pdf_name = os.path.basename(pdf_path)
    if verbose:
        print(f"\n{'='*60}")
        print(f"Processing: {pdf_name}")
        print(f"{'='*60}")

    # L0: FPGA 检测
    is_fpga = detect_fpga_datasheet(pdf_path)
    if verbose and is_fpga:
        print(f"\n  🔧 FPGA datasheet detected — using FPGA-optimized pipeline")

    # L0: 页面分类
    t0 = time.time()
    pages = classify_pages(pdf_path, is_fpga=is_fpga)
    l0_time = time.time() - t0

    electrical_pages = [p for p in pages if p.category == "electrical"]
    pin_pages = [p for p in pages if p.category == "pin"]
    cover_pages = [p for p in pages if p.category == "cover"]
    application_pages = [p for p in pages if p.category == "application"]
    fpga_supply_pages = [p for p in pages if p.category == "fpga_supply"]

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
        print(f"  Application:{len(application_pages)} pages")
        print(f"  Vision targets: {len(vision_page_nums)} pages → {vision_page_nums}")
        for p in pages:
            marker = "★" if p.page_num in vision_page_nums else " "
            print(f"  {marker} P{p.page_num+1:2d} [{p.category:12s}] {p.text_length:5d} chars")

    # --- Domain-driven extraction via extractor registry ---
    gemini_client = get_gemini_client()
    domains = {}
    domain_validations = {}
    domain_timings = {}

    for ExtractorClass in EXTRACTOR_REGISTRY:
        extractor = ExtractorClass(
            client=gemini_client,
            model=GEMINI_MODEL,
            pdf_path=pdf_path,
            page_classification=pages,
            is_fpga=is_fpga,
        )
        domain_name = extractor.DOMAIN_NAME

        t_domain = time.time()
        selected_pages = extractor.select_pages()

        if domain_name == "thermal":
            # ThermalExtractor post-processes electrical extraction
            electrical_result = domains.get("electrical", {})
            result = extractor.extract(electrical_result)
            validation = extractor.validate(result)
        elif domain_name == "design_context":
            # DesignContextExtractor reads PDF text directly, no images needed
            result = extractor.extract({})
            validation = extractor.validate(result)
        elif selected_pages:
            images = render_pages_to_images(pdf_path, selected_pages)
            result = extractor.extract(images)
            validation = extractor.validate(result)
        else:
            result = {}
            validation = {}

        domain_timings[domain_name] = round(time.time() - t_domain, 3)
        domains[domain_name] = result
        domain_validations[domain_name] = validation

    # --- Map domain results back to original flat output structure ---

    # L1a: Electrical extraction result
    extraction = domains.get("electrical", {})
    l1_time = domain_timings.get("electrical", 0)

    if verbose:
        if "error" in extraction:
            print(f"\nL1 Vision Extraction FAILED ({l1_time:.1f}s): {extraction['error']}")
        else:
            comp = extraction.get("component", {})
            amr = extraction.get("absolute_maximum_ratings", [])
            ec = extraction.get("electrical_characteristics", [])
            pins_from_vision = extraction.get("pin_definitions", [])
            print(f"\nL1 Vision Extraction ({l1_time:.1f}s):")
            print(f"  Component: {comp.get('mpn', '?')} ({comp.get('manufacturer', '?')})")
            print(f"  Category:  {comp.get('category', '?')}")
            print(f"  Abs Max Ratings:  {len(amr)} params")
            print(f"  Elec Chars:       {len(ec)} params")
            print(f"  Pin Definitions:  {len(pins_from_vision)} pins")
            # 变体和温度覆盖统计
            devices = set(p.get('device', '') for p in ec if p.get('device'))
            temps = set(p.get('temp_range', '') for p in ec if p.get('temp_range'))
            if devices:
                print(f"  Devices:  {sorted(devices)}")
            if temps:
                print(f"  Temp ranges: {sorted(temps)}")

    # L1b: Pin extraction result
    pin_extraction = domains.get("pin", {})
    pin_validation_issues = domain_validations.get("pin", {}).get("pin_validation_issues", [])
    l1b_time = domain_timings.get("pin", 0)

    if verbose:
        if not pin_extraction or (isinstance(pin_extraction, dict) and "error" in pin_extraction):
            if pin_extraction and "error" in pin_extraction:
                print(f"\nL1b Pin Extraction FAILED: {pin_extraction.get('error')}")
            else:
                pin_page_nums = sorted(set(
                    [p.page_num for p in pin_pages] +
                    [p.page_num for p in cover_pages]
                ))
                if not pin_page_nums and not (is_fpga and fpga_supply_pages):
                    print(f"\nL1b Pin Extraction: SKIPPED (no pin/cover pages)")
        else:
            logical_pins = pin_extraction.get("logical_pins", [])
            errors = [i for i in pin_validation_issues if i["level"] == "error"]
            warnings = [i for i in pin_validation_issues if i["level"] == "warning"]

            if is_fpga:
                print(f"\nL1b FPGA Pin Extraction:")
                fpga_pin_page_nums = sorted(set(
                    [p.page_num for p in electrical_pages] +
                    [p.page_num for p in fpga_supply_pages] +
                    [p.page_num for p in cover_pages]
                ))
                print(f"  Pages: {fpga_pin_page_nums}")
                print(f"  Logical pins: {len(logical_pins)}")
                group_dist = {}
                for p in logical_pins:
                    g = p.get("pin_group", "?")
                    group_dist[g] = group_dist.get(g, 0) + 1
                print(f"  Pin group distribution: {group_dist}")
                dir_dist = {}
                for p in logical_pins:
                    d = p.get("direction", "?")
                    dir_dist[d] = dir_dist.get(d, 0) + 1
                print(f"  Direction distribution: {dir_dist}")
                sig_dist = {}
                for p in logical_pins:
                    s = p.get("signal_type", "?")
                    sig_dist[s] = sig_dist.get(s, 0) + 1
                print(f"  Signal type distribution: {sig_dist}")
            else:
                print(f"\nL1b Pin Extraction:")
                pin_page_nums_display = sorted(set(
                    [p.page_num for p in pin_pages] +
                    [p.page_num for p in cover_pages]
                ))
                print(f"  Pages: {pin_page_nums_display}")
                print(f"  Logical pins: {len(logical_pins)}")
                dir_dist = {}
                for p in logical_pins:
                    d = p.get("direction", "?")
                    dir_dist[d] = dir_dist.get(d, 0) + 1
                print(f"  Direction distribution: {dir_dist}")
                sig_dist = {}
                for p in logical_pins:
                    s = p.get("signal_type", "?")
                    sig_dist[s] = sig_dist.get(s, 0) + 1
                print(f"  Signal type distribution: {sig_dist}")
                all_pkgs = set()
                for p in logical_pins:
                    pkgs = p.get("packages", {})
                    if isinstance(pkgs, dict):
                        all_pkgs.update(pkgs.keys())
                print(f"  Packages found: {sorted(all_pkgs)}")

            print(f"  Validation: {len(errors)} errors, {len(warnings)} warnings")
            for issue in pin_validation_issues:
                icon = "❌" if issue["level"] == "error" else "⚠️"
                print(f"    {icon} {issue['message']}")

    # Transform pin_extraction → pin_index (按封装拆分、pin number 做 key)
    pin_index = {}
    if pin_extraction and "error" not in pin_extraction:
        logical_pins_list = pin_extraction.get("logical_pins", [])
        if logical_pins_list:
            pin_index = transform_pins_to_package_indexed(logical_pins_list)
            if verbose:
                print(f"\n  Pin Index (package-indexed):")
                for pkg_name, pins_map in pin_index.get("packages", {}).items():
                    print(f"    {pkg_name}: {len(pins_map)} pins")

    # L2: 校验 — use electrical domain validation
    validations = []
    electrical_val = domain_validations.get("electrical", {})
    l2_items = electrical_val.get("l2_validation", [])
    if l2_items:
        for item in l2_items:
            validations.append(ValidationResult(
                param=item["param"], rule=item["rule"],
                passed=item["passed"], message=item["message"]
            ))
    elif "error" not in extraction:
        # Fallback: run inline validation (should not happen if extractor worked)
        validations = validate_extraction(extraction)

    if verbose and validations:
        failures = [v for v in validations if not v.passed]
        print(f"\nL2 Validation:")
        print(f"  Total checks: {len(validations)}")
        print(f"  Passed: {len(validations) - len(failures)}")
        print(f"  Failed: {len(failures)}")
        for f in failures:
            print(f"  ❌ {f.param}: {f.message}")

    # L3: 交叉验证 (cross-domain, stays in pipeline)
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

    # L4: Design extraction result
    design_extraction = domains.get("design_context", {})
    if verbose and design_extraction.get("design_page_candidates"):
        print(f"\nL4 Design Extraction:")
        print(f"  Design pages: {len(design_extraction['design_page_candidates'])}")
        print(f"  External hints: {len(design_extraction['recommended_external_components'])}")
        print(f"  Layout hints: {len(design_extraction['layout_hints'])}")
        print(f"  Equation hints: {len(design_extraction['design_equation_hints'])}")

    # L5: Physics validation — use electrical domain validation
    physics_val = []
    l5_items = electrical_val.get("l5_physics", [])
    if l5_items:
        for item in l5_items:
            physics_val.append(ValidationResult(
                param=item["param"], rule=item["rule"],
                passed=item["passed"], message=item["message"]
            ))
    elif "error" not in extraction:
        # Fallback: run inline physics validation (should not happen if extractor worked)
        physics_val = validate_physics(extraction)

    if verbose and physics_val:
        physics_failures = [v for v in physics_val if not v.passed]
        print(f"\nL5 Physics Validation:")
        print(f"  Total checks: {len(physics_val)}")
        print(f"  Passed: {len(physics_val) - len(physics_failures)}")
        print(f"  Failed: {len(physics_failures)}")
        for f in physics_failures:
            print(f"  ❌ {f.param}: {f.message}")

    # Assemble output — flat structure for backward compatibility (1.1 compat)
    result = {
        "pdf_name": pdf_name,
        "model": GEMINI_MODEL,
        "mode": "vision",
        "is_fpga": is_fpga,
        "checksum": hashlib.md5(open(pdf_path, 'rb').read()).hexdigest(),
        "total_pages": len(pages),
        "vision_pages": vision_page_nums,
        "page_classification": [asdict(p) for p in pages],
        "application_pages": [p.page_num for p in application_pages],
        "extraction": extraction,
        "design_extraction": design_extraction,
        "pin_extraction": pin_extraction,
        "pin_index": pin_index,
        "pin_validation": pin_validation_issues,
        "validation": [asdict(v) for v in validations],
        "physics_validation": [asdict(v) for v in physics_val],
        "cross_validation": cross_val,
        "timing": {
            "l0_classify_s": round(l0_time, 3),
            "l1a_extract_s": round(l1_time, 3),
            "l1b_pin_s": round(l1b_time, 3),
        },
        # New: domain-structured results (for future use)
        "domains": {name: data for name, data in domains.items()},
        "domain_validations": {name: data for name, data in domain_validations.items()},
        "domain_timings": domain_timings,
    }
    return result


def run_batch(limit: int = 5):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    lock_path = OUTPUT_DIR / ".pipeline.lock"
    lock = try_exclusive_lock(
        lock_path,
        metadata=f"pid={os.getpid()} started={time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n",
    )
    if lock is None:
        print("ERROR: Another pipeline instance is already running!")
        sys.exit(1)

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
    lock.release()
    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="OpenDatasheet v0.2 vision pipeline"
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="PDF path for single-file extraction, or an integer batch limit"
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Optional output JSON path for single-file extraction"
    )
    args = parser.parse_args()

    if args.input:
        candidate = Path(args.input)
        if candidate.exists() and candidate.is_file():
            result = process_single_pdf(str(candidate))
            if args.output:
                out_path = Path(args.output)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"saved {out_path}")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        try:
            limit = int(args.input)
        except ValueError as exc:
            raise SystemExit(
                f"Unsupported input '{args.input}'. Pass a PDF path or batch limit integer."
            ) from exc
    else:
        limit = 5

    run_batch(limit=limit)


if __name__ == "__main__":
    main()
