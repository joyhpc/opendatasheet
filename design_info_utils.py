"""Helpers for extracting schematic-oriented design hints from datasheet text."""

from __future__ import annotations

import re


APPLICATION_PATTERN_STRINGS = (
    r"(?i)typical\s+application",
    r"(?i)applications?\s+information",
    r"(?i)application\s+(and\s+implementation|information|circuit|note|example|hints?)",
    r"(?i)design\s+guide",
    r"(?i)component\s+selection",
    r"(?i)inductor\s+selection",
    r"(?i)capacitor\s+selection",
    r"(?i)power\s+supply\s+recommendations?",
    r"(?i)power\s+supply\s+recomme",
    r"(?i)recommended\s+operating\s+circuit",
    r"(?i)list\s+of\s+capacitors?",
    r"(?i)list\s+of\s+inductors?",
    r"(?i)thermocouple\s+amplifier",
    r"(?i)strain\s+gage\s+circuit",
    r"(?i)function\s+generator",
    r"(?i)bandpass\s+filter",
    r"(?i)snubber\s+network",
    r"(?i)voltage\s+follower",
)

LAYOUT_PATTERN_STRINGS = (
    r"(?i)pcb\s+layout\s+(guidelines?|guide|considerations?|example|recommendations?)",
    r"(?i)printed\s+circuit\s+board\s+layout",
    r"(?i)layout\s+(guidelines?|guide|considerations?|example|recommendations?)",
    r"(?i)place.*close",
    r"(?i)minimi[sz]e.*loop",
    r"(?i)ground\s+plane",
    r"(?i)thermal\s+via",
)

POWER_SUPPLY_PATTERN_STRINGS = (
    r"(?i)power\s+supply\s+recommendations?",
    r"(?i)input\s+voltage\s+supply\s+range",
    r"(?i)designed\s+to\s+operate\s+from",
    r"(?i)operate\s+from\s+an?\s+input\s+voltage",
)

TEST_CIRCUIT_PATTERN_STRINGS = (
    r"(?i)test\s+circuit",
    r"(?i)circuit\s+implementation",
    r"(?i)system\s+examples?",
    r"(?i)schematic\s+diagram",
)

DECODER_INTERFACE_PATTERN_STRINGS = (
    r"(?i)simplified\s+application\s+circuit",
    r"(?i)block\s+diagram",
    r"(?i)functional\s+block\s+diagram",
)

HARD_EXCLUDED_PAGE_PATTERN_STRINGS = (
    r"(?i)table\s+of\s+contents",
    r"(?i)^contents\b",
    r"(?i)revision\s+history",
    r"(?i)package\s+option\s+addendum",
    r"(?i)tape\s+and\s+reel",
    r"(?i)mechanical,\s+packaging",
    r"(?i)ordering\s+information",
    r"(?i)package\s+outline",
    r"(?i)restrictions?\s+on\s+product\s+use",
)

SOFT_EXCLUDED_PAGE_PATTERN_STRINGS = (
    r"(?i)absolute\s+maximum\s+ratings?",
    r"(?i)electrical\s+characteristics?",
    r"(?i)recommended\s+operating\s+conditions?",
    r"(?i)pin\s+configurations?",
    r"(?i)pin\s+functions?",
    r"(?i)pin\s+description",
)

EXCLUDED_LAYOUT_LINE_PATTERN_STRINGS = (
    r"(?i)^thermal\s+resistance",
    r"(?i)^thermal\s+data",
    r"(?i)^absolute\s+maximum",
    r"(?i)^electrical\s+characteristics",
    r"(?i)^pin\s+configuration",
    r"(?i)response\s+time",
    r"(?i)^replaced\s",
)

