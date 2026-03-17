#!/usr/bin/env python3
"""Design-guide domain helpers for sch-review export.

Keeps vendor/family document parsing and domain normalization outside
``export_for_sch_review.py`` so the exporter only orchestrates loading
and merging.
"""

from __future__ import annotations

import re
import json
from pathlib import Path


LATEST_GOWIN_FAMILY_GUIDES = {
    "GW5AR": {
        "document_id": "UG1117",
        "version": "1.1E",
        "released_on": "2025-08-08",
        "title": "GW5AR FPGA Schematic Manual",
        "url": "https://www.gowinsemi.com/en/support/database/1823/",
        "device_family": "GW5AR",
    },
    "GW5AS": {
        "document_id": "UG1116",
        "version": "1.1E",
        "released_on": "2025-08-08",
        "title": "GW5AS FPGA Schematic Manual",
        "url": "https://www.gowinsemi.com/en/support/database/1828/",
        "device_family": "GW5AS",
    },
}


LATEST_GOWIN_PACKAGE_GUIDES = {
    "GW5AT-15": {
        "document_id": "UG1224",
        "version": "1.2E",
        "released_on": "2025-06-27",
        "title": "GW5AT-15 Device Pinout Guide",
        "url": "https://www.gowinsemi.com/en/support/database/1793/",
    },
    "GW5AT-60": {
        "document_id": "UG1222",
        "version": "1.3.3E",
        "released_on": "2025-12-19",
        "title": "GW5AT-60 Device Pinout Guide",
        "url": "https://www.gowinsemi.com/en/support/database/1866/",
    },
    "GW5AT-138": {
        "document_id": "UG982",
        "version": "1.5.4E",
        "released_on": "2025-06-27",
        "title": "GW5AT-138 Device Pinout Guide",
        "url": "https://www.gowinsemi.com/en/support/database/1880/",
    },
    "GW5AR-25": {
        "document_id": "UG1110",
        "version": "1.1.1E",
        "released_on": "2025-06-27",
        "title": "GW5AR-25 Device Pinout Guide",
        "url": "https://www.gowinsemi.com/en/support/database/1840/",
    },
    "GW5AS-25": {
        "document_id": "UG1115",
        "version": "1.1.4E",
        "released_on": "2026-01-16",
        "title": "GW5AS-25 Device Pinout Guide",
        "url": "https://www.gowinsemi.com/en/support/database/1938/",
    },
}


GOWIN_PRODUCT_SOURCES = {
    "GW5AT": {
        "document_id": "product_detail_72",
        "version": None,
        "released_on": None,
        "title": "Gowin Arora V FPGA Product Detail",
        "url": "https://www.gowinsemi.com/en/product/detail/72/",
    },
    "GW5AR": {
        "document_id": "product_detail_79",
        "version": None,
        "released_on": None,
        "title": "Gowin Arora-R FPGA Product Detail",
        "url": "https://www.gowinsemi.com/en/product/detail/79/",
    },
    "GW5AS": {
        "document_id": "product_detail_78",
        "version": None,
        "released_on": None,
        "title": "Gowin Arora-S FPGA Product Detail",
        "url": "https://www.gowinsemi.com/en/product/detail/78/",
    },
}


GOWIN_GUIDE_SOURCE_CANDIDATES = {
    "GW5AT": [
        "data/extracted_v2/fpga/gowin_gw5at_design_guide.json",
        "data/extracted_v2/fpga/gowin_gw5at_schematic_guide.md",
    ],
    "GW5AR": [
        "data/extracted_v2/fpga/gowin_gw5ar_design_guide.json",
        "data/extracted_v2/fpga/gowin_gw5ar_schematic_guide.md",
    ],
    "GW5AS": [
        "data/extracted_v2/fpga/gowin_gw5as_design_guide.json",
        "data/extracted_v2/fpga/gowin_gw5as_schematic_guide.md",
    ],
}


PACKAGE_PROFILE_NOTES = {
    ("GW5AT-15", "CS130"): [
        "Package pinout bonds VCCX, VCCLDO, and VDDXM together; one bonded pin also carries VDD12M.",
    ],
    ("GW5AT-15", "CS130F"): [
        "Latest package pinout splits the auxiliary rails into VCCX/VDDXM and VCCLDO/VDD12M bonded groups.",
        "Use the package pinout as the binding source when it is more specific than the family-level merge summary.",
    ],
    ("GW5AT-15", "MG132"): [
        "MG132 keeps VCCX and VCCLDO as separate package rails; only the MIPI auxiliary rail is bonded with VDDAM.",
    ],
    ("GW5AR-25", "UG256P"): [
        "Use the package pinout as the binding source for bonded rails such as VCC/VCCC and M0_VDDX/VCC_REG/VCCIO10/VCCX.",
    ],
    ("GW5AS-25", "UG256"): [
        "Use the package pinout as the binding source for bonded VCCIO bank groups and M0_VDDX/VCCX auxiliary rails.",
    ],
}