COMPONENT_RULES = (
    ("input_capacitor", (r"(?i)input\s+capacitor", r"(?i)\bCIN\b")),
    ("output_capacitor", (r"(?i)output\s+capacitor", r"(?i)\bCOUT\b", r"(?i)\bCL\b")),
    ("inductor", (r"(?i)inductor\s+selection", r"(?i)\binductor\b", r"(?i)\bL1\b")),
    ("poc_inductor", (r"(?i)power\s+over\s+coax", r"(?i)\bpoc\b.*\binductor\b", r"(?i)smallest\s+valued\s+inductor")),
    ("feedback_divider", (r"(?i)feedback.*divider", r"(?i)connected\s+from\s+OUT\s+to\s+FB", r"(?i)\bR1\b.*\bR2\b")),
    ("line_fault_resistor", (r"(?i)line-?fault.*resistor", r"(?i)\bREXT[12]?\b")),
    ("termination_resistor", (r"(?i)termination\s+resistor", r"(?i)\bRTERM\b", r"(?i)50Ω\s+termination")),
    ("link_isolation_capacitor", (r"(?i)link\s+isolation(?:\s+capacitors?)?", r"(?i)dc\s+blocking(?:\s+capacitors?)?", r"(?i)\bCLINK\b", r"(?i)ac\s+coupling\s+capacitors?")),
    ("bootstrap_capacitor", (r"(?i)bootstrap\s+capacitor", r"(?i)\bBOOT\b", r"(?i)\bBST\b")),
    ("soft_start_capacitor", (r"(?i)soft-?start", r"(?i)\bSS/TR\b")),
    ("pullup_resistor", (r"(?i)pull-up", r"(?i)open\s+drain", r"(?i)open\s+collector")),
    ("current_limit_resistor", (r"(?i)\bR\(?ILIM\)?\b", r"(?i)\bRILIM\b", r"(?i)ilim\s+resistor")),
    ("dvdt_capacitor", (r"(?i)\bC\(?dVdT\)?\b", r"(?i)\bCdVdT\b", r"(?i)ramp-?up\s+capacitor")),
    ("uvlo_divider", (r"(?i)\bUVLO\b.*\bR\d+\b", r"(?i)resistors?.*\bUVLO\b", r"(?i)uvlo.*divider")),
    ("ovp_divider", (r"(?i)\bOVP\b.*\bR\d+\b", r"(?i)resistors?.*\bOVP\b", r"(?i)ovp.*divider")),
    ("gain_resistor", (r"(?i)\bRF\b", r"(?i)\bRIN\b", r"(?i)gain.*resistor", r"(?i)large\s+signal\s+gain")),
    ("sense_resistor", (r"(?i)\bRSENSE\b", r"(?i)sense\s+resistor")),
    ("snubber_capacitor", (r"(?i)snubber\s+network", r"(?i)\bCx\b")),
    ("snubber_resistor", (r"(?i)snubber\s+network", r"(?i)\bRx\b")),
    ("filter_network", (r"(?i)bandpass\s+filter", r"(?i)notch\s+output", r"(?i)function\s+generator", r"(?i)voltage\s+follower")),
)

EQUATION_SYMBOL_HINTS = (
    "vout",
    "vin",
    "iout",
    "fsw",
    "f_sw",
    "delta",
    "r1",
    "r2",
    "rt",
    "fb",
    "ss",
    "uvlo",
    "av",
    "gain",
    "ilim",
    "pd",
)

LAYOUT_LINE_KEYWORDS = (
    "as close as possible",
    "close to the",
    "ground plane",
    "thermal via",
    "wide and short",
    "short and wide",
    "routing",
    "return path",
    "kelvin",
    "guard ring",
    "analog ground",
    "power ground",
    "pgnd",
    "agnd",
    "loop area",
    "minimize the loop",
    "powerpad",
)

APPLICATION_PATTERNS = tuple(re.compile(pattern) for pattern in APPLICATION_PATTERN_STRINGS)
LAYOUT_PATTERNS = tuple(re.compile(pattern) for pattern in LAYOUT_PATTERN_STRINGS)
POWER_SUPPLY_PATTERNS = tuple(re.compile(pattern) for pattern in POWER_SUPPLY_PATTERN_STRINGS)
TEST_CIRCUIT_PATTERNS = tuple(re.compile(pattern) for pattern in TEST_CIRCUIT_PATTERN_STRINGS)
DECODER_INTERFACE_PATTERNS = tuple(re.compile(pattern) for pattern in DECODER_INTERFACE_PATTERN_STRINGS)
HARD_EXCLUDED_PAGE_PATTERNS = tuple(re.compile(pattern) for pattern in HARD_EXCLUDED_PAGE_PATTERN_STRINGS)
SOFT_EXCLUDED_PAGE_PATTERNS = tuple(re.compile(pattern) for pattern in SOFT_EXCLUDED_PAGE_PATTERN_STRINGS)
EXCLUDED_LAYOUT_LINE_PATTERNS = tuple(re.compile(pattern) for pattern in EXCLUDED_LAYOUT_LINE_PATTERN_STRINGS)

VALUE_WITH_UNIT_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>pF|nF|uF|µF|μF|mF|Ω|kΩ|MΩ|uH|µH|μH|mH|A|mA|V|kHz|MHz)",
    re.IGNORECASE,
)
PASSIVE_VALUE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:pF|nF|uF|µF|μF|mF|Ω|kΩ|MΩ|uH|µH|μH|mH)\b",
    re.IGNORECASE,
)
DESIGN_RANGE_RE = re.compile(
    r"\b(?P<name>VIN|VOUT|IOUT|FSW|FOSC|VFB|UVLO|ILIM)\s*=\s*(?P<min>\d+(?:\.\d+)?)\s*(?P<unit1>pF|nF|uF|µF|μF|mF|Ω|kΩ|MΩ|uH|µH|μH|mH|A|mA|V|kHz|MHz)?\s*(?:to|TO|~|～|–|-)\s*(?P<max>\d+(?:\.\d+)?)\s*(?P<unit2>pF|nF|uF|µF|μF|mF|Ω|kΩ|MΩ|uH|µH|μH|mH|A|mA|V|kHz|MHz)?",
    re.IGNORECASE,
)
EQUATION_RE = re.compile(r"([A-Za-zΔ][A-Za-z0-9_(),\-/ ]{0,24})\s*=\s*([^\n]{4,120})")
VARIABLE_TOKEN_RE = re.compile(r"\b[A-Za-zΔ][A-Za-z0-9_]*\b")