_RAMP_RE = re.compile(
    r"-\s*([A-Z0-9\[\]_*]+)\s*上升斜率:\s*([0-9.]+)\s*~\s*([0-9.]+)\s*([A-Za-z/μµ]+)"
)
_RIPPLE_RE = re.compile(r"-\s*([A-Z0-9\[\]_*]+):\s*≤\s*([0-9.]+)%")
_SOURCE_RE = re.compile(r"^#\s*Source:\s*([^\n]+)$", re.MULTILINE)
_SECTION_RE = re.compile(r"^##\s+(.+?)\n(.*?)(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL)
_SUBSECTION_RE = re.compile(r"^###\s+(.+?)\n(.*?)(?=^###\s+|\Z)", re.MULTILINE | re.DOTALL)
_LOGICAL_POWER_PATTERNS = [
    (re.compile(r"M0_VDD_12(?![A-Z0-9])"), "M0_VDD_12"),
    (re.compile(r"M0_VDDA(?![A-Z0-9])"), "M0_VDDA"),
    (re.compile(r"M0_VDDD(?![A-Z0-9])"), "M0_VDDD"),
    (re.compile(r"M0_VDDX(?![A-Z0-9])"), "M0_VDDX"),
    (re.compile(r"VCC_REG(?![A-Z0-9])"), "VCC_REG"),
    (re.compile(r"VCC_EXT(?![A-Z0-9])"), "VCC_EXT"),
    (re.compile(r"VCCLDO(?![A-Z0-9])"), "VCCLDO"),
    (re.compile(r"VCCIO\d+"), "VCCIO"),
    (re.compile(r"VCCX(?![A-Z0-9])"), "VCCX"),
    (re.compile(r"VCCC(?![A-Z0-9])"), "VCCC"),
    (re.compile(r"VDDAQ(?![A-Z0-9])"), "VDDAQ"),
    (re.compile(r"VDDDQ(?![A-Z0-9])"), "VDDDQ"),
    (re.compile(r"VDDHAQ(?![A-Z0-9])"), "VDDHAQ"),
    (re.compile(r"VDDTQ(?![A-Z0-9])"), "VDDTQ"),
    (re.compile(r"VDDA_MIPI(?![A-Z0-9])"), "VDDAM"),
    (re.compile(r"VDDD_MIPI(?![A-Z0-9])"), "VDDDM"),
    (re.compile(r"VDDX_MIPI(?![A-Z0-9])"), "VDDXM"),
    (re.compile(r"VDD12_MIPI(?![A-Z0-9])"), "VDD12M"),
    (re.compile(r"VDDAM(?![A-Z0-9])"), "VDDAM"),
    (re.compile(r"VDDDM(?![A-Z0-9])"), "VDDDM"),
    (re.compile(r"VDDXM(?![A-Z0-9])"), "VDDXM"),
    (re.compile(r"VDD12M(?![A-Z0-9])"), "VDD12M"),
    (re.compile(r"VEFUSE(?![A-Z0-9])"), "VEFUSE"),
    (re.compile(r"VQPS(?:\[\d+\])?"), "VQPS"),
    (re.compile(r"(?<![A-Z0-9_])VCC(?![A-Z0-9_])"), "VCC"),
]


def _repo_relative_path(path: Path) -> str:
    repo_root = Path(__file__).resolve().parent.parent
    try:
        return str(path.resolve().relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        return str(path)


def _gowin_family_key(device: str | None) -> str | None:
    upper = (device or "").upper()
    if upper.startswith(("GW5AT-", "GW5AST-")) or upper in {"GW5AT", "GW5AST"}:
        return "GW5AT"
    if upper.startswith("GW5AR-") or upper == "GW5AR":
        return "GW5AR"
    if upper.startswith("GW5AS-") or upper == "GW5AS":
        return "GW5AS"
    return None


def resolve_gowin_design_guide_source_path(device: str | None, repo_root: Path | None = None) -> Path | None:
    family_key = _gowin_family_key(device)
    if family_key is None:
        return None

    root = repo_root or Path(__file__).resolve().parent.parent
    for relative in GOWIN_GUIDE_SOURCE_CANDIDATES.get(family_key, []):
        candidate = root / relative
        if candidate.exists():
            return candidate
    return None


def _deep_merge_dict(base: dict, overlay: dict) -> dict:
    merged = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dict(existing, value)
        elif isinstance(existing, list) and isinstance(value, list):
            merged[key] = existing + [item for item in value if item not in existing]
        else:
            merged[key] = value
    return merged


def _extract_table_rows(section_text: str) -> list[list[str]]:
    rows = []
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or all(not cell for cell in cells):
            continue
        if all(set(cell) <= {"-"} for cell in cells):
            continue
        rows.append(cells)
    return rows


def _section_map(text: str) -> dict[str, str]:
    return {title.strip(): body for title, body in _SECTION_RE.findall(text)}


def _subsection_map(section_text: str) -> dict[str, str]:
    return {title.strip(): body for title, body in _SUBSECTION_RE.findall(section_text)}


def _parse_source_document(text: str, guide_path: Path) -> dict:
    source = "UG984-1.2"
    match = _SOURCE_RE.search(text)
    if match:
        source = match.group(1).strip()

    document_id = source
    version = None
    doc_match = re.match(r"([A-Za-z]+\d+)(?:-([0-9A-Za-z.]+))?", source)
    if doc_match:
        document_id = doc_match.group(1)
        version = doc_match.group(2)

    return {
        "title": "GW5AT & GW5AST FPGA Schematic Design Guide",
        "document_id": document_id,
        "version": version,
        "device_family": "GW5AT/GW5AST",
        "path": _repo_relative_path(guide_path),
    }


def _parse_power_domain_map(text: str, source_label: str) -> list[dict]:
    power_section = _section_map(text).get("1. 电源设计", "")
    domain_rows = _extract_table_rows(_subsection_map(power_section).get("电源域分类", ""))
    result = []
    for group, rail_name, description, *_rest in domain_rows[1:]:
        result.append({
            "group": group,
            "rail_name": rail_name,
            "description": description or None,
            "nominal_voltage": None,
            "ripple_max_pct": None,
            "source": source_label,
        })

    ripple_map = {
        rail: float(pct)
        for rail, pct in _RIPPLE_RE.findall(power_section)
    }
    for item in result:
        base_name = item["rail_name"].replace("*", "")
        if base_name in ripple_map:
            item["ripple_max_pct"] = ripple_map[base_name]
    return result


def _parse_power_sequencing_rules(text: str, source_label: str) -> list[dict]:
    power_section = _section_map(text).get("1. 电源设计", "")
    rules = []
    if "VCCX 在 VCC 之前上电" in power_section:
        rules.append({
            "rule": "Power up VCCX before VCC.",
            "rail_before": "VCCX",
            "rail_after": "VCC",
            "severity": "WARNING",
            "source": source_label,
        })
    return rules


def _parse_power_ramp_constraints(text: str, source_label: str) -> list[dict]:
    result = []
    for rail, min_v, max_v, unit in _RAMP_RE.findall(text):
        result.append({
            "rail": rail.replace("*", ""),
            "slew_rate_min": float(min_v),
            "slew_rate_max": float(max_v),
            "unit": unit.replace("µ", "μ"),
            "source": source_label,
        })
    return result


def _parse_rail_merge_guidelines(text: str, source_label: str) -> list[dict]:
    power_section = _section_map(text).get("1. 电源设计", "")
    merge_rows = _extract_table_rows(_subsection_map(power_section).get("电源合并建议", ""))
    result = []
    for row in merge_rows[1:]:
        if len(row) < 2:
            continue
        rails_text, recommendation = row[0], row[1]
        rails = [
            token.strip().replace("*", "")
            for token in re.split(r"\+|,|/| and ", rails_text)
            if token.strip()
        ]
        can_merge = "可合并" in recommendation or "可与同电压电源合并" in recommendation
        severity = "WARNING" if ("不要和其他电源合并" in recommendation or "单独供电" in recommendation) else "INFO"
        result.append({
            "rails": rails or [rails_text.replace("*", "")],
            "can_merge": can_merge,
            "conditions": recommendation,
            "recommendation": recommendation,
            "severity": severity,
            "source": source_label,
        })
    return result


def _parse_pin_connection_rules(text: str, source_label: str) -> list[dict]:
    config_section = _section_map(text).get("2. 关键配置管脚", "")
    result = []

    def add_rule(pin: str, rule: str, connection_type: str, severity: str, *, external_component: str | None = None, condition: str | None = None) -> None:
        result.append({
            "pin": pin,
            "rule": rule,
            "connection_type": connection_type,
            "external_component": external_component,
            "condition": condition,
            "severity": severity,
            "source": source_label,
        })

    if "RECONFIG_N" in config_section:
        add_rule("RECONFIG_N", "Keep high during power-up; release after power is stable for 1 ms.", "pull_up", "ERROR")
        add_rule("RECONFIG_N", "Reconfiguration requires a low pulse of at least 25 ns.", "conditional", "INFO")

    if "READY" in config_section:
        add_rule("READY", "External pull-up required for open-drain READY output.", "pull_up", "ERROR", external_component="4.7K pull-up to 3.3V")

    if "DONE" in config_section:
        add_rule("DONE", "External pull-up required for open-drain DONE output.", "pull_up", "ERROR", external_component="4.7K pull-up to 3.3V")
        add_rule("DONE", "When used as GPIO input, keep the initial value high before configuration.", "conditional", "WARNING")

    if "CFGBVS" in config_section:
        add_rule("CFGBVS", "CFGBVS must not float.", "must_not_float", "ERROR")
        add_rule("CFGBVS", "Tie high when configuration-bank VCCIO is at least 2.5 V.", "tie_high", "ERROR", condition="configuration-bank VCCIO >= 2.5V")
        add_rule("CFGBVS", "Tie low when configuration-bank VCCIO is at most 1.8 V.", "tie_low", "ERROR", condition="configuration-bank VCCIO <= 1.8V")

    if "PUDC_B" in config_section:
        add_rule("PUDC_B", "PUDC_B must not float.", "must_not_float", "ERROR")
        add_rule("PUDC_B", "Bias PUDC_B through a 1k resistor to VCCIO or GND.", "external_component", "ERROR", external_component="1k resistor to VCCIO or GND")

    if "MODE[2:0]" in config_section:
        add_rule("MODE[2:0]", "Bias MODE straps with 4.7K pull-up and 1K pull-down resistors.", "external_component", "ERROR", external_component="4.7K pull-up, 1K pull-down")
        add_rule("SSPI_HOLDN/SSPI_CSN", "If SSPI is unused, pull SSPI_HOLDN low or pull SSPI_CSN high.", "conditional", "WARNING")

    return result


def _parse_decoupling_requirements(text: str, source_label: str) -> list[dict]:
    power_section = _section_map(text).get("1. 电源设计", "")
    result = []
    common_filter = "ferrite bead isolation plus ceramic capacitor"
    for rail, pct in _RIPPLE_RE.findall(power_section):
        result.append({
            "rail": rail.replace("*", ""),
            "ripple_max_pct": float(pct),
            "filter_type": common_filter,
            "capacitor_tolerance": "±10%",
            "notes": "Cross-domain isolation and ferrite-bead filtering are recommended.",
            "severity": "WARNING",
            "source": source_label,
        })

    special_rails = [
        ("VDDAQ/VDDDQ", "Use a low-noise LDO if merged."),
        ("VDDTQ", "Do not merge with other noisy rails."),
        ("VDDAM/VDDDM/VDDXM", "Use ferrite-bead isolation for MIPI-sensitive rails."),
    ]
    for rail, notes in special_rails:
        result.append({
            "rail": rail,
            "ripple_max_pct": None,
            "filter_type": common_filter,
            "capacitor_tolerance": "±10%",
            "notes": notes,
            "severity": "WARNING",
            "source": source_label,
        })
    return result


def _parse_clock_design_rules(text: str, source_label: str) -> list[dict]:
    clock_section = _section_map(text).get("4. 时钟设计", "")
    result = []
    if "串联 0.1uF 电容" in clock_section:
        result.append({
            "signal": "SerDes reference clock",
            "requirement": "AC-couple the SerDes high-speed reference clock close to the FPGA pins.",
            "external_component": "0.1uF series capacitor",
            "notes": "Applies to high-speed SerDes reference-clock inputs.",
            "severity": "ERROR",
            "source": source_label,
        })
    if "GCLK_T" in clock_section:
        result.append({
            "signal": "System clock",
            "requirement": "Prefer a dedicated GCLK_T pin for single-ended system clocks.",
            "external_component": None,
            "notes": None,
            "severity": "WARNING",
            "source": source_label,
        })
    if "PLL_T" in clock_section:
        result.append({
            "signal": "PLL clock input",
            "requirement": "Prefer a dedicated PLL_T pin for single-ended PLL clock inputs.",
            "external_component": None,
            "notes": None,
            "severity": "WARNING",
            "source": source_label,
        })
    if "MH2029-221Y" in clock_section:
        result.append({
            "signal": "External crystal",
            "requirement": "Bias the crystal supply with a ferrite bead and local decoupling.",
            "external_component": "MH2029-221Y ferrite bead + 10nF decoupling",
            "notes": "Series resistor tolerance should be <= ±5%.",
            "severity": "WARNING",
            "source": source_label,
        })
    return result


def _parse_configuration_mode_support(text: str, source_label: str) -> list[dict]:
    result = []
    config_section = _section_map(text).get("3. 配置模式", "")
    table = _extract_table_rows(_subsection_map(config_section).get("GW5AT-15 支持的配置模式", ""))
    if table:
        header = table[0][1:]
        for row in table[1:]:
            package = row[0]
            for mode, supported in zip(header, row[1:]):
                result.append({
                    "device": "GW5AT-15",
                    "package": package,
                    "mode": mode,
                    "supported": supported == "✓",
                    "max_clock_freq": "100MHz" if mode == "JTAG" else None,
                    "signals": [],
                    "notes": None,
                    "source": source_label,
                })

    if "JTAG" in config_section:
        result.append({
            "device": None,
            "package": None,
            "mode": "JTAG",
            "supported": True,
            "max_clock_freq": "100MHz",
            "signals": ["TCK", "TMS", "TDI", "TDO"],
            "notes": "Align VCCIO with the JTAG bank voltage.",
            "source": source_label,
        })
    return result


def _parse_io_standard_rules(text: str, source_label: str) -> list[dict]:
    result = []
    if "100Ω" in text and "LVDS" in text:
        result.append({
            "standard": "LVDS",
            "requirement": "Use internal programmable 100Ω differential input termination where supported.",
            "termination": "100Ω internal differential termination",
            "applies_to": "GW5AT-15/GW5AT-60 all regions; GW5AT-138/GW5AT-75 top and bottom regions only",
            "severity": "WARNING",
            "source": source_label,
        })
    if "SSTL/HSTL" in text:
        result.append({
            "standard": "SSTL/HSTL",
            "requirement": "Provide VREF for SSTL/HSTL using internal 0.5x VCCIO or an external VREF input.",
            "termination": None,
            "applies_to": "Banks using SSTL/HSTL inputs or outputs",
            "severity": "ERROR",
            "source": source_label,
        })
    return result


def _parse_design_guideline_text(text: str, source_label: str) -> list[dict]:
    guidelines = [
        ("power", "Use ferrite-bead isolation between different voltage domains."),
        ("power", "Prefer a dedicated supply for VCC; do not merge noisy VDDTQ rails with other domains."),
        ("clock", "Place SerDes reference-clock AC coupling close to the FPGA pins."),
        ("clock", "Use dedicated clock input pins for system and PLL clocks when available."),
        ("io", "All banks support true LVDS output; review package-specific input-termination scope before reusing family capability."),
        ("config", "MODE straps should use resistor networks instead of hard ties whenever possible."),
    ]
    return [
        {"category": category, "guideline": guideline, "source": source_label}
        for category, guideline in guidelines
    ]


def parse_gowin_gw5at_design_guide(guide_path: Path) -> dict:
    text = guide_path.read_text(encoding="utf-8", errors="replace")
    source_document = _parse_source_document(text, guide_path)
    source_label = "-".join(
        part for part in [source_document.get("document_id"), source_document.get("version")] if part
    ) or source_document.get("document_id") or "UG984"

    return {
        "source_document": source_document,
        "source_documents": [source_document],
        "power_domain_map": _parse_power_domain_map(text, source_label),
        "power_sequencing_rules": _parse_power_sequencing_rules(text, source_label),
        "power_ramp_constraints": _parse_power_ramp_constraints(text, source_label),
        "rail_merge_guidelines": _parse_rail_merge_guidelines(text, source_label),
        "pin_connection_rules": _parse_pin_connection_rules(text, source_label),
        "decoupling_requirements": _parse_decoupling_requirements(text, source_label),
        "clock_design_rules": _parse_clock_design_rules(text, source_label),
        "configuration_mode_support": _parse_configuration_mode_support(text, source_label),
        "io_standard_rules": _parse_io_standard_rules(text, source_label),
        "design_guideline_text": _parse_design_guideline_text(text, source_label),
    }


def _load_design_guide_from_json(guide_path: Path) -> dict:
    try:
        payload = json.loads(guide_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if isinstance(payload.get("domains"), dict):
        guide = payload["domains"].get("design_guide", {})
    else:
        guide = payload.get("design_guide", payload)

    if not isinstance(guide, dict):
        return {}

    result = dict(guide)
    source_document = result.get("source_document", {})
    if source_document and "path" not in source_document:
        result["source_document"] = {
            **source_document,
            "path": _repo_relative_path(guide_path),
        }

    source_documents = []
    for item in result.get("source_documents", []):
        if not isinstance(item, dict):
            continue
        if "path" not in item and item.get("scope") == "family_schematic_manual":
            item = {
                **item,
                "path": _repo_relative_path(guide_path),
            }
        source_documents.append(item)
    if source_documents:
        result["source_documents"] = source_documents
    return result


def _package_source_documents(device: str, package: str | None, pinout_data: dict | None) -> list[dict]:
    device_key = device if device in LATEST_GOWIN_PACKAGE_GUIDES else device.split("_")[0]
    family_key = _gowin_family_key(device)
    source_doc = LATEST_GOWIN_PACKAGE_GUIDES.get(device_key)
    result = []
    if source_doc:
        result.append({
            **source_doc,
            "scope": "package_pinout",
            "device": device,
            "package": package,
        })

    if pinout_data and pinout_data.get("source_file"):
        result.append({
            "document_id": "local_pinout_extract",
            "version": None,
            "released_on": None,
            "title": pinout_data.get("source_file"),
            "url": None,
            "scope": "local_extract_input",
            "device": device,
            "package": package,
        })

    product_source = GOWIN_PRODUCT_SOURCES.get(family_key)
    if product_source:
        result.append({
            **product_source,
            "scope": "product_page_capability_boundary",
            "device": device,
            "package": package,
        })
    return result


def _extract_logical_power_rails(physical_rail: str) -> list[str]:
    upper = (physical_rail or "").upper().strip("*")
    matches: list[tuple[int, str]] = []
    for pattern, normalized in _LOGICAL_POWER_PATTERNS:
        for match in pattern.finditer(upper):
            matches.append((match.start(), normalized))

    logical = []
    for _offset, normalized in sorted(matches, key=lambda item: item[0]):
        if normalized not in logical:
            logical.append(normalized)
    return logical


def _rail_name_tokens(rail_name: str | None) -> list[str]:
    upper = (rail_name or "").upper().strip().strip("*")
    if not upper:
        return []

    tokens = []
    for part in re.split(r"[/,]", upper):
        token = re.sub(r"\[\d+\]$", "", part.strip())
        if token and token not in tokens:
            tokens.append(token)
    return tokens


def build_gowin_package_profile(
    device: str,
    package: str | None,
    pinout_data: dict | None,
    source_documents: list[dict],
    *,
    family_rules_apply: bool = True,
) -> dict:
    package_upper = (package or "").upper()
    device_upper = (device or "").upper()
    power_rails = (pinout_data or {}).get("power_rails", {})
    pins = (pinout_data or {}).get("pins", [])

    alias_map: dict[str, dict] = {}
    for physical_rail, info in power_rails.items():
        logical_rails = _extract_logical_power_rails(physical_rail)
        if not logical_rails:
            continue
        alias_map[physical_rail] = {
            "physical_rail": physical_rail,
            "logical_rails": logical_rails,
            "pin_count": info.get("pin_count"),
            "pins": info.get("pins", []),
            "merge_type": "bonded_merge" if len(logical_rails) > 1 else "dedicated",
            "source": "package_pinout",
        }

    for pin in pins:
        physical_rail = pin.get("name")
        logical_rails = _extract_logical_power_rails(physical_rail or "")
        if not physical_rail or not logical_rails:
            continue
        alias = alias_map.setdefault(
            physical_rail,
            {
                "physical_rail": physical_rail,
                "logical_rails": logical_rails,
                "pin_count": 0,
                "pins": [],
                "merge_type": "bonded_merge" if len(logical_rails) > 1 else "dedicated",
                "source": "package_pinout",
            },
        )
        pin_id = pin.get("pin")
        if pin_id and pin_id not in alias["pins"]:
            alias["pins"].append(pin_id)
        alias["pin_count"] = len(alias["pins"]) if alias["pins"] else alias.get("pin_count")
        for logical_rail in logical_rails:
            if logical_rail not in alias["logical_rails"]:
                alias["logical_rails"].append(logical_rail)

    power_rail_aliases = sorted(alias_map.values(), key=lambda item: item["physical_rail"])
    logical_rail_map: dict[str, list[dict]] = {}
    merged_logical_rail_groups = []
    for alias in power_rail_aliases:
        if len(alias["logical_rails"]) > 1 and alias["logical_rails"] not in merged_logical_rail_groups:
            merged_logical_rail_groups.append(alias["logical_rails"])
        for logical_rail in alias["logical_rails"]:
            logical_rail_map.setdefault(logical_rail, []).append({
                "physical_rail": alias["physical_rail"],
                "pin_count": alias.get("pin_count"),
                "source": "package_pinout",
            })

    return {
        "device": device,
        "package": package_upper or package,
        "family_rules_apply": family_rules_apply,
        "source_documents": source_documents,
        "power_rail_aliases": power_rail_aliases,
        "logical_rail_map": logical_rail_map,
        "merged_logical_rail_groups": merged_logical_rail_groups,
        "package_notes": PACKAGE_PROFILE_NOTES.get((device_upper, package_upper), []),
    }


def _derive_pinout_config_rules(pinout_data: dict | None, source_label: str) -> list[dict]:
    pins = (pinout_data or {}).get("pins", [])
    rules = []

    def add_rule(pin: str, rule: str, connection_type: str, severity: str, **extra: object) -> None:
        item = {
            "pin": pin,
            "rule": rule,
            "connection_type": connection_type,
            "severity": severity,
            "source": source_label,
        }
        item.update(extra)
        rules.append(item)

    seen: set[tuple[str, str]] = set()
    for pin in pins:
        config_function = (pin.get("config_function") or "").upper()
        drc = pin.get("drc") or {}
        must_connect = drc.get("must_connect")
        if not config_function and not must_connect:
            continue

        tokens = {part.strip() for part in config_function.split("/") if part.strip()}
        if drc.get("config_function"):
            tokens.add(str(drc.get("config_function")).upper())

        def maybe_add(pin_name: str, text: str, connection_type: str = "must_connect", severity: str = "ERROR", **extra: object) -> None:
            key = (pin_name, text)
            if key in seen:
                return
            seen.add(key)
            add_rule(pin_name, text, connection_type, severity, **extra)

        if "RECONFIG_N" in tokens:
            maybe_add("RECONFIG_N", "Package pinout marks RECONFIG_N as a required configuration connection.")
        if "READY" in tokens:
            maybe_add("READY", "Package pinout marks READY as a required status output connection.")
        if "DONE" in tokens:
            maybe_add("DONE", "Package pinout marks DONE as a required status output connection.")
        if "PUDC_B" in tokens:
            maybe_add("PUDC_B", "Package pinout exposes PUDC_B as a configuration strap that must not be left floating.", "must_not_float")
        if "MODE0" in tokens or "MODE1" in tokens or "MODE2" in tokens:
            for mode_pin in sorted(token for token in tokens if token.startswith("MODE")):
                maybe_add(mode_pin, f"Package pinout marks {mode_pin} as a required configuration strap.", "must_not_float")
        if "CCLK" in tokens or "EMCCLK" in tokens:
            maybe_add("CCLK", "Package pinout marks CCLK as a required configuration clock connection.")
        if {"TCK", "TMS", "TDI", "TDO"} & tokens:
            for jtag_pin in sorted(token for token in tokens if token in {"TCK", "TMS", "TDI", "TDO"}):
                maybe_add(jtag_pin, f"Package pinout exposes {jtag_pin} for JTAG configuration/debug access.", "conditional", "INFO")
        if {"SSPI_CLK", "SSPI_CS_N", "SSPI_WPN"} & tokens:
            for spi_pin in sorted(token for token in tokens if token.startswith("SSPI_")):
                maybe_add(spi_pin, f"Package pinout exposes {spi_pin} for serial configuration mode.", "conditional", "INFO")
        if {"MOSI", "MISO"} & tokens:
            for spi_pin in sorted(token for token in tokens if token in {"MOSI", "MISO"}):
                severity = "WARNING" if must_connect == "recommended" else "INFO"
                maybe_add(spi_pin, f"Package pinout exposes {spi_pin} as a serial configuration data path.", "conditional", severity)

    return rules


def _derive_power_domain_map_from_pinout(pinout_data: dict | None, source_label: str) -> list[dict]:
    result = []
    power_rails = (pinout_data or {}).get("power_rails", {})
    for rail_name, info in power_rails.items():
        logical_rails = _extract_logical_power_rails(rail_name)
        group = "general"
        upper = rail_name.upper()
        if "M0_" in upper:
            group = "mipi"
        elif "VCCIO" in upper:
            group = "io_bank"
        elif "VQPS" in upper:
            group = "efuse"
        elif "VCC" in upper or "VCC_" in upper:
            group = "core_aux"

        result.append({
            "group": group,
            "rail_name": rail_name,
            "description": info.get("description"),
            "nominal_voltage": None,
            "voltage_range": {
                "min": info.get("min_voltage"),
                "max": info.get("max_voltage"),
                "unit": "V",
            },
            "logical_rails": logical_rails,
            "source": source_label,
        })
    return result


def _derive_configuration_modes_from_pinout(pinout_data: dict | None, source_label: str) -> list[dict]:
    pins = (pinout_data or {}).get("pins", [])
    package = (pinout_data or {}).get("package")
    device = (pinout_data or {}).get("device")
    token_to_names: dict[str, list[str]] = {}

    for pin in pins:
        config_function = (pin.get("config_function") or "").upper()
        drc = pin.get("drc") or {}
        tokens = {part.strip() for part in config_function.split("/") if part.strip()}
        if drc.get("config_function"):
            tokens.add(str(drc.get("config_function")).upper())
        for token in tokens:
            token_to_names.setdefault(token, []).append(pin.get("name") or pin.get("pin"))

    result = []
    if all(token in token_to_names for token in ("TCK", "TMS", "TDI", "TDO")):
        result.append({
            "device": device,
            "package": package,
            "mode": "JTAG",
            "supported": True,
            "max_clock_freq": None,
            "signals": ["TCK", "TMS", "TDI", "TDO"],
            "notes": "Derived from package pinout JTAG signal exposure.",
            "source": source_label,
        })
    if "RECONFIG_N" in token_to_names and "CCLK" in token_to_names:
        serial_signals = [token for token in ("CCLK", "MOSI", "MISO", "SSPI_CLK", "SSPI_CS_N", "SSPI_WPN") if token in token_to_names]
        result.append({
            "device": device,
            "package": package,
            "mode": "SERIAL_BOOT",
            "supported": bool(serial_signals),
            "max_clock_freq": None,
            "signals": serial_signals,
            "notes": "Derived from package pinout configuration/status signal exposure.",
            "source": source_label,
        })
    return result


def _derive_io_standard_rules_from_dc(gowin_dc: dict | None, source_label: str) -> list[dict]:
    result = []
    items = (gowin_dc or {}).get("io_standards", [])
    if any(item.get("standard") == "LVDS" and item.get("vcco") == 2.5 for item in items):
        result.append({
            "standard": "LVDS",
            "requirement": "Set the bank VCCIO to 2.5 V when using True LVDS.",
            "termination": None,
            "applies_to": "Banks using True LVDS",
            "severity": "WARNING",
            "source": source_label,
        })
    return result


def _derive_metadata_only_guidelines(pin_rules: list[dict], power_domain_map: list[dict], io_rules: list[dict], source_label: str) -> list[dict]:
    guidelines = [
        {
            "category": "coverage",
            "guideline": "This design-guide bundle is derived from package pinout and DC datasheet facts; family prose rules are not yet normalized.",
            "source": source_label,
        }
    ]
    if any(item.get("pin") == "PUDC_B" for item in pin_rules):
        guidelines.append({
            "category": "config",
            "guideline": "Treat PUDC_B and MODE straps as explicit configuration nets, not optional GPIO defaults.",
            "source": source_label,
        })
    if any(item.get("group") == "mipi" for item in power_domain_map):
        guidelines.append({
            "category": "power",
            "guideline": "Package power rails include dedicated MIPI-related supplies; keep package-level rail binding visible during review.",
            "source": source_label,
        })
    if io_rules:
        guidelines.append({
            "category": "io",
            "guideline": "True LVDS use should be checked against package/DC VCCIO requirements before reusing generic family assumptions.",
            "source": source_label,
        })
    return guidelines


def build_gowin_metadata_only_design_guide(
    device: str,
    package: str | None,
    pinout_data: dict | None,
    gowin_dc: dict | None = None,
) -> dict:
    family_key = _gowin_family_key(device)
    source_document = dict(LATEST_GOWIN_FAMILY_GUIDES.get(family_key, {}))
    if not source_document:
        return {}

    source_document.update({
        "scope": "family_schematic_manual",
        "device": device,
        "package": package,
    })
    source_documents = [source_document]
    source_documents.extend(
        item for item in _package_source_documents(device, package, pinout_data)
        if item not in source_documents
    )
    source_label = "-".join(
        part for part in [source_document.get("document_id"), source_document.get("version")] if part
    ) or source_document.get("document_id")
    pin_rules = _derive_pinout_config_rules(pinout_data, source_label)
    power_domain_map = _derive_power_domain_map_from_pinout(pinout_data, source_label)
    io_standard_rules = _derive_io_standard_rules_from_dc(gowin_dc, source_label)
    configuration_mode_support = _derive_configuration_modes_from_pinout(pinout_data, source_label)

    return {
        "source_document": source_document,
        "source_documents": source_documents,
        "package_profile": build_gowin_package_profile(
            device,
            package,
            pinout_data,
            source_documents,
            family_rules_apply=False,
        ),
        "power_domain_map": power_domain_map,
        "power_sequencing_rules": [],
        "power_ramp_constraints": [],
        "rail_merge_guidelines": [],
        "pin_connection_rules": pin_rules,
        "decoupling_requirements": [],
        "clock_design_rules": [],
        "configuration_mode_support": configuration_mode_support,
        "io_standard_rules": io_standard_rules,
        "design_guideline_text": _derive_metadata_only_guidelines(pin_rules, power_domain_map, io_standard_rules, source_label),
    }


def build_gowin_power_sequence_domain(design_guide: dict) -> dict:
    source_doc = design_guide.get("source_document", {})
    source_label = "-".join(
        part for part in [source_doc.get("document_id"), source_doc.get("version")] if part
    ) or source_doc.get("document_id")
    ramp_map = {item.get("rail"): item for item in design_guide.get("power_ramp_constraints", [])}
    sequencing_rules = []
    for item in design_guide.get("power_sequencing_rules", []):
        sequencing_rules.append({
            "rail_before": item.get("rail_before"),
            "rail_after": item.get("rail_after"),
            "min_delay": {},
            "max_delay": {},
            "description": item.get("rule"),
            "source": item.get("source"),
        })

    power_rails = []
    ordered_names = []
    for rule in design_guide.get("power_sequencing_rules", []):
        before = rule.get("rail_before")
        after = rule.get("rail_after")
        if before and before not in ordered_names:
            ordered_names.append(before)
        if after and after not in ordered_names:
            ordered_names.append(after)
    for fallback in ("VCCLDO", "VCCIO"):
        if fallback in ramp_map and fallback not in ordered_names:
            ordered_names.append(fallback)

    for index, rail_name in enumerate(ordered_names, start=1):
        ramp = ramp_map.get(rail_name)
        power_rails.append({
            "name": rail_name,
            "nominal_voltage": None,
            "voltage_range": {
                "min": None,
                "max": None,
                "unit": "V",
            },
            "sequence_order": index if index <= 2 else None,
            "ramp_rate": {
                "min": ramp.get("slew_rate_min"),
                "typ": None,
                "max": ramp.get("slew_rate_max"),
                "unit": ramp.get("unit"),
            } if ramp else None,
            "max_current": {},
            "source": ramp.get("source") if ramp else source_label,
        })

    return {
        "power_stages": [],
        "power_rails": power_rails,
        "startup_parameters": [],
        "protection_thresholds": [],
        "sequencing_rules": sequencing_rules,
        "power_sequence_summary": {
            "has_soft_start": False,
            "has_power_good": False,
            "has_enable_pin": False,
            "has_uvlo": False,
            "rail_count": len(power_rails),
            "sequencing_type": "fixed" if sequencing_rules else None,
            "source": source_label,
            "source_path": source_doc.get("path"),
        },
    }


def build_gowin_constraint_overlays(design_guide: dict) -> dict:
    source_doc = design_guide.get("source_document", {})
    source_label = "-".join(
        part for part in [source_doc.get("document_id"), source_doc.get("version")] if part
    ) or source_doc.get("document_id")
    source_path = source_doc.get("path")
    source_documents = design_guide.get("source_documents", [])
    package_profile = design_guide.get("package_profile", {})

    pin_rules = design_guide.get("pin_connection_rules", [])
    pin_requirements = {}

    def pin_rule(pin: str, keyword: str | None = None) -> list[dict]:
        return [
            item for item in pin_rules
            if item.get("pin") == pin and (keyword is None or keyword in (item.get("rule") or "") or keyword in (item.get("external_component") or ""))
        ]

    if pin_rule("RECONFIG_N"):
        pin_requirements["RECONFIG_N"] = {
            "must_not_float": True,
            "must_be_high_during_powerup": True,
            "release_after": {"typ": 1.0, "unit": "ms"},
            "reconfig_pulse_low_min": {"min": 25.0, "unit": "ns"},
            "gpio_usage": "output_only",
            "source": source_label,
        }

    ready_rule = pin_rule("READY", "4.7K")
    if ready_rule:
        pin_requirements["READY"] = {
            "must_not_float": True,
            "open_drain": True,
            "requires_pullup": {
                "resistance_ohm": 4700,
                "target_voltage": 3.3,
                "unit": "V",
            },
            "source": source_label,
        }

    done_rule = pin_rule("DONE", "4.7K")
    if done_rule:
        pin_requirements["DONE"] = {
            "must_not_float": True,
            "open_drain": True,
            "requires_pullup": {
                "resistance_ohm": 4700,
                "target_voltage": 3.3,
                "unit": "V",
            },
            "gpio_input_requires_initial_high": True,
            "source": source_label,
        }

    if pin_rule("CFGBVS"):
        pin_requirements["CFGBVS"] = {
            "must_not_float": True,
            "configuration_banks": ["bank3", "bank4", "bank10"],
            "tie_high_when_vccio_gte_v": 2.5,
            "tie_low_when_vccio_lte_v": 1.8,
            "source": source_label,
        }

    if pin_rule("PUDC_B"):
        pin_requirements["PUDC_B"] = {
            "must_not_float": True,
            "strap_resistor_ohm": 1000,
            "tie_to": ["VCCIO", "GND"],
            "low_behavior": "all_gpio_weak_pullup",
            "high_behavior": "all_gpio_high_z",
            "source": source_label,
        }

    ripple_limits = {}
    sensitive_rail_groups = {"serdes": [], "mipi": []}
    for item in design_guide.get("decoupling_requirements", []):
        rail = item.get("rail")
        if item.get("ripple_max_pct") is not None:
            ripple_limits[rail] = {
                "max_pct": float(item.get("ripple_max_pct")),
                "unit": "%",
            }
        upper_rail = (rail or "").upper()
        if any(token in upper_rail for token in ("VDDAQ", "VDDDQ", "VDDHAQ", "VDDTQ")):
            sensitive_rail_groups["serdes"].append(rail)
        if any(token in upper_rail for token in ("VDDAM", "VDDDM", "VDDXM")):
            sensitive_rail_groups["mipi"].append(rail)

    sensitive_power_pin_groups = {}
    for group_name, rails in sensitive_rail_groups.items():
        logical_rails = []
        pin_name_tokens = []

        for rail in rails:
            for logical_rail in _extract_logical_power_rails(rail):
                if logical_rail not in logical_rails:
                    logical_rails.append(logical_rail)
                if logical_rail not in pin_name_tokens:
                    pin_name_tokens.append(logical_rail)
            for token in _rail_name_tokens(rail):
                if token not in pin_name_tokens:
                    pin_name_tokens.append(token)

        for alias in package_profile.get("power_rail_aliases", []):
            alias_logical_rails = alias.get("logical_rails", [])
            if not any(item in alias_logical_rails for item in logical_rails):
                continue
            for token in _rail_name_tokens(alias.get("physical_rail")):
                if token not in pin_name_tokens:
                    pin_name_tokens.append(token)

        if pin_name_tokens:
            sensitive_power_pin_groups[group_name] = {
                "logical_rails": logical_rails,
                "pin_name_tokens": pin_name_tokens,
                "recommended_component": "ferrite_bead",
                "missing_isolation_severity": "WARNING" if group_name == "mipi" else "ERROR",
                "source": source_label,
            }

    ramp_rates = {
        item.get("rail"): {
            "min": item.get("slew_rate_min"),
            "typ": None,
            "max": item.get("slew_rate_max"),
            "unit": item.get("unit"),
        }
        for item in design_guide.get("power_ramp_constraints", [])
    }

    return {
        "configuration_boot": {
            "class": "boot_configuration",
            "review_required": True,
            "design_guide_source": source_label,
            "design_guide_source_path": source_path,
            "source_documents": source_documents,
            "package_profile_summary": {
                "device": package_profile.get("device"),
                "package": package_profile.get("package"),
                "package_notes": package_profile.get("package_notes", []),
            } if package_profile else {},
            "pin_requirements": pin_requirements,
            "mode_requirements": {
                "strap_required": True,
                "signals": ["MODE0", "MODE1", "MODE2"],
                "pullup_resistor_ohm": 4700,
                "pulldown_resistor_ohm": 1000,
                "post_config_default_mode": "SSPI",
                "unused_interface_rules": [
                    {
                        "interface": "SSPI",
                        "allowed_mitigations": [
                            "pull SSPI_HOLDN low",
                            "pull SSPI_CSN high",
                        ],
                    }
                ],
                "source": source_label,
            },
            "jtag_constraints": {
                "tck_max_freq_mhz": 100.0,
                "tck_pullup_resistor_ohm": 4700,
                "tck_local_bypass_cap_nf": 100.0,
                "vccio_alignment_required": True,
                "esd_recommended": "SP3003_04XTG",
                "source": source_label,
            },
        },
        "power_integrity": {
            "class": "power_integrity",
            "review_required": True,
            "design_guide_source": source_label,
            "design_guide_source_path": source_path,
            "source_documents": source_documents,
            "package_power_rail_aliases": package_profile.get("power_rail_aliases", []),
            "package_merged_logical_rail_groups": package_profile.get("merged_logical_rail_groups", []),
            "package_specific_notes": package_profile.get("package_notes", []),
            "ripple_limits_pct": ripple_limits,
            "ramp_rates": ramp_rates,
            "cross_domain_isolation_recommended": True,
            "ferrite_bead_recommended": True,
            "sensitive_rail_groups": sensitive_rail_groups,
            "sensitive_power_pin_groups": sensitive_power_pin_groups,
            "merge_recommendations": {
                "VCC": "dedicated_supply_recommended",
                "VCCX": "merge_allowed_if_same_voltage_and_current_budget_ok",
                "VCCLDO": "merge_allowed_if_same_voltage_and_current_budget_ok",
                "VDDTQ": "do_not_merge_with_other_rails",
                "VDDAQ_VDDDQ": "low_noise_ldo_recommended_if_merged",
            },
        },
        "clocking": {
            "class": "clocking",
            "review_required": True,
            "design_guide_source": source_label,
            "design_guide_source_path": source_path,
            "source_documents": source_documents,
            "system_clock_preferred_single_ended_pin": "GCLK_T",
            "pll_clock_preferred_single_ended_pin": "PLL_T",
            "serdes_refclk_ac_coupling_nf": 100.0,
            "serdes_refclk_placement": "close_to_fpga_pins",
            "external_crystal_recommendation": {
                "ferrite_bead": "MH2029-221Y",
                "local_decoupling_nf": 10.0,
                "series_resistor_tolerance_pct_max": 5.0,
            },
        },
        "io_signaling": {
            "class": "io_signaling",
            "review_required": True,
            "design_guide_source": source_label,
            "design_guide_source_path": source_path,
            "source_documents": source_documents,
            "lvds_input_termination": {
                "supported": True,
                "differential_termination_ohm": 100,
                "package_scope": {
                    "GW5AT-15": "all_regions",
                    "GW5AT-60": "all_regions",
                    "GW5AT-138": "top_bottom_only",
                    "GW5AT-75": "top_bottom_only",
                },
            },
            "vref_required_for": ["SSTL", "HSTL"],
            "vref_options": ["internal_0.5x_vccio", "external_input"],
            "all_banks_true_lvds_output": True,
        },
    }


def build_gowin_package_only_constraint_overlays(design_guide: dict) -> dict:
    source_doc = design_guide.get("source_document", {})
    source_label = "-".join(
        part for part in [source_doc.get("document_id"), source_doc.get("version")] if part
    ) or source_doc.get("document_id")
    source_path = source_doc.get("path")
    source_documents = design_guide.get("source_documents", [])
    package_profile = design_guide.get("package_profile", {})
    pin_rules = design_guide.get("pin_connection_rules", [])
    io_rules = design_guide.get("io_standard_rules", [])
    config_modes = design_guide.get("configuration_mode_support", [])

    pin_requirements: dict[str, dict] = {}
    for item in pin_rules:
        pin_name = item.get("pin")
        if pin_name in {"RECONFIG_N", "READY", "DONE", "PUDC_B", "MODE0", "MODE1", "MODE2", "CCLK"}:
            requirement = pin_requirements.setdefault(pin_name, {
                "must_not_float": item.get("connection_type") == "must_not_float",
                "must_connect": item.get("connection_type") in {"must_connect", "must_not_float"},
                "source": item.get("source"),
            })
            requirement["must_not_float"] = requirement.get("must_not_float") or item.get("connection_type") == "must_not_float"
            requirement["must_connect"] = requirement.get("must_connect") or item.get("connection_type") in {"must_connect", "must_not_float"}

    mode_signals = []
    for item in config_modes:
        if item.get("mode") == "SERIAL_BOOT":
            mode_signals = list(item.get("signals", []))
            break

    lvds_rule = next((item for item in io_rules if item.get("standard") == "LVDS"), None)

    return {
        "configuration_boot": {
            "class": "boot_configuration",
            "review_required": True,
            "design_guide_source": source_label,
            "design_guide_source_path": source_path,
            "source_documents": source_documents,
            "package_profile_summary": {
                "device": package_profile.get("device"),
                "package": package_profile.get("package"),
                "package_notes": package_profile.get("package_notes", []),
            } if package_profile else {},
            "pin_requirements": pin_requirements,
            "mode_requirements": {
                "strap_required": any(name.startswith("MODE") for name in pin_requirements),
                "signals": mode_signals,
                "source": source_label,
                "derived_from": "package_pinout",
            },
        },
        "power_integrity": {
            "class": "power_integrity",
            "review_required": True,
            "design_guide_source": source_label,
            "design_guide_source_path": source_path,
            "source_documents": source_documents,
            "package_power_rail_aliases": package_profile.get("power_rail_aliases", []),
            "package_merged_logical_rail_groups": package_profile.get("merged_logical_rail_groups", []),
            "package_specific_notes": package_profile.get("package_notes", []),
            "design_guide_rules_normalized": False,
            "coverage": "package_profile_only",
        },
        "io_signaling": {
            "class": "io_signaling",
            "review_required": True,
            "design_guide_source": source_label,
            "design_guide_source_path": source_path,
            "source_documents": source_documents,
            "design_guide_rules_normalized": False,
            "coverage": "package_dc_only",
            "lvds_bank_vccio_requirement_v": 2.5 if lvds_rule else None,
            "lvds_requirement_source": lvds_rule.get("source") if lvds_rule else None,
        },
    }


def load_gowin_design_guide_bundle(device: str, package: str | None, pinout_data: dict | None, guide_path: Path | None, gowin_dc: dict | None = None) -> dict:
    device_upper = (device or "").upper()
    family_key = _gowin_family_key(device_upper)
    if family_key is None:
        return {}

    if family_key == "GW5AT":
        if guide_path is None or not guide_path.exists():
            return {}

        if guide_path.suffix.lower() == ".json":
            design_guide = _load_design_guide_from_json(guide_path)
        else:
            design_guide = parse_gowin_gw5at_design_guide(guide_path)
        if not design_guide:
            return {}
        source_documents = design_guide.get("source_documents", [])
        source_documents.extend(
            item for item in _package_source_documents(device, package, pinout_data)
            if item not in source_documents
        )
        design_guide["source_documents"] = source_documents
        design_guide["package_profile"] = build_gowin_package_profile(device, package, pinout_data, source_documents)
        constraint_overlays = build_gowin_constraint_overlays(design_guide)
        domains = {
            "design_guide": design_guide,
            "power_sequence": build_gowin_power_sequence_domain(design_guide),
        }
    else:
        if guide_path is not None and guide_path.exists() and guide_path.suffix.lower() == ".json":
            design_guide = _load_design_guide_from_json(guide_path)
            if design_guide:
                source_documents = design_guide.get("source_documents", [])
                source_documents.extend(
                    item for item in _package_source_documents(device, package, pinout_data)
                    if item not in source_documents
                )
                design_guide["source_documents"] = source_documents
                design_guide["package_profile"] = build_gowin_package_profile(device, package, pinout_data, source_documents)
                constraint_overlays = build_gowin_constraint_overlays(design_guide)
                domains = {
                    "design_guide": design_guide,
                    "power_sequence": build_gowin_power_sequence_domain(design_guide),
                }
            else:
                return {}
        else:
            design_guide = build_gowin_metadata_only_design_guide(device, package, pinout_data, gowin_dc)
            if not design_guide:
                return {}
            constraint_overlays = build_gowin_package_only_constraint_overlays(design_guide)
            domains = {
                "design_guide": design_guide,
            }

    return {
        "source": design_guide.get("source_document", {}).get("document_id"),
        "source_path": design_guide.get("source_document", {}).get("path"),
        "domains": domains,
        "constraint_overlays": constraint_overlays,
    }