def dedupe_preserve_order(items: list[dict | str]) -> list[dict | str]:
    seen = set()
    result = []
    for item in items:
        key = repr(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _normalized_head(text: str, limit: int = 2000) -> str:
    return " ".join(text.split())[:limit]


def _has_strong_design_heading(text: str) -> bool:
    head = _normalized_head(text, 1600)
    return any(pattern.search(head) for pattern in APPLICATION_PATTERNS + LAYOUT_PATTERNS + POWER_SUPPLY_PATTERNS)


def _is_hard_excluded_page(text: str) -> bool:
    head = _normalized_head(text)
    return any(pattern.search(head) for pattern in HARD_EXCLUDED_PAGE_PATTERNS)


def _is_soft_excluded_page(text: str) -> bool:
    head = _normalized_head(text)
    if not any(pattern.search(head) for pattern in SOFT_EXCLUDED_PAGE_PATTERNS):
        return False
    return not _has_strong_design_heading(head)


def _looks_like_overview_page(text: str) -> bool:
    head = _normalized_head(text, 2200).lower()
    if "typical application" in head or "application information" in head or "power supply recommendations" in head:
        return False
    return "features" in head and "general description" in head


def _looks_like_schematic_example_page(text: str) -> bool:
    head = _normalized_head(text, 2600)
    if not any(pattern.search(head) for pattern in TEST_CIRCUIT_PATTERNS):
        return False
    upper_head = head.upper()
    has_component_refs = any(
        re.search(pattern, upper_head)
        for pattern in (
            r"\bC\d+\b",
            r"\bR\d+\b",
            r"\bS\d+\b",
            r"\bRILIM\b",
            r"\bCDVDT\b",
            r"\bCIN\b",
            r"\bCOUT\b",
            r"\bRF\b",
            r"\bRIN\b",
            r"\bRSENSE\b",
        )
    )
    has_values = bool(VALUE_WITH_UNIT_RE.search(head))
    has_io_context = sum(token in upper_head for token in ("VIN", "VOUT", "IN", "OUT", "GND", "VDD", "VSS", "EN")) >= 3
    return has_component_refs and (has_values or has_io_context)


def _looks_like_decoder_interface_page(text: str) -> bool:
    head = _normalized_head(text, 2600)
    if not any(pattern.search(head) for pattern in DECODER_INTERFACE_PATTERNS):
        return False
    lower_head = head.lower()
    keyword_hits = sum(
        token in lower_head
        for token in (
            "decoder",
            "deserializer",
            "serializer",
            "gmsl",
            "mipi",
            "csi",
            "video",
            "cvbs",
            "hd-tvi",
        )
    )
    io_hits = sum(token in head.upper() for token in ("VIN", "SIO", "CSI", "MIPI", "SCL", "SDA", "CK", "DA", "DB"))
    return keyword_hits >= 2 and io_hits >= 2


def _looks_like_schematic_figure(text: str) -> bool:
    head = _normalized_head(text, 2600)
    upper_head = head.upper()
    ref_hits = sum(
        bool(re.search(pattern, upper_head))
        for pattern in (
            r"\bC\d+\b",
            r"\bR\d+\b",
            r"\bL\d+\b",
            r"\bS\d+\b",
            r"\bRILIM\b",
            r"\bCDVDT\b",
            r"\bCIN\b",
            r"\bCOUT\b",
            r"\bRF\b",
            r"\bRIN\b",
            r"\bRSENSE\b",
            r"\bUVLO\b",
            r"\bOVP\b",
        )
    )
    has_values = bool(VALUE_WITH_UNIT_RE.search(head))
    io_hits = sum(token in upper_head for token in ("VIN", "VOUT", "IN", "OUT", "GND", "VDD", "VSS", "FLT", "ILIM"))
    has_figure_context = "FIGURE" in upper_head or "CIRCUIT" in upper_head or "OPTIONAL COMPONENTS" in upper_head
    return ref_hits >= 2 and has_figure_context and (has_values or io_hits >= 3)

def detect_design_page_kind(text: str) -> str | None:
    if not text:
        return None
    head = _normalized_head(text, 1200)
    if _is_hard_excluded_page(head):
        return None
    if _is_soft_excluded_page(head):
        return None
    if _looks_like_overview_page(head):
        return None
    if any(pattern.search(head) for pattern in APPLICATION_PATTERNS):
        return "application"
    if any(pattern.search(head) for pattern in POWER_SUPPLY_PATTERNS):
        return "power_supply"
    if any(pattern.search(head) for pattern in LAYOUT_PATTERNS):
        return "layout"
    if _looks_like_decoder_interface_page(text):
        return "application"
    if _looks_like_schematic_example_page(text):
        return "application"
    if _looks_like_schematic_figure(text):
        return "application"
    upper_text = text.upper()
    if (
        all(token in upper_text for token in ("VIN", "VOUT"))
        and re.search(r"\bC\d+\b", upper_text)
        and re.search(r"\bR\d+\b", upper_text)
        and ("FIGURE" in upper_text or "APPLICATION" in upper_text)
    ):
        return "application"
    return None


def _interesting_lines(text: str) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if len(line) >= 8:
            lines.append(line)
    return lines


def _component_context_lines(text: str) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if line and any(ch.isalnum() for ch in line):
            lines.append(line)
    return lines


def _line_context_window(lines: list[str], index: int, span: int = 8) -> str:
    start = max(0, index - 4)
    end = min(len(lines), index + span)
    return " ".join(lines[start:end])


def _passive_values_from_text(text: str) -> list[str]:
    return dedupe_preserve_order([_normalize_passive_value(value) for value in PASSIVE_VALUE_RE.findall(text)])


def _extract_named_value_hint(line: str, names: tuple[str, ...], unit_kind: str) -> str | None:
    lowered = line.lower()
    for name in names:
        index = lowered.find(name.lower())
        if index < 0:
            continue
        window = line[index:index + 48]
        for value in PASSIVE_VALUE_RE.findall(window):
            value_lower = value.lower()
            if unit_kind == "capacitor" and any(unit in value_lower for unit in ("pf", "nf", "uf", "µf", "μf", "mf")):
                return value
            if unit_kind == "resistor" and ("ω" in value_lower or "ohm" in value_lower):
                return value
            if unit_kind == "inductor" and any(unit in value_lower for unit in ("uh", "µh", "μh", "mh")):
                return value
    return None


def _normalize_passive_value(value: str) -> str:
    value = " ".join(value.split())
    value = re.sub(r"\s+(?=(?:kΩ|MΩ)\b)", "", value)
    value = re.sub(r"(?<=\d)(?=(?:pF|nF|uF|µF|μF|mF|Ω|uH|µH|μH|mH)\b)", " ", value)
    return value


def _extract_role_value_hint_from_page(role: str, page_text: str) -> str | None:
    if not page_text:
        return None
    role_tokens = {
        "link_isolation_capacitor": ["clink", "link isolation", "dc blocking"],
        "termination_resistor": ["rterm", "termination"],
        "line_fault_resistor": ["rext1", "rext2"],
        "poc_inductor": ["poc", "power over coax", "inductor"],
    }
    unit_kind = {
        "link_isolation_capacitor": "capacitor",
        "termination_resistor": "resistor",
        "line_fault_resistor": "resistor",
        "poc_inductor": "inductor",
    }.get(role)
    if not unit_kind or role not in role_tokens:
        return None

    lower = page_text.lower()
    if role == "link_isolation_capacitor" and "gmsl2 mode" in lower and "0.1" in page_text and any(unit in page_text for unit in ("μF", "µF", "uF")):
        unit = "μF" if "μF" in page_text else "µF" if "µF" in page_text else "uF"
        return _normalize_passive_value(f"0.1 {unit}")
    for token in role_tokens[role]:
        start = 0
        while True:
            index = lower.find(token, start)
            if index < 0:
                break
            window = page_text[max(0, index - 120): index + 220]
            direct_values = _passive_values_from_text(window)
            if unit_kind == "capacitor":
                preferred = []
                for value in direct_values:
                    if any(unit in value.lower() for unit in ("pf", "nf", "uf", "µf", "μf", "mf")):
                        preferred.append(_normalize_passive_value(value))
                if role == "link_isolation_capacitor":
                    for number in (("0.1", "μF"), ("0.1", "µF"), ("0.22", "μF"), ("0.22", "µF"), ("0.047", "μF"), ("0.047", "µF")):
                        if number[0] in window and number[1] in window:
                            return _normalize_passive_value(f"{number[0]} {number[1]}")
                    for candidate in preferred:
                        if candidate.startswith("0.1 "):
                            return candidate
                if preferred:
                    return preferred[0]
                for number in (("0.1", "μF"), ("0.22", "μF"), ("0.047", "μF"), ("0.1", "µF"), ("0.22", "µF"), ("0.047", "µF")):
                    if number[0] in window and number[1] in window:
                        return _normalize_passive_value(f"{number[0]} {number[1]}")
            elif unit_kind == "resistor":
                preferred = []
                for value in direct_values:
                    if "ω" in value.lower() or "ohm" in value.lower():
                        preferred.append(_normalize_passive_value(value))
                if role == "line_fault_resistor":
                    for candidate in preferred:
                        if candidate.startswith("42.2kΩ") or candidate.startswith("48.7kΩ"):
                            return candidate
                if preferred:
                    return preferred[0]
                ordered_pairs = (("42.2", "kΩ"), ("48.7", "kΩ"), ("49.9", "Ω")) if role == "line_fault_resistor" else (("49.9", "Ω"), ("48.7", "kΩ"), ("42.2", "kΩ"))
                for number, unit in ordered_pairs:
                    if number in window and unit in window:
                        return _normalize_passive_value(f"{number} {unit}")
            elif unit_kind == "inductor":
                for value in direct_values:
                    if any(unit in value.lower() for unit in ("uh", "µh", "μh", "mh")):
                        return _normalize_passive_value(value)
            start = index + len(token)
    return None


def _select_role_value_hint(role: str, value_hints: list[str], line: str) -> str | None:
    if not value_hints:
        return None
    role_lower = role.lower()
    role_specific = {
        "input_capacitor": (("cin",), "capacitor"),
        "output_capacitor": (("cout", "cl"), "capacitor"),
        "dvdt_capacitor": (("cdvdt", "c(dvdt)", "dvdt"), "capacitor"),
        "soft_start_capacitor": (("ss/tr", "soft-start", "soft start"), "capacitor"),
        "bootstrap_capacitor": (("boot", "bst", "bootstrap"), "capacitor"),
        "current_limit_resistor": (("rilim", "r(ilim)", "ilim"), "resistor"),
        "pullup_resistor": (("pull-up", "pullup", "open drain", "open collector"), "resistor"),
        "uvlo_divider": (("uvlo",), "resistor"),
        "ovp_divider": (("ovp",), "resistor"),
        "gain_resistor": (("rf", "rin", "gain"), "resistor"),
        "sense_resistor": (("rsense", "sense resistor"), "resistor"),
        "snubber_capacitor": (("cx", "snubber"), "capacitor"),
        "snubber_resistor": (("rx", "snubber"), "resistor"),
        "inductor": (("inductor", "l1"), "inductor"),
        "poc_inductor": (("poc", "inductor"), "inductor"),
        "line_fault_resistor": (("rext1", "rext2", "line-fault", "line fault"), "resistor"),
        "termination_resistor": (("rterm", "termination"), "resistor"),
        "link_isolation_capacitor": (("clink", "dc blocking", "link isolation", "ac coupling"), "capacitor"),
    }
    if role in role_specific:
        tokens, unit_kind = role_specific[role]
        matched = _extract_named_value_hint(line, tokens, unit_kind)
        if matched:
            return _normalize_passive_value(matched)
    if "capacitor" in role_lower:
        for value in value_hints:
            if any(unit in value.lower() for unit in ("pf", "nf", "uf", "µf", "μf", "mf")):
                return value
    if "resistor" in role_lower or "divider" in role_lower:
        for value in value_hints:
            if "ω" in value.lower() or "ohm" in value.lower():
                return value
    if "inductor" in role_lower:
        for value in value_hints:
            if any(unit in value.lower() for unit in ("uh", "µh", "μh", "mh")):
                return value
    return None


def _should_skip_component_line(line: str) -> bool:
    lowered = line.lower()
    return any(
        phrase in lowered
        for phrase in (
            "internally connected",
            "internal on the",
            "internal soft-start",
            "is internal",
            "not internally connected",
            "table of contents",
            "revision history",
            "packet spacing",
            "line crc error",
            "cfg0 input map",
            "device address",
            "i2csel",
            "mapped configuration",
        )
    )


def _should_skip_role_on_line(role: str, line: str, context_text: str, page: dict) -> bool:
    line_lowered = line.lower()
    lowered = context_text.lower()
    page_text = (page.get("text") or "").lower()
    decoder_context = any(token in page_text for token in ("decoder", "deserializer", "serializer", "gmsl", "mipi", "csi"))

    if role == "feedback_divider" and decoder_context:
        return True
    if role == "inductor" and decoder_context:
        return True
    if role == "poc_inductor":
        if "packet spacing" in lowered:
            return True
        if not any(token in line_lowered for token in ("poc", "power over coax", "inductor")):
            return True
    if role == "line_fault_resistor":
        if "rext" not in lowered:
            return True
        if not any(token in line_lowered for token in ("line-fault", "rext1", "rext2", "rext")):
            return True
    if role == "termination_resistor":
        if not any(token in line_lowered for token in ("termination", "rterm")):
            return True
    if role == "link_isolation_capacitor":
        if not any(token in line_lowered for token in ("clink", "dc blocking", "link isolation", "ac coupling")):
            return True
    return False


def _extract_component_hints(text_pages: list[dict], limit: int = 12) -> list[dict]:
    results = []
    role_counts: dict[str, int] = {}
    for page in text_pages:
        lines = _component_context_lines(page.get("text", ""))
        for index, line in enumerate(lines):
            if _should_skip_component_line(line):
                continue
            context_text = _line_context_window(lines, index)
            value_hints = _passive_values_from_text(context_text)
            matched_any = False
            for role, patterns in COMPONENT_RULES:
                if not any(re.search(pattern, line) or re.search(pattern, context_text) for pattern in patterns):
                    continue
                if _should_skip_role_on_line(role, line, context_text, page):
                    continue
                if role_counts.get(role, 0) >= 2:
                    continue
                matched_any = True
                role_counts[role] = role_counts.get(role, 0) + 1
                value_hint = _select_role_value_hint(role, value_hints, context_text)
                if value_hint is None:
                    value_hint = _extract_role_value_hint_from_page(role, page.get("text", ""))
                results.append(
                    {
                        "role": role,
                        "source_page": page.get("page_num"),
                        "value_hint": value_hint,
                        "value_hints": value_hints,
                        "snippet": line[:220],
                    }
                )
                if len(results) >= limit:
                    return dedupe_preserve_order(results)
            if matched_any and len(results) >= limit:
                return dedupe_preserve_order(results)
    return dedupe_preserve_order(results)


def _looks_like_useful_equation(lhs: str, rhs: str) -> bool:
    lhs_clean = lhs.strip()
    rhs_clean = rhs.strip()
    lowered = f"{lhs_clean} = {rhs_clean}".lower()

    if any(token in lhs_clean for token in (",", ";", ":")):
        return False
    if " and " in lhs_clean.lower() or len(lhs_clean.split()) > 3:
        return False
    if re.search(r"\bif\b", lhs_clean, re.IGNORECASE):
        return False
    if " to " in rhs_clean.lower() and VALUE_WITH_UNIT_RE.search(rhs_clean):
        return False
    if any(
        phrase in lowered
        for phrase in (
            "unless otherwise specified",
            "typical values are",
            "this sets",
            "fully enhanced",
            "total power dissipation",
            "maximum current-limit threshold",
            "minimum resulting current-limit threshold",
            "transient response",
            "load current",
            "div",
            "waveform",
        )
    ):
        return False

    if "=" in rhs_clean:
        return False
    if "," in rhs_clean and not any(token in rhs_clean for token in ("+", "-", "*", "/", "×", "(", ")")):
        return False

    if any(token in rhs_clean for token in ("+", "-", "*", "/", "×", "(", ")")):
        return True

    rhs_vars = VARIABLE_TOKEN_RE.findall(rhs_clean)
    lhs_vars = VARIABLE_TOKEN_RE.findall(lhs_clean)
    if len(rhs_vars) >= 2 and len(lhs_vars) >= 1:
        return True

    unit_match = VALUE_WITH_UNIT_RE.search(rhs_clean)
    return bool(unit_match and len(lhs_vars) == 1 and lhs_clean.upper() in {"RILIM", "ILIM", "VOUT", "AV"})


def _extract_equation_hints(text_pages: list[dict], limit: int = 10) -> list[dict]:
    results = []
    for page in text_pages:
        for line in _interesting_lines(page.get("text", "")):
            lowered = line.lower()
            if "=" not in line or not any(symbol in lowered for symbol in EQUATION_SYMBOL_HINTS):
                continue
            match = EQUATION_RE.search(line)
            if not match:
                continue
            lhs = match.group(1).strip()
            rhs = match.group(2).strip()
            if not _looks_like_useful_equation(lhs, rhs):
                continue
            results.append(
                {
                    "equation": f"{lhs} = {rhs}",
                    "source_page": page.get("page_num"),
                }
            )
            if len(results) >= limit:
                return dedupe_preserve_order(results)
    return dedupe_preserve_order(results)


def _extract_layout_hints(text_pages: list[dict], limit: int = 10) -> list[dict]:
    results = []
    for page in text_pages:
        for line in _interesting_lines(page.get("text", "")):
            lowered = line.lower()
            if any(pattern.search(line) for pattern in EXCLUDED_LAYOUT_LINE_PATTERNS):
                continue
            if not any(keyword in lowered for keyword in LAYOUT_LINE_KEYWORDS):
                continue
            results.append(
                {
                    "hint": line[:220],
                    "source_page": page.get("page_num"),
                }
            )
            if len(results) >= limit:
                return dedupe_preserve_order(results)
    return dedupe_preserve_order(results)


def _extract_supply_hints(text_pages: list[dict], limit: int = 8) -> list[dict]:
    results = []
    for page in text_pages:
        for line in _interesting_lines(page.get("text", "")):
            lowered = line.lower()
            if any(token in lowered for token in ("absolute maximum", "electrical characteristics", "ordering information")):
                continue
            if not any(keyword in lowered for keyword in ("input voltage", "operate from", "supply", "uvlo", "power supply")):
                continue
            results.append(
                {
                    "hint": line[:220],
                    "source_page": page.get("page_num"),
                }
            )
            if len(results) >= limit:
                return dedupe_preserve_order(results)
    return dedupe_preserve_order(results)


def _extract_topology_hints(text_pages: list[dict], limit: int = 8) -> list[dict]:
    results = []
    for page in text_pages:
        for line in _interesting_lines(page.get("text", "")):
            lowered = line.lower()
            if not any(keyword in lowered for keyword in ("step-down", "step up", "buck", "boost", "ldo", "application", "topology", "linear regulator")):
                continue
            results.append(
                {
                    "hint": line[:220],
                    "source_page": page.get("page_num"),
                }
            )
            if len(results) >= limit:
                return dedupe_preserve_order(results)
    return dedupe_preserve_order(results)


def _extract_component_value_hints(text_pages: list[dict], limit: int = 8) -> list[dict]:
    results = []
    seen_signatures: set[tuple[int | None, tuple[str, ...]]] = set()
    for page in text_pages:
        if page.get("kind") not in {"application", "power_supply", "layout"}:
            continue
        lines = _component_context_lines(page.get("text", ""))
        for index, line in enumerate(lines):
            lowered = line.lower()
            if _should_skip_component_line(line):
                continue
            context_text = _line_context_window(lines, index)
            context_lowered = context_text.lower()
            values = _passive_values_from_text(context_text)
            matched_values = []
            for role, patterns in COMPONENT_RULES:
                if not any(re.search(pattern, line) or re.search(pattern, context_text) for pattern in patterns):
                    continue
                if _should_skip_role_on_line(role, line, context_text, page):
                    continue
                value_hint = _select_role_value_hint(role, values, context_text)
                if value_hint is None:
                    value_hint = _extract_role_value_hint_from_page(role, page.get("text", ""))
                if value_hint:
                    matched_values.append(_normalize_passive_value(value_hint))
            values = dedupe_preserve_order(matched_values + values)
            if not values:
                continue
            if len(values) < 2 and not any(token in context_lowered for token in ("inductor", "capacitor", "feedback", "pull-up", "pullup", "bootstrap", "soft-start", "ss/tr", "r1", "r2", "cin", "cout", "l1", "clink", "rext", "rterm", "termination", "line-fault", "line fault", "poc", "ac coupling", "dc blocking", "link isolation")):
                continue
            signature = (page.get("page_num"), tuple(values[:6]))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            results.append(
                {
                    "values": values[:6],
                    "source_page": page.get("page_num"),
                    "snippet": context_text[:220],
                }
            )
            if len(results) >= limit:
                return dedupe_preserve_order(results)
    return dedupe_preserve_order(results)


def _extract_design_range_hints(text_pages: list[dict], limit: int = 8) -> list[dict]:
    results = []
    for page in text_pages:
        for line in _interesting_lines(page.get("text", "")):
            lowered = line.lower()
            if any(token in lowered for token in ("absolute maximum", "electrical characteristics", "test condition", "revision history")):
                continue
            for match in DESIGN_RANGE_RE.finditer(line):
                unit = match.group("unit2") or match.group("unit1")
                if not unit:
                    continue
                name = match.group("name").upper()
                results.append(
                    {
                        "name": name,
                        "min": float(match.group("min")),
                        "max": float(match.group("max")),
                        "unit": unit,
                        "source_page": page.get("page_num"),
                        "snippet": line[:220],
                    }
                )
                if len(results) >= limit:
                    return dedupe_preserve_order(results)
    return dedupe_preserve_order(results)


def extract_design_context(text_pages: list[dict]) -> dict:
    normalized_pages = []
    for page in text_pages:
        text = page.get("text") or ""
        kind = page.get("kind") or detect_design_page_kind(text)
        if not kind:
            continue
        normalized_pages.append(
            {
                "page_num": page.get("page_num"),
                "kind": kind,
                "text": text,
                "preview": " ".join(text.split())[:220],
            }
        )

    if not normalized_pages:
        return {
            "design_page_candidates": [],
            "recommended_external_components": [],
            "component_value_hints": [],
            "design_range_hints": [],
            "design_equation_hints": [],
            "layout_hints": [],
            "supply_recommendations": [],
            "topology_hints": [],
        }

    layout_hints = _extract_layout_hints(normalized_pages)
    if not layout_hints:
        layout_pages = [page for page in normalized_pages if page["kind"] == "layout"]
        layout_hints = [
            {"hint": page["preview"], "source_page": page["page_num"]}
            for page in layout_pages[:3]
        ]

    return {
        "design_page_candidates": [
            {
                "page_num": page["page_num"],
                "kind": page["kind"],
                "preview": page["preview"],
            }
            for page in normalized_pages
        ],
        "recommended_external_components": _extract_component_hints(normalized_pages),
        "component_value_hints": _extract_component_value_hints(normalized_pages),
        "design_range_hints": _extract_design_range_hints(normalized_pages),
        "design_equation_hints": _extract_equation_hints(normalized_pages),
        "layout_hints": layout_hints,
        "supply_recommendations": _extract_supply_hints(normalized_pages),
        "topology_hints": _extract_topology_hints(normalized_pages),
    }
