#!/usr/bin/env python3
"""Export schematic-design helper bundles from sch-review device exports.

The existing `data/sch_review_export/*.json` files are optimized for DRC and
machine consumption. This script produces a layered design bundle per device so
hardware engineers can move faster when starting a schematic block around one
component.

Each bundle contains:
- `L0_device.json`         canonical device knowledge copied from sch-review export
- `L1_design_intent.json`  grouped pins, constraints, and external block hints
- `L2_quickstart.md`       human-readable checklist for schematic design
- `L3_module_template.json` starter module structure for EDA/manual drafting
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from functools import lru_cache
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(REPO_ROOT))

from design_info_utils import detect_design_page_kind, extract_design_context

DEFAULT_INPUT_DIR = REPO_ROOT / "data/sch_review_export"
DEFAULT_EXTRACTED_DIR = REPO_ROOT / "data/extracted_v2"
DEFAULT_PDF_DIR = REPO_ROOT / "data/raw/datasheet_PDF"
DEFAULT_RAW_SOURCE_MANIFEST = REPO_ROOT / "data/raw/_source_manifest.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/design_bundle"
DEFAULT_REFERENCE_DIR = DEFAULT_INPUT_DIR / "reference"
BUNDLE_SCHEMA = "opendatasheet-design-bundle/0.1"


POWER_PIN_PATTERNS = (
    r"^(VIN|VCC|VDD|VBAT|AVDD|DVDD|PVDD|VDD[A-Z0-9_/-]*)$",
    r"^(IN|SUPPLY)$",
)
GROUND_PIN_PATTERNS = (
    r"^(GND|AGND|PGND|DGND|VSS|EP|PAD|TAB)$",
    r".*GND$",
)
CONTROL_PIN_PATTERNS = (
    r"^(EN|ENABLE|CE|SHDN|SD|RUN|ON/OFF|CTRL|CTL|MODE|FSEL|SYNC|TRK|TRACK|SS/TR|ILIM|RT|RST|RESET|RSTB|RESETB|PWDN|PWDNB|PDN|PDNB)$",
)
STATUS_PIN_PATTERNS = (
    r"^(PG|POK|PGOOD|RESET|FAULT|INT|ALERT|FLAG|STATUS|IRQ|LOCK|ERRB)$",
)
SENSE_PIN_PATTERNS = (
    r"^(FB|VOS|VSENSE|COMP|SNS|SENSE|TR|SS/TR)$",
)
OUTPUT_PIN_PATTERNS = (
    r"^(VOUT|OUT|SW|LX|BST|BOOT)$",
)
OPEN_DRAIN_HINTS = ("open drain", "open-drain", "open collector")


def _sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("_") or "unknown"


def _matches_any(value: str | None, patterns: tuple[str, ...]) -> bool:
    if not value:
        return False
    normalized = value.strip().upper()
    return any(re.match(pattern, normalized) for pattern in patterns)


def _contains_any(value: str | None, fragments: tuple[str, ...]) -> bool:
    if not value:
        return False
    normalized = value.lower()
    return any(fragment in normalized for fragment in fragments)


def _pick_preferred_package(device: dict) -> str | None:
    packages = device.get("packages", {})
    if not packages:
        return None
    ranked = sorted(
        packages.items(),
        key=lambda item: (
            item[1].get("pin_count", 0) <= 0,
            item[1].get("pin_count", 0),
            item[0],
        ),
    )
    return ranked[0][0]


def _constraint_record(source_kind: str, source_key: str | None, entry: dict | str, source_page: int | None = None) -> dict:
    if isinstance(entry, dict):
        parameter = entry.get("parameter")
        min_value = entry.get("min")
        typ_value = entry.get("typ")
        max_value = entry.get("max")
        unit = entry.get("unit")
        conditions = entry.get("conditions")
    else:
        parameter = str(entry)
        min_value = None
        typ_value = None
        max_value = None
        unit = None
        conditions = None
    return {
        "source_kind": source_kind,
        "source_key": source_key,
        "source_page": source_page,
        "parameter": parameter,
        "min": min_value,
        "typ": typ_value,
        "max": max_value,
        "unit": unit,
        "conditions": conditions,
    }


def _entry_haystack(key: str, entry: dict | str) -> str:
    if isinstance(entry, dict):
        parameter = entry.get("parameter") or ""
        conditions = entry.get("conditions") or ""
    else:
        parameter = str(entry)
        conditions = ""
    return " ".join([key, parameter, conditions])


def _score_constraint_candidate(
    key: str,
    entry: dict,
    include: tuple[str, ...],
    exclude: tuple[str, ...] = (),
    prefer: tuple[str, ...] = (),
    prefer_keys: tuple[str, ...] = (),
    unit_allow: tuple[str, ...] = (),
) -> int | None:
    haystack = _entry_haystack(key, entry)
    if exclude and any(re.search(pattern, haystack, re.IGNORECASE) for pattern in exclude):
        return None

    include_hits = sum(bool(re.search(pattern, haystack, re.IGNORECASE)) for pattern in include)
    if include_hits == 0:
        return None

    score = include_hits * 3
    score += sum(bool(re.search(pattern, haystack, re.IGNORECASE)) for pattern in prefer) * 5

    normalized_key = key.upper().split("_")[0]
    if prefer_keys and normalized_key in prefer_keys:
        score += 4

    unit = entry.get("unit") or "" if isinstance(entry, dict) else ""
    if unit_allow and unit not in unit_allow:
        return None
    if unit_allow:
        score += 2

    for value_key in ("min", "typ", "max"):
        if entry.get(value_key) is not None:
            score += 1

    parameter = (entry.get("parameter") or "").lower()
    if "range" in parameter:
        score += 1
    if "maximum" in parameter:
        score += 1
    return score


def _best_constraint_match(
    source_kind: str,
    source: dict,
    include: tuple[str, ...],
    exclude: tuple[str, ...] = (),
    prefer: tuple[str, ...] = (),
    prefer_keys: tuple[str, ...] = (),
    unit_allow: tuple[str, ...] = (),
) -> dict | None:
    best_score = None
    best_match = None
    for key, entry in source.items():
        score = _score_constraint_candidate(
            key,
            entry,
            include=include,
            exclude=exclude,
            prefer=prefer,
            prefer_keys=prefer_keys,
            unit_allow=unit_allow,
        )
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_score = score
            best_match = _constraint_record(source_kind, key, entry)
    return best_match


def _collect_constraints(device: dict, datasheet_design_context: dict | None = None) -> dict:
    abs_max = device.get("absolute_maximum_ratings", {})
    electrical = device.get("electrical_parameters", {})

    spec_map = {
        "vin_abs_max": {
            "source_kind": "absolute_maximum_ratings",
            "source": abs_max,
            "include": (r"^VIN\b", r"^VCC\b", r"^VDD\b", r"^VS\b", r"supply voltage", r"input voltage range"),
            "exclude": (r"leakage", r"current", r"en pin", r"common mode", r"differential input"),
            "prefer": (r"supply voltage", r"input voltage range"),
            "prefer_keys": ("VIN", "VCC", "VDD", "VS"),
            "unit_allow": ("V",),
        },
        "vin_operating": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"\bVIN\b", r"input voltage", r"supply voltage"),
            "exclude": (r"uvlo", r"threshold", r"leakage", r"input current", r"en pin", r"high level", r"low level", r"logic", r"mode pin", r"fsel", r"\bVEN\b"),
            "prefer": (r"^VIN\b", r"input voltage range", r"^input voltage$"),
            "prefer_keys": ("VIN",),
            "unit_allow": ("V",),
        },
        "vout_range": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"\bVOUT\b", r"output voltage"),
            "exclude": (r"threshold", r"power good", r"tolerance", r"accuracy", r"noise", r"\bhigh\b", r"\blow\b", r"monitor", r"feedback"),
            "prefer": (r"output voltage range", r"^VOUT\b"),
            "prefer_keys": ("VOUT",),
            "unit_allow": ("V",),
        },
        "feedback_reference": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"\bVFB\b", r"feedback voltage"),
            "exclude": (r"accuracy", r"leakage"),
            "prefer": (r"^feedback voltage$", r"^VFB\b"),
            "prefer_keys": ("VFB",),
            "unit_allow": ("V",),
        },
        "iout_max": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"\bILOAD\b", r"load current", r"output current", r"maximum load current"),
            "exclude": (r"quiescent", r"leakage", r"input current", r"ground current", r"noise", r"transient"),
            "prefer": (r"maximum load current", r"^load current$", r"^ILOAD\b"),
            "prefer_keys": ("ILOAD", "IOUT"),
            "unit_allow": ("A", "mA"),
        },
        "current_limit": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"current limit", r"short-circuit current", r"\bILIM"),
            "exclude": (r"quiescent", r"leakage", r"threshold hysteresis"),
            "prefer": (r"short-circuit current limit", r"current limit", r"^ILIM"),
            "prefer_keys": ("ILIM", "ISC"),
            "unit_allow": ("A", "mA"),
        },
        "fsw": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"switch.*freq", r"oscillat.*freq", r"\bFSW\b", r"\bFOSC\b"),
            "prefer": (r"switching frequency", r"oscillator frequency"),
            "prefer_keys": ("FSW", "FOSC"),
            "unit_allow": ("kHz", "MHz", "Hz"),
        },
        "uvlo": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"UVLO", r"undervoltage"),
            "prefer": (r"undervoltage lockout", r"\(rising\)"),
            "prefer_keys": ("VUVLO", "UVLO"),
            "unit_allow": ("V",),
        },
        "thermal_shutdown": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"thermal.*shut", r"over.?temp", r"\bTSD\b"),
            "prefer": (r"thermal shutdown",),
        },
        "quiescent_current": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"quiescent current", r"\bIQ\b"),
            "exclude": (r"disabled", r"shutdown current"),
            "prefer": (r"^quiescent current$", r"operating quiescent current"),
            "prefer_keys": ("IQ",),
        },
        "dropout_voltage": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"dropout voltage", r"\bVDROPOUT\b"),
            "prefer": (r"dropout voltage",),
            "prefer_keys": ("VDROPOUT",),
            "unit_allow": ("V", "mV"),
        },
        "common_mode_range": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"common mode voltage range", r"\bVICR\b", r"\bVCM\b"),
            "exclude": (r"rejection",),
            "prefer": (r"common mode voltage range", r"\bVICR\b"),
            "prefer_keys": ("VICR", "VCM"),
            "unit_allow": ("V",),
        },
        "gain_bandwidth": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"gain bandwidth", r"gain bandwidth product", r"\bGBP\b", r"unity gain bandwidth"),
            "prefer": (r"gain bandwidth", r"gain bandwidth product", r"\bGBP\b"),
            "prefer_keys": ("GBP",),
            "unit_allow": ("MHz", "kHz"),
        },
        "slew_rate": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"slew rate", r"\bSR\b"),
            "prefer": (r"slew rate", r"\bSR\b"),
            "prefer_keys": ("SR",),
        },
        "supply_current": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"supply current", r"power supply current", r"\bICC\b", r"\bISY\b"),
            "exclude": (r"shutdown", r"disabled"),
            "prefer": (r"supply current", r"power supply current", r"per amplifier"),
            "prefer_keys": ("ICC", "ISY"),
        },
        "output_capacitance": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"output capacitance", r"\bCOUT\b", r"capacitance for stability"),
            "exclude": (r"input capacitance",),
            "prefer": (r"output capacitance", r"capacitance for stability"),
            "prefer_keys": ("COUT",),
            "unit_allow": ("pF", "nF", "µF", "μF", "uF", "mF"),
        },
        "output_cap_esr": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"\bESR\b", r"capacitance ESR"),
            "prefer": (r"output/input capacitance esr", r"\bESR\b"),
            "prefer_keys": ("ESR",),
            "unit_allow": ("Ω", "mΩ", "kΩ"),
        },
    }

    collected = {}
    for name, spec in spec_map.items():
        match = _best_constraint_match(
            spec["source_kind"],
            spec["source"],
            include=spec["include"],
            exclude=spec.get("exclude", ()),
            prefer=spec.get("prefer", ()),
            prefer_keys=spec.get("prefer_keys", ()),
            unit_allow=spec.get("unit_allow", ()),
        )
        if match:
            collected[name] = match

    datasheet_design_context = datasheet_design_context or {}
    range_map = {
        "VIN": "vin_operating",
        "VOUT": "vout_range",
        "IOUT": "iout_max",
        "FSW": "fsw",
        "FOSC": "fsw",
        "UVLO": "uvlo",
    }
    for hint in datasheet_design_context.get("design_range_hints", []):
        target = range_map.get((hint.get("name") or "").upper())
        if not target or target in collected:
            continue
        collected[target] = {
            "source_kind": "datasheet_range_hint",
            "source_key": hint.get("name"),
            "source_page": hint.get("source_page"),
            "parameter": f"{hint.get('name')} range",
            "min": hint.get("min"),
            "typ": None,
            "max": hint.get("max"),
            "unit": hint.get("unit"),
            "conditions": hint.get("snippet"),
        }
    return collected




def _index_extracted_records(extracted_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not extracted_dir.exists():
        return index
    for path in sorted(extracted_dir.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        mpn = payload.get("extraction", {}).get("component", {}).get("mpn")
        if not mpn:
            continue
        index.setdefault(_sanitize_name(mpn), path)
    return index


def _load_extracted_record(device: dict, extracted_index: dict[str, Path]) -> tuple[dict | None, Path | None]:
    record_path = extracted_index.get(_sanitize_name(device.get("mpn") or ""))
    if not record_path:
        return None, None
    return json.loads(record_path.read_text(encoding="utf-8")), record_path


def _canonical_pdf_map(pdf_dir: Path) -> dict[str, dict]:
    index_path = pdf_dir / "_canonical_index.json"
    if not index_path.exists():
        return {}
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload.get("plan", {})


def _find_canonical_pdf_for_device(device: dict, pdf_dir: Path) -> Path | None:
    mpn = device.get("mpn") or ""
    if not mpn:
        return None
    plan = _canonical_pdf_map(pdf_dir)
    exact = plan.get(f"{mpn}::datasheet", {})
    canonical = exact.get("canonical")
    if canonical:
        candidate = pdf_dir / canonical
        if candidate.exists():
            return candidate

    wanted = _sanitize_name(mpn)
    for key, entry in plan.items():
        material = key.split("::", 1)[0]
        if _sanitize_name(material) != wanted:
            continue
        canonical = entry.get("canonical")
        if canonical:
            candidate = pdf_dir / canonical
            if candidate.exists():
                return candidate

    for candidate in sorted(pdf_dir.glob("*.pdf")):
        if wanted in _sanitize_name(candidate.stem):
            return candidate
    return None


def _build_design_text_pages_from_raw_pdf(pdf_path: Path) -> list[dict]:
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return []
    text_pages = []
    for page_num in range(len(doc)):
        text = doc[page_num].get_text("text", sort=True)
        kind = detect_design_page_kind(text)
        if kind:
            text_pages.append({"page_num": page_num, "kind": kind, "text": text})
    doc.close()
    return text_pages


def _build_design_text_pages_from_pdf(extracted_record: dict, pdf_dir: Path) -> list[dict]:
    pdf_name = extracted_record.get("pdf_name")
    if not pdf_name:
        return []
    pdf_path = pdf_dir / pdf_name
    if not pdf_path.exists():
        return []

    page_classification = extracted_record.get("page_classification", [])
    if not page_classification:
        return []

    doc = fitz.open(pdf_path)
    text_pages = []
    for page in page_classification:
        page_num = page.get("page_num")
        if page_num is None or page_num >= len(doc):
            continue
        text = doc[page_num].get_text("text", sort=True)
        kind = detect_design_page_kind(text) or detect_design_page_kind(page.get("text_preview", ""))
        if kind:
            text_pages.append({"page_num": page_num, "kind": kind, "text": text})
    doc.close()
    return text_pages


def _build_design_text_pages_from_preview(extracted_record: dict) -> list[dict]:
    text_pages = []
    for page in extracted_record.get("page_classification", []):
        preview = page.get("text_preview", "")
        kind = detect_design_page_kind(preview)
        if not kind:
            continue
        text_pages.append({"page_num": page.get("page_num"), "kind": kind, "text": preview})
    return text_pages


def _load_datasheet_design_context(device: dict, extracted_index: dict[str, Path], pdf_dir: Path) -> dict:
    extracted_record, record_path = _load_extracted_record(device, extracted_index)
    if extracted_record:
        if extracted_record.get("design_extraction"):
            design_context = dict(extracted_record["design_extraction"])
            design_context["source_mode"] = "pipeline_design_extraction"
            design_context["source_record"] = record_path.name if record_path else None
            design_context["pdf_name"] = extracted_record.get("pdf_name")
            return design_context

        text_pages = _build_design_text_pages_from_pdf(extracted_record, pdf_dir)
        source_mode = "pdf_text"
        if not text_pages:
            text_pages = _build_design_text_pages_from_preview(extracted_record)
            source_mode = "preview_only"

        design_context = extract_design_context(text_pages)
        design_context["source_mode"] = source_mode
        design_context["source_record"] = record_path.name if record_path else None
        design_context["pdf_name"] = extracted_record.get("pdf_name")
        return design_context

    pdf_path = _find_canonical_pdf_for_device(device, pdf_dir)
    if not pdf_path:
        return {"source_mode": "unavailable"}

    text_pages = _build_design_text_pages_from_raw_pdf(pdf_path)
    if not text_pages:
        return {"source_mode": "unavailable", "pdf_name": pdf_path.name}

    design_context = extract_design_context(text_pages)
    design_context["source_mode"] = "raw_pdf_scan"
    design_context["source_record"] = None
    design_context["pdf_name"] = pdf_path.name
    return design_context


def _repo_relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


@lru_cache(maxsize=1)
def _raw_source_manifest_index(manifest_path: str = str(DEFAULT_RAW_SOURCE_MANIFEST)) -> dict[str, dict]:
    path = Path(manifest_path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    index = {}
    for entry in payload.get("entries", []):
        filename = entry.get("filename")
        if filename and filename not in index:
            index[filename] = entry
    return index


def _official_source_documents(datasheet_design_context: dict) -> list[dict]:
    pdf_name = datasheet_design_context.get("pdf_name")
    if not pdf_name:
        return []

    entry = _raw_source_manifest_index().get(pdf_name)
    if not entry:
        return [
            {
                "filename": pdf_name,
                "path": _repo_relative_path(DEFAULT_PDF_DIR / pdf_name),
                "doc_type": "datasheet",
                "source": "datasheet_design_context.pdf_name",
            }
        ]

    return [
        {
            "filename": entry.get("filename"),
            "path": _repo_relative_path(REPO_ROOT / "data/raw" / entry["path"]),
            "doc_type": entry.get("doc_type"),
            "storage_tier": entry.get("storage_tier"),
            "vendor_hint": entry.get("vendor_hint"),
            "material_hint": entry.get("material_hint"),
            "sha256": entry.get("sha256"),
            "source": "data/raw/_source_manifest.json",
        }
    ]


def _pin_source_ref(preferred_package: str | None, *pin_groups: list[dict], note: str | None = None) -> dict | None:
    pins = []
    seen = set()
    for group in pin_groups:
        for item in group or []:
            name = item.get("name")
            pin = item.get("pin")
            key = (pin, name)
            if not name or key in seen:
                continue
            seen.add(key)
            pins.append({"pin": pin, "name": name})

    if not pins and not preferred_package:
        return None

    ref = {
        "source": "sch_review_export.packages.pins",
        "package": preferred_package,
        "pins": pins,
    }
    if note:
        ref["note"] = note
    return ref


def _reference_asset_record(path: Path, title: str, summary: str, topics: list[str], applicability: str) -> dict:
    return {
        "title": title,
        "summary": summary,
        "topics": topics,
        "applicability": applicability,
        "source_path": _repo_relative_path(path),
    }


def _gowin_reference_design_assets(device: dict) -> list[dict]:
    if (device.get("manufacturer") or "").lower() != "gowin":
        return []

    mpn = device.get("mpn") or ""
    assets = []
    guide_path = DEFAULT_REFERENCE_DIR / "gowin_gw5at_design_guide.md"
    devboard_path = DEFAULT_REFERENCE_DIR / "gowin_gw5at60_devboard_ref.md"

    if mpn.startswith(("GW5AT", "GW5AST")) and guide_path.exists():
        assets.append(
            _reference_asset_record(
                guide_path,
                "GW5AT schematic guide",
                "UG984 family-level rules for power sequencing, configuration straps, JTAG, clocks, LVDS, and package planning.",
                ["power", "configuration", "JTAG", "clock", "LVDS"],
                "family_guidance",
            )
        )

    if mpn.startswith("GW5AT-60") and devboard_path.exists():
        assets.append(
            _reference_asset_record(
                devboard_path,
                "GW5AT-60 devboard reference",
                "DK_START_GW5AT-LV60UG225 board topology for power tree, config/JTAG, DDR, MIPI, SerDes, and decoupling review.",
                ["devboard", "configuration", "JTAG", "MIPI", "DDR", "SerDes"],
                "topology_reference",
            )
        )

    return assets


def _reference_design_assets(device: dict) -> list[dict]:
    return _gowin_reference_design_assets(device)


def _pin_record(pin_number: str, pin_data: dict) -> dict:
    return {
        "pin": pin_number,
        "name": pin_data.get("name"),
        "direction": pin_data.get("direction"),
        "signal_type": pin_data.get("signal_type"),
        "description": pin_data.get("description"),
        "unused_treatment": pin_data.get("unused_treatment"),
    }


def _group_normal_ic_pins(device: dict, preferred_package: str | None) -> tuple[dict, list[dict]]:
    packages = device.get("packages", {})
    package_data = packages.get(preferred_package or "", {}) if preferred_package else {}
    pins = package_data.get("pins", {})

    groups = {
        "power_inputs": [],
        "grounds": [],
        "power_outputs": [],
        "control_inputs": [],
        "status_outputs": [],
        "sense_and_compensation": [],
        "signal_pins": [],
        "no_connect": [],
    }
    attention_items: list[dict] = []

    for pin_number, pin_data in pins.items():
        record = _pin_record(pin_number, pin_data)
        pin_name = (pin_data.get("name") or "").strip()
        description = pin_data.get("description") or ""
        unused_treatment = pin_data.get("unused_treatment")

        if pin_data.get("direction") == "NC":
            groups["no_connect"].append(record)
        elif _matches_any(pin_name, POWER_PIN_PATTERNS) or pin_data.get("direction") == "POWER_IN":
            if _matches_any(pin_name, GROUND_PIN_PATTERNS):
                groups["grounds"].append(record)
            else:
                groups["power_inputs"].append(record)
        elif _matches_any(pin_name, GROUND_PIN_PATTERNS):
            groups["grounds"].append(record)
        elif _matches_any(pin_name, OUTPUT_PIN_PATTERNS) or (
            pin_data.get("signal_type") == "POWER" and pin_data.get("direction") == "OUTPUT"
        ):
            groups["power_outputs"].append(record)
        elif _matches_any(pin_name, CONTROL_PIN_PATTERNS):
            groups["control_inputs"].append(record)
        elif _matches_any(pin_name, STATUS_PIN_PATTERNS):
            groups["status_outputs"].append(record)
        elif _matches_any(pin_name, SENSE_PIN_PATTERNS):
            groups["sense_and_compensation"].append(record)
        else:
            groups["signal_pins"].append(record)

        if unused_treatment:
            attention_items.append(
                {
                    "pin": pin_number,
                    "name": pin_name,
                    "reason": f"unused_treatment={unused_treatment}",
                    "action": f"Handle unused pin as {unused_treatment}",
                }
            )

        if "do not leave" in description.lower() or "must be connected" in description.lower():
            attention_items.append(
                {
                    "pin": pin_number,
                    "name": pin_name,
                    "reason": "description_requires_connection",
                    "action": description,
                }
            )

        if _contains_any(description, OPEN_DRAIN_HINTS):
            attention_items.append(
                {
                    "pin": pin_number,
                    "name": pin_name,
                    "reason": "open_drain_output",
                    "action": "Check whether an external pull-up is required on this net.",
                }
            )

    return groups, attention_items


def _normal_ic_external_components(device: dict, pin_groups: dict) -> list[dict]:
    category = (device.get("category") or "").lower()
    package_name = _pick_preferred_package(device)
    components = [
        {
            "role": "input_decoupling",
            "designator": "CIN",
            "status": "required",
            "connect_between": ["VIN", "GND"],
            "why": "Every module should start with local input decoupling near the device power pin.",
        }
    ]

    has_feedback = bool(pin_groups["sense_and_compensation"])
    has_power_output = bool(pin_groups["power_outputs"])
    control_names = {item["name"] for item in pin_groups["control_inputs"]}

    if "buck" in category or "boost" in category:
        components.extend(
            [
                {
                    "role": "output_capacitor",
                    "designator": "COUT",
                    "status": "required",
                    "connect_between": ["VOUT", "GND"],
                    "why": "Switching regulators need a local output capacitor for loop stability.",
                },
                {
                    "role": "inductor",
                    "designator": "L1",
                    "status": "required",
                    "connect_between": ["SW", "VOUT"],
                    "why": "Buck/boost topologies require an energy-storage inductor.",
                },
            ]
        )
        if has_feedback:
            components.append(
                {
                    "role": "feedback_divider",
                    "designator": "RFB_TOP/RFB_BOT",
                    "status": "required_if_adjustable",
                    "connect_between": ["VOUT", "FB", "GND"],
                    "why": "Adjustable regulators typically set output voltage with a resistor divider.",
                }
            )
        if "BST" in {item["name"] for item in pin_groups["power_outputs"]}:
            components.append(
                {
                    "role": "bootstrap_capacitor",
                    "designator": "CBST",
                    "status": "check_datasheet",
                    "connect_between": ["BST", "SW"],
                    "why": "Bootstrap capacitor value is topology-specific and should be confirmed in the datasheet.",
                }
            )

    elif "ldo" in category:
        components.append(
            {
                "role": "output_capacitor",
                "designator": "COUT",
                "status": "required",
                "connect_between": ["VOUT", "GND"],
                "why": "LDO stability usually depends on the output capacitor value and ESR window.",
            }
        )
        if has_feedback:
            components.append(
                {
                    "role": "feedback_divider",
                    "designator": "RFB_TOP/RFB_BOT",
                    "status": "required_if_adjustable",
                    "connect_between": ["VOUT", "FB", "GND"],
                    "why": "Adjustable LDO variants require an output-setting divider.",
                }
            )

    elif "opamp" in category or "amplifier" in category or "comparator" in category:
        components.extend(
            [
                {
                    "role": "supply_decoupling",
                    "designator": "CBYP",
                    "status": "required",
                    "connect_between": ["V+", "GND"],
                    "why": "Analog front ends benefit from local high-frequency bypassing.",
                },
                {
                    "role": "feedback_network",
                    "designator": "RIN/RF",
                    "status": "design_specific",
                    "connect_between": ["OUT", "IN-", "signal_in"],
                    "why": "Gain and bandwidth are defined by the feedback network.",
                },
            ]
        )

    if "EN" in control_names or "CE" in control_names:
        components.append(
            {
                "role": "enable_bias",
                "designator": "REN",
                "status": "optional",
                "connect_between": ["EN", "VIN_or_logic"],
                "why": "A bias resistor or logic source prevents ambiguous enable-state bring-up.",
            }
        )

    if package_name and has_power_output and not any(component["role"] == "output_capacitor" for component in components):
        components.append(
            {
                "role": "load_side_decoupling",
                "designator": "CLOAD",
                "status": "recommended",
                "connect_between": ["OUT", "GND"],
                "why": f"{package_name} exposes a power output pin; add local load-side decoupling.",
            }
        )

    return components




def _infer_mcu_traits(device: dict, pin_groups: dict, datasheet_context: dict | None = None) -> dict | None:
    mpn = (device.get("mpn") or "").upper()
    manufacturer = (device.get("manufacturer") or "")
    package_name = _pick_preferred_package(device)
    package_data = (device.get("packages") or {}).get(package_name or "", {})
    pins = package_data.get("pins", {})
    datasheet_context = datasheet_context or {}

    def record(pin_number: str, pin_data: dict) -> dict:
        item = _pin_record(pin_number, pin_data)
        item["description"] = pin_data.get("description")
        return item

    reset_pins = []
    boot_pins = []
    debug_pins = []
    hse_pins = []
    lse_pins = []
    vcap_pins = []
    analog_supply_pins = []
    backup_supply_pins = []
    usb_pins = []
    comm_pins = []

    for pin_number, pin_data in pins.items():
        pin_name = (pin_data.get("name") or "").upper()
        description = (pin_data.get("description") or "").upper()
        item = record(pin_number, pin_data)

        if any(token in pin_name for token in ("NRST", "RESET", "RST")):
            reset_pins.append(item)
        if "BOOT" in pin_name:
            boot_pins.append(item)
        if any(token in pin_name for token in ("SWDIO", "SWCLK", "SWO", "JTMS", "JTCK", "JTDI", "JTDO", "TMS", "TCK", "TDI", "TDO", "TRACESWO")):
            debug_pins.append(item)
        is_lse_pin = any(token in pin_name for token in ("LSE_IN", "LSE_OUT", "OSC32", "PC14", "PC15")) or any(token in description for token in ("LOW SPEED EXTERNAL", "32.768", "LSE"))
        is_hse_pin = (
            any(token in pin_name for token in ("HSE_IN", "HSE_OUT", "OSC_IN", "OSC_OUT", "PH0", "PH1"))
            or "HSE" in description
            or "HIGH-SPEED EXTERNAL" in description
            or ("OSCILLATOR" in description and not is_lse_pin)
        ) and not is_lse_pin
        if is_hse_pin:
            hse_pins.append(item)
        if is_lse_pin:
            lse_pins.append(item)
        if "VCAP" in pin_name:
            vcap_pins.append(item)
        if any(token in pin_name for token in ("VDDA", "VSSA", "VREF+", "VREF-", "VREF")):
            analog_supply_pins.append(item)
        if "VBAT" in pin_name:
            backup_supply_pins.append(item)
        if any(token in pin_name for token in ("USB_DM", "USB_DP", "OTG_FS_DM", "OTG_FS_DP")) or ("USB" in description and any(token in description for token in ("DM", "DP", "D-", "D+"))):
            usb_pins.append(item)
        if any(token in pin_name for token in ("USART", "UART", "I2C", "SPI", "CAN", "FDCAN", "ETH", "SDIO", "ADC", "DAC")) or any(token in description for token in ("USART", "UART", "I2C", "SPI", "CAN", "USB", "ETHERNET", "SDIO", "ADC", "DAC")):
            comm_pins.append(item)

    control_names = {item.get("name", "").upper() for item in pin_groups.get("control_inputs", [])}
    is_stm32 = mpn.startswith("STM32") or manufacturer == "STMicroelectronics"
    has_mcu_markers = any((reset_pins, boot_pins, debug_pins, hse_pins, lse_pins, vcap_pins))
    if not is_stm32 and not has_mcu_markers:
        return None

    return {
        "family": "STM32" if mpn.startswith("STM32") else manufacturer,
        "preferred_package": package_name,
        "reset_pins": reset_pins,
        "boot_pins": boot_pins,
        "debug_pins": debug_pins,
        "hse_pins": hse_pins,
        "lse_pins": lse_pins,
        "vcap_pins": vcap_pins,
        "analog_supply_pins": analog_supply_pins,
        "backup_supply_pins": backup_supply_pins,
        "usb_pins": usb_pins,
        "comm_pins": comm_pins,
        "control_names": sorted(control_names),
        "datasheet_hints": datasheet_context.get("topology_hints", []),
    }


def _mcu_external_components(mcu_context: dict) -> list[dict]:
    components = [
        {
            "role": "supply_decoupling",
            "designator": "CDEC",
            "status": "required",
            "connect_between": ["VDD", "VSS"],
            "why": "Each STM32 supply domain needs local high-frequency decoupling close to the package pins.",
        },
        {
            "role": "swd_header",
            "designator": "JDBG",
            "status": "required",
            "connect_between": ["SWDIO", "SWCLK", "NRST", "VTREF", "GND"],
            "why": "Bring-up and recovery are significantly easier if SWD/JTAG access is exposed from rev A.",
        },
        {
            "role": "reset_bias_or_button",
            "designator": "RRESET/SRESET",
            "status": "recommended",
            "connect_between": ["NRST", "VDD", "GND"],
            "why": "A deterministic reset network avoids ambiguous boot behavior during power-up and programming.",
        },
    ]
    if mcu_context.get("boot_pins"):
        components.append(
            {
                "role": "boot_mode_straps",
                "designator": "RBOOT",
                "status": "required_if_boot_pins_present",
                "connect_between": ["BOOT0", "VDD_or_GND"],
                "why": "Boot straps should be fixed in hardware before firmware and factory programming flow are frozen.",
            }
        )
    if mcu_context.get("hse_pins"):
        components.append(
            {
                "role": "hse_clock_source",
                "designator": "YHSE/CLOAD_HSE",
                "status": "design_specific",
                "connect_between": ["HSE_IN", "HSE_OUT"],
                "why": "Many STM32 designs need an HSE crystal or oscillator footprint to lock debug, USB, or comms timing early.",
            }
        )
    if mcu_context.get("lse_pins"):
        components.append(
            {
                "role": "lse_clock_source",
                "designator": "YLSE/CLOAD_LSE",
                "status": "optional_but_common",
                "connect_between": ["LSE_IN", "LSE_OUT"],
                "why": "RTC and low-power timekeeping usually need a 32.768 kHz source reserved up front.",
            }
        )
    if mcu_context.get("vcap_pins"):
        components.append(
            {
                "role": "vcap_stabilizer",
                "designator": "CVCAP",
                "status": "required_if_vcap_present",
                "connect_between": ["VCAP", "GND"],
                "why": "Internal regulator VCAP pins require the datasheet-specified capacitor and should never be repurposed as normal IO.",
            }
        )
    if mcu_context.get("analog_supply_pins"):
        components.append(
            {
                "role": "analog_rail_filter",
                "designator": "FBANA/CANA",
                "status": "recommended",
                "connect_between": ["VDD", "VDDA"],
                "why": "ADC/DAC/reference performance usually depends on isolating VDDA/VREF from noisy digital rails.",
            }
        )
    if mcu_context.get("backup_supply_pins"):
        components.append(
            {
                "role": "backup_supply_source",
                "designator": "VBAT_SRC",
                "status": "optional",
                "connect_between": ["VBAT", "backup_cell_or_main_rail"],
                "why": "RTC/backup domains need explicit ownership instead of being left floating until late firmware bring-up.",
            }
        )
    if mcu_context.get("usb_pins"):
        components.append(
            {
                "role": "usb_connector_or_esd",
                "designator": "JUSB/UESD",
                "status": "required_if_usb_used",
                "connect_between": ["USB_DP", "USB_DM", "VBUS", "GND"],
                "why": "USB-capable STM32 designs should freeze connector, ESD, and VBUS sensing topology before layout.",
            }
        )
    return components


def _mcu_starter_nets(mcu_context: dict) -> list[dict]:
    nets = [
        {"name": "VDD", "purpose": "primary_digital_supply"},
        {"name": "VSS", "purpose": "digital_ground"},
        {"name": "NRST", "purpose": "system_reset"},
        {"name": "SWDIO", "purpose": "debug_data"},
        {"name": "SWCLK", "purpose": "debug_clock"},
    ]
    if mcu_context.get("boot_pins"):
        nets.append({"name": "BOOT0", "purpose": "boot_mode_strap"})
    if mcu_context.get("hse_pins"):
        nets.extend([
            {"name": "HSE_IN", "purpose": "high_speed_clock_input"},
            {"name": "HSE_OUT", "purpose": "high_speed_clock_output"},
        ])
    if mcu_context.get("lse_pins"):
        nets.extend([
            {"name": "LSE_IN", "purpose": "rtc_clock_input"},
            {"name": "LSE_OUT", "purpose": "rtc_clock_output"},
        ])
    if mcu_context.get("analog_supply_pins"):
        nets.extend([
            {"name": "VDDA", "purpose": "analog_supply"},
            {"name": "VSSA", "purpose": "analog_ground"},
        ])
    if mcu_context.get("vcap_pins"):
        nets.append({"name": "VCAP", "purpose": "internal_regulator_stabilization"})
    if mcu_context.get("backup_supply_pins"):
        nets.append({"name": "VBAT", "purpose": "backup_domain_supply"})
    if mcu_context.get("usb_pins"):
        nets.extend([
            {"name": "USB_DP", "purpose": "usb_full_speed_d_plus"},
            {"name": "USB_DM", "purpose": "usb_full_speed_d_minus"},
            {"name": "VBUS", "purpose": "usb_bus_power_sense"},
        ])
    if any((item.get("name") or "").upper() == "SWO" for item in mcu_context.get("debug_pins", [])):
        nets.append({"name": "SWO", "purpose": "trace_output"})
    return nets


def _mcu_standard_templates(device: dict, mcu_context: dict) -> list[dict]:
    templates = [
        {
            "name": "stm32_minimum_system",
            "label": "STM32 Minimum System",
            "sheet_name": "U1_minimum_system",
            "summary": "Core rails, reset, boot straps, debug header, and mandatory support parts grouped for first-pass bring-up.",
            "recommended_when": "Use for any STM32 design before peripheral-specific daughter sheets split away.",
            "nets": [item["name"] for item in _mcu_starter_nets(mcu_context)],
            "blocks": ["U1", "CDEC", "JDBG", "RRESET/SRESET"] + (["RBOOT"] if mcu_context.get("boot_pins") else []) + (["CVCAP"] if mcu_context.get("vcap_pins") else []),
            "default_refdes_map": {"U1": "U1", "CDEC": "CDEC", "JDBG": "JDBG", "RRESET/SRESET": "RRESET/SRESET"},
            "connections": [
                {"from": "SWDIO", "to": "JDBG", "note": "Keep SWD ownership explicit from day one."},
                {"from": "SWCLK", "to": "JDBG", "note": "Route the debug clock with a deterministic return path."},
                {"from": "NRST", "to": "RRESET/SRESET", "note": "Reset bias and manual reset should live on the root MCU sheet."},
            ],
            "checklist": ["Freeze debug header, reset topology, and boot mode straps before firmware bring-up starts."],
        }
    ]
    if mcu_context.get("usb_pins"):
        templates.append(
            {
                "name": "stm32_usb_device",
                "label": "STM32 USB Device",
                "sheet_name": "U2_usb_device",
                "summary": "USB data pair, VBUS sense, ESD, and connector ownership grouped with the MCU root sheet.",
                "recommended_when": "Use when the STM32 exposes native USB FS/HS device connectivity.",
                "nets": ["USB_DP", "USB_DM", "VBUS", "GND"],
                "blocks": ["U1", "JUSB/UESD"],
                "default_refdes_map": {"U1": "U1", "JUSB/UESD": "JUSB/UESD"},
                "connections": [
                    {"from": "USB_DP", "to": "JUSB/UESD", "note": "Keep the D+ path visible for ESD and connector review."},
                    {"from": "USB_DM", "to": "JUSB/UESD", "note": "Keep the D- path coupled with D+ and the protection network."},
                ],
                "checklist": ["Freeze connector type, VBUS sense method, and ESD placement before layout."],
            }
        )
    return templates


def _choose_default_mcu_template(templates: list[dict]) -> str | None:
    if not templates:
        return None
    return templates[0]["name"]
def _datasheet_component_entries(datasheet_design_context: dict) -> list[dict]:
    grouped: dict[str, dict] = {}
    for hint in datasheet_design_context.get("recommended_external_components", []):
        role = hint.get("role") or "support_part"
        bucket = grouped.setdefault(
            role,
            {
                "role": role,
                "snippets": [],
                "values": [],
                "source_pages": [],
            },
        )
        snippet = hint.get("snippet")
        if snippet and snippet not in bucket["snippets"] and len(bucket["snippets"]) < 2:
            bucket["snippets"].append(snippet)
        preferred_values = []
        if hint.get("value_hint"):
            preferred_values.append(hint.get("value_hint"))
        for value in preferred_values:
            if value and value not in bucket["values"]:
                bucket["values"].append(value)
        source_page = hint.get("source_page")
        if source_page is not None and source_page not in bucket["source_pages"]:
            bucket["source_pages"].append(source_page)

    results = []
    for role, bucket in grouped.items():
        why = bucket["snippets"][0] if bucket["snippets"] else f"See datasheet guidance for {role}."
        if bucket["values"]:
            why = f"{why} Suggested values: {', '.join(bucket['values'][:4])}."
        results.append(
            {
                "role": role,
                "designator": f"AUTO_{role.upper()}",
                "status": "datasheet_hint",
                "connect_between": None,
                "why": why,
                "source_pages": bucket["source_pages"],
                "value_hints": bucket["values"],
            }
        )
    return results


def _build_normal_ic_design_intent(device: dict, datasheet_design_context: dict | None = None) -> dict:
    preferred_package = _pick_preferred_package(device)
    pin_groups, attention_items = _group_normal_ic_pins(device, preferred_package)
    datasheet_design_context = datasheet_design_context or {}
    constraints = _collect_constraints(device, datasheet_design_context=datasheet_design_context)
    category = (device.get("category") or "").lower()
    decoder_device_context = None
    interface_switch_device_context = None
    switch_device_context = None
    mcu_device_context = _infer_mcu_traits(device, pin_groups, datasheet_context=datasheet_design_context)

    datasheet_components = _datasheet_component_entries(datasheet_design_context)
    if _is_decoder_like(device):
        decoder_device_context = _infer_decoder_traits(device, pin_groups, datasheet_context=datasheet_design_context)
        external_components = _decoder_external_components(decoder_device_context)
        noisy_roles = {
            "inductor",
            "feedback_divider",
            "bootstrap_capacitor",
            "current_limit_resistor",
            "dvdt_capacitor",
            "uvlo_divider",
            "ovp_divider",
            "gain_resistor",
            "sense_resistor",
            "snubber_capacitor",
            "snubber_resistor",
            "filter_network",
        }
        datasheet_components = [item for item in datasheet_components if item.get("role") not in noisy_roles]
    elif _is_interface_switch_like(device):
        interface_switch_device_context = _infer_interface_switch_traits(device, datasheet_context=datasheet_design_context)
        external_components = _interface_switch_external_components(interface_switch_device_context)
        noisy_roles = {
            "input_capacitor",
            "output_capacitor",
            "snubber_capacitor",
            "snubber_resistor",
            "filter_network",
        }
        datasheet_components = [item for item in datasheet_components if item.get("role") not in noisy_roles]
    elif _is_signal_switch_like(device):
        switch_device_context = _infer_switch_traits(device, datasheet_context=datasheet_design_context)
        external_components = _switch_external_components(switch_device_context)
        noisy_roles = {
            "input_capacitor",
            "output_capacitor",
            "snubber_capacitor",
            "snubber_resistor",
            "filter_network",
        }
        datasheet_components = [item for item in datasheet_components if item.get("role") not in noisy_roles]
    elif mcu_device_context:
        external_components = _mcu_external_components(mcu_device_context)
    else:
        external_components = _normal_ic_external_components(device, pin_groups)
    external_components.extend(datasheet_components)

    if "opamp" in category or "amplifier" in category or "comparator" in category:
        starter_nets = [
            {"name": "V+", "purpose": "analog_positive_supply"},
            {"name": "GND", "purpose": "module_ground"},
            {"name": "VIN_SIG", "purpose": "analog_input_signal"},
            {"name": "VOUT_ANA", "purpose": "analog_output_signal"},
            {"name": "VREF", "purpose": "analog_reference_or_bias"},
        ]
    elif decoder_device_context:
        starter_nets = _decoder_starter_nets(decoder_device_context)
    elif interface_switch_device_context:
        starter_nets = _interface_switch_starter_nets(interface_switch_device_context)
    elif switch_device_context:
        starter_nets = _switch_starter_nets(switch_device_context)
    elif mcu_device_context:
        starter_nets = _mcu_starter_nets(mcu_device_context)
    else:
        starter_nets = [
            {"name": "VIN", "purpose": "primary_input_supply"},
            {"name": "GND", "purpose": "module_ground"},
        ]
        if pin_groups["power_outputs"]:
            starter_nets.append({"name": "VOUT", "purpose": "regulated_or_power_output"})
        if pin_groups["control_inputs"]:
            starter_nets.append({"name": "EN", "purpose": "enable_or_mode_control"})
        if pin_groups["status_outputs"]:
            starter_nets.append({"name": "PG", "purpose": "status_feedback"})

    return {
        "_schema": BUNDLE_SCHEMA,
        "bundle_layer": "L1_design_intent",
        "device_ref": {
            "mpn": device.get("mpn"),
            "type": device.get("_type"),
            "category": device.get("category"),
            "manufacturer": device.get("manufacturer"),
            "preferred_package": preferred_package,
            "packages": sorted(device.get("packages", {}).keys()),
        },
        "pin_groups": pin_groups,
        "attention_items": attention_items,
        "constraints": constraints,
        "external_components": external_components,
        "starter_nets": starter_nets,
        "decoder_device_context": decoder_device_context,
        "interface_switch_device_context": interface_switch_device_context,
        "switch_device_context": switch_device_context,
        "mcu_device_context": mcu_device_context,
        "datasheet_design_context": datasheet_design_context,
    }


def _fpga_high_speed_semantic_context(device: dict) -> dict:
    refclk_requirements = ((device.get("constraint_blocks") or {}).get("refclk_requirements") or {})
    lane_groups = refclk_requirements.get("lane_group_mappings") or []
    refclk_pairs = refclk_requirements.get("refclk_pairs") or []
    if not lane_groups and not refclk_pairs:
        return {}

    scenario_candidates = []
    bundle_tags = []
    use_case_tags = []
    protocol_candidates = []

    def add_unique(target: list[str], values) -> None:
        for value in values or []:
            if value and value not in target:
                target.append(value)

    for group in lane_groups:
        add_unique(scenario_candidates, group.get("bundle_scenario_candidates") or [])
        add_unique(bundle_tags, group.get("bundle_tags") or [])
        add_unique(use_case_tags, group.get("use_case_tags") or [])
        add_unique(protocol_candidates, group.get("candidate_protocols") or [])
    for pair in refclk_pairs:
        add_unique(scenario_candidates, pair.get("bundle_scenario_candidates") or [])
        add_unique(bundle_tags, pair.get("bundle_tags") or [])
        add_unique(use_case_tags, pair.get("use_case_tags") or [])
        add_unique(protocol_candidates, pair.get("candidate_protocols") or [])

    return {
        "lane_groups": lane_groups,
        "refclk_pairs": refclk_pairs,
        "scenario_candidates": scenario_candidates,
        "bundle_tags": bundle_tags,
        "use_case_tags": use_case_tags,
        "protocol_candidates": protocol_candidates,
        "source": "sch_review_export.constraint_blocks.refclk_requirements",
    }


def _build_fpga_design_intent(device: dict, datasheet_design_context: dict | None = None) -> dict:
    pins = device.get("pins", [])
    grouped = {
        "power_pins": [],
        "ground_pins": [],
        "config_pins": [],
        "io_pins": [],
        "special_pins": [],
    }
    attention_items = []

    for pin in pins:
        record = {
            "pin": pin.get("pin"),
            "name": pin.get("name"),
            "function": pin.get("function"),
            "bank": pin.get("bank"),
            "drc": pin.get("drc"),
        }
        function = pin.get("function")
        if function in {"POWER", "GT_POWER"}:
            grouped["power_pins"].append(record)
        elif function in {"GROUND", "RSVDGND"}:
            grouped["ground_pins"].append(record)
        elif function == "CONFIG":
            grouped["config_pins"].append(record)
        elif function == "IO":
            grouped["io_pins"].append(record)
        else:
            grouped["special_pins"].append(record)

        drc = pin.get("drc") or {}
        if drc.get("must_connect"):
            attention_items.append(
                {
                    "pin": pin.get("pin"),
                    "name": pin.get("name"),
                    "reason": "drc_requires_connection",
                    "action": drc,
                }
            )

    power_rails = []
    for rail_name, rail in sorted((device.get("power_rails") or {}).items()):
        power_rails.append(
            {
                "name": rail_name,
                "description": rail.get("description"),
                "nominal": rail.get("nominal") or rail.get("voltage") or rail.get("value"),
                "source": rail.get("source"),
            }
        )

    high_speed_semantic_context = _fpga_high_speed_semantic_context(device)
    customer_scenarios = _fpga_customer_scenarios(device, {
        "pin_groups": grouped,
        "power_rails": power_rails,
        "high_speed_semantic_context": high_speed_semantic_context,
    })
    vendor_design_rules = _gowin_family_design_rules(device)
    reference_design_assets = _reference_design_assets(device)
    fpga_context = {"pin_groups": grouped, "power_rails": power_rails, "high_speed_semantic_context": high_speed_semantic_context}
    external_components = _fpga_external_components(device, fpga_context, customer_scenarios)
    starter_nets = _fpga_starter_nets(device, fpga_context, customer_scenarios)

    return {
        "_schema": BUNDLE_SCHEMA,
        "bundle_layer": "L1_design_intent",
        "device_ref": {
            "mpn": device.get("mpn"),
            "type": device.get("_type"),
            "category": device.get("category"),
            "manufacturer": device.get("manufacturer"),
            "package": device.get("package"),
        },
        "pin_groups": grouped,
        "power_rails": power_rails,
        "banks": device.get("banks"),
        "diff_pairs": device.get("diff_pairs"),
        "attention_items": attention_items,
        "external_components": external_components,
        "datasheet_design_context": datasheet_design_context or {},
        "high_speed_semantic_context": high_speed_semantic_context,
        "customer_scenarios": customer_scenarios,
        "vendor_design_rules": vendor_design_rules,
        "reference_design_assets": reference_design_assets,
        "starter_nets": starter_nets,
    }


def _gowin_family_design_rules(device: dict) -> dict:
    if (device.get("manufacturer") or "").lower() != "gowin":
        return {}

    mpn = (device.get("mpn") or "").upper()
    is_littlebee = mpn.startswith("GW1N") or mpn.startswith("GW1NR")
    is_arora = mpn.startswith("GW2A") or "ARORA" in mpn or mpn.startswith("GW5")

    config_rules = [
        "`RECONFIG_N` 上电期间保持高电平，稳定后再允许重配置。",
        "`DONE` / `READY` 作为状态脚时默认预留上拉，量产前冻结其复用方式。",
        "`MODE[2:0]`、`JTAGSEL`、`MSPI/SSPI` 启动拓扑在原理图阶段一次定版，不要等 PCB 后补。",
        "配置接口若走 `I2C` / `SSPI` / `MSPI`，相关 `SCL/SDA/CLK/CS` 拉阻和主从归属必须写进页注释。",
    ]
    if is_littlebee:
        config_rules.append("LittleBee 系列常见为 `JTAG + Autoboot/SSPI/MSPI`，需提前确认模式脚默认电平与 Flash 上电时序。")
    if is_arora:
        config_rules.append("Arora / GW5 / GW2A 若启用高速接口，配置模式与高速 refclk、电源域分区一起评审。")

    clock_rules = [
        "系统时钟优先走专用 `GCLK/PLL` 管脚；外部晶振或有源时钟源按磁珠 + 去耦预留。",
        "`TCK` 默认预留上拉到对应 `VCCIO` 域，并保持 JTAG header 回路最短。",
    ]
    if is_arora:
        clock_rules.append("SerDes / MIPI 高速参考时钟靠近 FPGA 管脚处预留 AC 耦合与测试点。")

    return {
        "power_rules": [
            "按器件手册冻结 `VCC` / `VCCX` / `VCCIO` / 模拟电源的上电顺序与斜率。",
            "MIPI / SerDes / PLL 等模拟与数字电源优先低噪声分区，跨域避免直接硬并。",
            "不同 Bank 的 `VCCIO` 先定电压，再做 pin swap、接口分配和 connector 映射。",
        ],
        "config_rules": config_rules,
        "clock_rules": clock_rules,
        "io_rules": [
            "LVDS / DDR / MIPI / SerDes 相关管脚优先按 byte-lane 或 lane 组整体分区。",
            "开发板参考设计里的 Bank 电压、终端和 strap 做法优先复用，不同物料不要混搭同类参考文件。",
        ],
    }


def _fpga_customer_scenarios(device: dict, design_intent: dict) -> list[dict]:
    pins = device.get("pins", [])
    diff_pairs = device.get("diff_pairs", []) or []
    power_rails = design_intent.get("power_rails", []) or []
    power_rail_names = {item.get("name") or "" for item in power_rails}
    pin_names = {pin.get("name") or "" for pin in pins}
    special_names = {pin.get("name") or "" for pin in design_intent.get("pin_groups", {}).get("special_pins", [])}
    high_speed_semantic_context = design_intent.get("high_speed_semantic_context", {}) or {}
    semantic_scenario_candidates = set(high_speed_semantic_context.get("scenario_candidates", []) or [])
    semantic_protocols = high_speed_semantic_context.get("protocol_candidates", []) or []
    semantic_bundle_tags = set(high_speed_semantic_context.get("bundle_tags", []) or [])
    semantic_use_case_tags = set(high_speed_semantic_context.get("use_case_tags", []) or [])
    scenarios = []
    seen = set()

    def add(name: str, label: str, why: str, nets: list[dict], blocks: list[dict], todo: list[str]) -> None:
        if name in seen:
            return
        seen.add(name)
        scenarios.append(
            {
                "name": name,
                "label": label,
                "why": why,
                "nets": nets,
                "blocks": blocks,
                "todo": todo,
            }
        )

    has_config = any(pin.get("function") == "CONFIG" for pin in pins)
    has_spi_cfg = any(any(token in (pin.get("name") or "") for token in ("SSPI", "CCLK", "DONE", "RECONFIG", "MODE")) for pin in pins)
    if has_config or has_spi_cfg:
        add(
            "qspi_jtag_bringup",
            "QSPI / JTAG Bring-Up",
            "Customer bring-up usually starts with a deterministic boot mode, programming header, and local config flash footprint.",
            [
                {"name": "JTAG", "purpose": "programming_and_debug"},
                {"name": "CFG_SPI", "purpose": "configuration_flash_bus"},
                {"name": "DONE", "purpose": "configuration_status"},
                {"name": "RECONFIG_N", "purpose": "reconfiguration_control"},
                {"name": "MODE_STRAP", "purpose": "boot_mode_selection"},
            ],
            [
                {"ref": "JCFG", "type": "connector", "role": "configuration_header"},
                {"ref": "UCFG", "type": "memory", "role": "configuration_flash"},
                {"ref": "RMODE", "type": "support_component", "role": "boot_mode_straps"},
            ],
            ["Freeze boot mode, flash size, and programming header ownership before schematic review."],
        )

    has_mipi = any("mipi" in name.lower() for name in special_names | power_rail_names)
    if has_mipi:
        add(
            "mipi_camera_bridge",
            "MIPI Camera Bridge",
            "Camera-centric customers need sensor connector, MIPI rail planning, and control bus grouped as one module boundary.",
            [
                {"name": "MIPI_CLK", "purpose": "camera_clock_lane"},
                {"name": "MIPI_DATA", "purpose": "camera_data_lanes"},
                {"name": "CAM_I2C", "purpose": "camera_control_bus"},
                {"name": "CAM_RESET_N", "purpose": "camera_reset"},
            ],
            [
                {"ref": "JCAM", "type": "connector", "role": "mipi_camera_connector"},
                {"ref": "PMIPI", "type": "power_block", "role": "mipi_rail_group"},
                {"ref": "RCAM", "type": "support_component", "role": "camera_control_pullups"},
            ],
            ["Freeze sensor lane count, connector pinout, and shared control bus topology before layout."],
        )

    if len(diff_pairs) >= 8:
        add(
            "lvds_io_expansion",
            "LVDS / Bank Expansion",
            "Many customer designs use Gowin devices as LVDS data concentrators or bank-level IO bridges.",
            [
                {"name": "LVDS_IO", "purpose": "differential_io_bundle"},
                {"name": "BANK_VCCIO", "purpose": "io_bank_supply"},
            ],
            [
                {"ref": "JLVDS", "type": "connector", "role": "lvds_io_connector"},
                {"ref": "TPBANK", "type": "testpoint", "role": "bank_voltage_testpoints"},
            ],
            ["Freeze each VCCIO bank voltage and diff-pair ownership before pin assignment freeze."],
        )

    has_serdes = any(re.search(r"Q\d+_LN\d+_(?:RX|TX)", name) for name in special_names)
    if has_serdes or "high_speed_link_bridge" in semantic_scenario_candidates or "high_speed_link" in semantic_use_case_tags:
        why = "Customers using transceiver-capable packages need refclk, AC-coupling, and link connector partitioned up front."
        if semantic_protocols:
            why = f"High-speed lane groups already export protocol candidates ({', '.join(semantic_protocols[:6])}); bind those groups to connectors and refclk sources early."
        todo = ["Freeze link standard, refclk frequency, and AC-coupling placement before stack-up review."]
        if semantic_protocols:
            todo.insert(0, f"Freeze protocol ownership per lane group from exported candidates: {', '.join(semantic_protocols[:6])}.")
        hs_nets = [
            {"name": "REFCLK", "purpose": "serdes_reference_clock"},
            {"name": "SERDES_RX", "purpose": "high_speed_receive_lanes"},
            {"name": "SERDES_TX", "purpose": "high_speed_transmit_lanes"},
        ]
        hs_blocks = [
            {"ref": "JHS", "type": "connector", "role": "high_speed_link_connector"},
            {"ref": "XO1", "type": "timing_source", "role": "reference_clock_source"},
            {"ref": "CACHS", "type": "support_component", "role": "ac_coupling_network"},
        ]
        if "pcie_link" in semantic_use_case_tags:
            hs_nets.extend([
                {"name": "PCIE_REFCLK", "purpose": "pcie_reference_clock"},
                {"name": "PCIE_TXRX", "purpose": "pcie_lane_bundle"},
            ])
            hs_blocks.extend([
                {"ref": "JPCIE", "type": "connector", "role": "pcie_link_boundary"},
                {"ref": "XPCIE", "type": "timing_source", "role": "pcie_refclk_source_or_buffer"},
            ])
        if "ethernet_link" in semantic_use_case_tags:
            hs_nets.extend([
                {"name": "ETH_REFCLK", "purpose": "ethernet_serdes_reference_clock"},
                {"name": "ETH_SERDES", "purpose": "ethernet_serdes_lane_bundle"},
            ])
            hs_blocks.append({"ref": "JETH/SFP/UETH", "type": "connector", "role": "ethernet_serdes_attachment"})
        if "custom_serdes" in semantic_use_case_tags:
            hs_nets.extend([
                {"name": "SERDES_USER_REFCLK", "purpose": "custom_serdes_reference_clock"},
                {"name": "SERDES_USER_DATA", "purpose": "custom_serdes_lane_bundle"},
            ])
            hs_blocks.append({"ref": "JHSUSR", "type": "connector", "role": "custom_serdes_breakout"})
        add(
            "high_speed_link_bridge",
            "High-Speed Link Bridge",
            why,
            hs_nets,
            hs_blocks,
            todo,
        )
        scenarios[-1]["source"] = "semantic_export" if semantic_protocols else "pin_inference"
        if semantic_protocols:
            scenarios[-1]["protocol_candidates"] = semantic_protocols
            scenarios[-1]["bundle_tags"] = sorted(semantic_bundle_tags)
            scenarios[-1]["use_case_tags"] = sorted(semantic_use_case_tags)
            scenarios[-1]["lane_group_refs"] = [group.get("group_id") for group in high_speed_semantic_context.get("lane_groups", []) if group.get("group_id")]

    dqs_count = sum(1 for pin in pins if pin.get("dqs"))
    if dqs_count >= 8:
        add(
            "ddr_memory_interface",
            "DDR Memory Interface",
            "Memory-oriented customers need byte-lane grouping, VCCIO planning, and memory footprint placeholders early.",
            [
                {"name": "DDR_CLK", "purpose": "memory_clock"},
                {"name": "DDR_ADDR", "purpose": "memory_address_command"},
                {"name": "DDR_DQ", "purpose": "memory_data_bus"},
                {"name": "DDR_DQS", "purpose": "memory_strobes"},
            ],
            [
                {"ref": "UDDR", "type": "memory", "role": "external_memory"},
                {"ref": "RTERM_DDR", "type": "support_component", "role": "memory_termination_review"},
            ],
            ["Freeze memory width, byte-lane placement, and bank voltage compatibility before PCB floorplanning."],
        )

    return scenarios


def _high_speed_bundle_families(high_speed_semantic_context: dict | None) -> set[str]:
    use_case_tags = set((high_speed_semantic_context or {}).get("use_case_tags") or [])
    families = set()
    if "pcie_link" in use_case_tags:
        families.add("pcie")
    if "ethernet_link" in use_case_tags:
        families.add("ethernet")
    if "custom_serdes" in use_case_tags:
        families.add("custom")
    return families


def _high_speed_lane_group_nets(high_speed_semantic_context: dict | None) -> list[dict]:
    nets = []
    for group in (high_speed_semantic_context or {}).get("lane_groups", []) or []:
        group_id = group.get("group_id")
        if not group_id:
            continue
        nets.append({"name": f"HS_{group_id}_RX", "purpose": f"lane_group_{group_id}_receive_bundle"})
        nets.append({"name": f"HS_{group_id}_TX", "purpose": f"lane_group_{group_id}_transmit_bundle"})
        if group.get("refclk_pair_names"):
            nets.append({"name": f"HS_{group_id}_REFCLK", "purpose": f"lane_group_{group_id}_reference_clock"})
    return nets


def _fpga_external_components(device: dict, design_intent: dict, scenarios: list[dict]) -> list[dict]:
    components = [
        {
            "role": "rail_decoupling",
            "designator": "Cbulk/Cdecap",
            "status": "required",
            "connect_between": ["each_power_rail", "nearest_ground"],
            "why": "Every FPGA rail requires distributed bulk and high-frequency decoupling.",
        },
        {
            "role": "configuration_header",
            "designator": "JCFG",
            "status": "recommended",
            "connect_between": ["JTAG_or_config_pins"],
            "why": "Bring-up is significantly faster if programming/debug pins are exposed early.",
        },
    ]
    names = {item["name"] for item in scenarios}
    high_speed_semantic_context = design_intent.get("high_speed_semantic_context", {}) or {}
    high_speed_families = _high_speed_bundle_families(high_speed_semantic_context)
    if "qspi_jtag_bringup" in names:
        components.extend(
            [
                {
                    "role": "configuration_flash",
                    "designator": "UCFG",
                    "status": "recommended",
                    "connect_between": ["CFG_SPI", "FPGA_config_pins"],
                    "why": "Most customer boards need a local nonvolatile image source for production bring-up.",
                },
                {
                    "role": "boot_mode_straps",
                    "designator": "RMODE",
                    "status": "required",
                    "connect_between": ["MODE_pins", "VCCIO_or_GND"],
                    "why": "Boot mode straps must be deterministic before first power-up.",
                },
            ]
        )
    if "mipi_camera_bridge" in names:
        components.extend(
            [
                {
                    "role": "mipi_camera_connector",
                    "designator": "JCAM",
                    "status": "design_specific",
                    "connect_between": ["MIPI_CLK/MIPI_DATA", "camera_module"],
                    "why": "Camera customers usually need a fixed sensor mezzanine or FFC connector boundary.",
                },
                {
                    "role": "mipi_rail_filter",
                    "designator": "PMIPI",
                    "status": "recommended",
                    "connect_between": ["MIPI_power_rails", "local_ground"],
                    "why": "MIPI analog rails benefit from explicit filtering and local decoupling partitions.",
                },
            ]
        )
    if "lvds_io_expansion" in names:
        components.append(
            {
                "role": "lvds_io_connector",
                "designator": "JLVDS",
                "status": "design_specific",
                "connect_between": ["LVDS_IO", "remote_adc_or_sensor"],
                "why": "Expose grouped differential pairs at a stable boundary so bank ownership stays reviewable.",
            }
        )
    if "high_speed_link_bridge" in names:
        components.extend(
            [
                {
                    "role": "reference_clock_source",
                    "designator": "XO1",
                    "status": "recommended",
                    "connect_between": ["REFCLK", "GT_refclk_input"],
                    "why": "High-speed links need a clearly owned low-jitter reference clock source.",
                },
                {
                    "role": "high_speed_link_connector",
                    "designator": "JHS",
                    "status": "design_specific",
                    "connect_between": ["SERDES_RX/SERDES_TX", "backplane_or_mezzanine"],
                    "why": "Link connector placement drives lane escape and AC-coupling ownership.",
                },
            ]
        )
        if "pcie" in high_speed_families:
            components.extend(
                [
                    {
                        "role": "pcie_link_boundary",
                        "designator": "JPCIE",
                        "status": "design_specific",
                        "connect_between": ["PCIE_TXRX", "slot_or_peer_device"],
                        "why": "PCIe-capable lane groups should terminate at an explicit card-edge, connector, or peer-device boundary in the schematic.",
                    },
                    {
                        "role": "pcie_refclk_source_or_buffer",
                        "designator": "XPCIE",
                        "status": "recommended",
                        "connect_between": ["PCIE_REFCLK", "HS_lane_groups"],
                        "why": "PCIe review needs an explicit 100 MHz reference-clock ownership point and any required fanout/buffer decision.",
                    },
                ]
            )
        if "ethernet" in high_speed_families:
            components.append(
                {
                    "role": "ethernet_serdes_attachment",
                    "designator": "JETH/SFP/UETH",
                    "status": "design_specific",
                    "connect_between": ["ETH_SERDES", "phy_or_cage_or_peer_link"],
                    "why": "Ethernet-oriented SerDes designs need a clear attachment point such as an SFP cage, PHY, or direct link peer.",
                }
            )
        if "custom" in high_speed_families:
            components.append(
                {
                    "role": "custom_serdes_breakout",
                    "designator": "JHSUSR",
                    "status": "design_specific",
                    "connect_between": ["SERDES_USER_DATA", "custom_link_partner"],
                    "why": "Custom SerDes mode still needs an explicit boundary so lane ownership and AC-coupling policy stay reviewable.",
                }
            )
    if "ddr_memory_interface" in names:
        components.append(
            {
                "role": "memory_connector_or_footprint",
                "designator": "UDDR",
                "status": "design_specific",
                "connect_between": ["DDR_bus", "external_memory"],
                "why": "Memory-oriented projects need the downstream DRAM footprint represented in the first schematic partition.",
            }
        )
    return components


def _fpga_starter_nets(device: dict, design_intent: dict, scenarios: list[dict]) -> list[dict]:
    nets = [
        {"name": "VCCINT", "purpose": "core_supply_placeholder"},
        {"name": "VCCIO", "purpose": "io_bank_supply_placeholder"},
        {"name": "GND", "purpose": "reference_ground"},
        {"name": "JTAG", "purpose": "bring_up_and_debug"},
    ]
    for scenario in scenarios:
        for net in scenario.get("nets", []):
            if not any(item.get("name") == net["name"] for item in nets):
                nets.append(net)

    high_speed_semantic_context = design_intent.get("high_speed_semantic_context", {}) or {}
    high_speed_families = _high_speed_bundle_families(high_speed_semantic_context)
    extra_nets = _high_speed_lane_group_nets(high_speed_semantic_context)
    if "pcie" in high_speed_families:
        extra_nets.extend([
            {"name": "PCIE_REFCLK", "purpose": "pcie_reference_clock"},
            {"name": "PCIE_TXRX", "purpose": "pcie_lane_bundle"},
        ])
    if "ethernet" in high_speed_families:
        extra_nets.extend([
            {"name": "ETH_REFCLK", "purpose": "ethernet_serdes_reference_clock"},
            {"name": "ETH_SERDES", "purpose": "ethernet_serdes_lane_bundle"},
        ])
    if "custom" in high_speed_families:
        extra_nets.extend([
            {"name": "SERDES_USER_REFCLK", "purpose": "custom_serdes_reference_clock"},
            {"name": "SERDES_USER_DATA", "purpose": "custom_serdes_lane_bundle"},
        ])
    for net in extra_nets:
        if not any(item.get("name") == net["name"] for item in nets):
            nets.append(net)
    return nets


def _choose_default_fpga_template(fpga_templates: list[dict]) -> str | None:
    if not fpga_templates:
        return None
    names = {item.get("name") for item in fpga_templates}
    for preferred in ("mipi_camera_bridge", "high_speed_link_bridge", "qspi_jtag_bringup", "ddr_memory_interface", "lvds_io_expansion"):
        if preferred in names:
            return preferred
    return fpga_templates[0].get("name")


def _fpga_standard_templates(device: dict, design_intent: dict, scenarios: list[dict]) -> list[dict]:
    templates = []

    def add_template(name: str, label: str, sheet_name: str, summary: str, recommended_when: str, nets: list[str], blocks: list[str], connections: list[dict], checklist: list[str]) -> None:
        templates.append(
            {
                "name": name,
                "label": label,
                "sheet_name": sheet_name,
                "summary": summary,
                "recommended_when": recommended_when,
                "nets": nets,
                "blocks": blocks,
                "default_refdes_map": {block: block for block in blocks},
                "connections": connections,
                "checklist": checklist,
            }
        )

    scenario_names = {item["name"] for item in scenarios}
    scenario_by_name = {item["name"]: item for item in scenarios}
    if "qspi_jtag_bringup" in scenario_names:
        add_template(
            "qspi_jtag_bringup",
            "QSPI / JTAG Bring-Up",
            "F1_qspi_bringup",
            "Boot source, mode straps, and programming header grouped around one production-friendly FPGA bring-up sheet.",
            "Use when the board needs local config flash or repeatable factory programming.",
            ["JTAG", "CFG_SPI", "DONE", "RECONFIG_N", "MODE_STRAP"],
            ["U1", "JCFG", "UCFG", "RMODE"],
            [
                {"from": "JTAG", "to": "JCFG", "note": "Expose programming/debug access without opening the main IO connector set."},
                {"from": "CFG_SPI", "to": "UCFG", "note": "Keep configuration flash on the same sheet as boot pins for review clarity."},
                {"from": "MODE_STRAP", "to": "RMODE", "note": "Document strap polarity before board release."},
            ],
            ["Freeze boot mode and flash image path before pin assignment freeze."],
        )
    if "mipi_camera_bridge" in scenario_names:
        add_template(
            "mipi_camera_bridge",
            "MIPI Camera Bridge",
            "F2_mipi_camera_bridge",
            "Camera connector, control bus, and MIPI rail planning grouped for fast sensor bring-up.",
            "Use when the Gowin FPGA sits between image sensors and the rest of the system.",
            ["MIPI_CLK", "MIPI_DATA", "CAM_I2C", "CAM_RESET_N"],
            ["U1", "JCAM", "PMIPI", "RCAM"],
            [
                {"from": "MIPI_CLK", "to": "JCAM", "note": "Keep lane ownership explicit at the sensor connector."},
                {"from": "MIPI_DATA", "to": "JCAM", "note": "Bundle data lanes with consistent polarity naming before layout."},
                {"from": "CAM_I2C", "to": "RCAM", "note": "Bias shared control bus close to the FPGA or bridge MCU domain."},
            ],
            ["Freeze lane count, connector pinout, and reset polarity before schematic review."],
        )
    if "lvds_io_expansion" in scenario_names:
        add_template(
            "lvds_io_expansion",
            "LVDS / Bank Expansion",
            "F3_lvds_io_expansion",
            "Differential IO bank breakout grouped so connector ownership and VCCIO planning are visible early.",
            "Use when the FPGA is acting as a sensor concentrator or fast GPIO bridge.",
            ["LVDS_IO", "BANK_VCCIO"],
            ["U1", "JLVDS", "TPBANK"],
            [
                {"from": "LVDS_IO", "to": "JLVDS", "note": "Group customer-facing diff pairs at a stable boundary."},
                {"from": "BANK_VCCIO", "to": "TPBANK", "note": "Expose bank-voltage ownership for bring-up and rework."},
            ],
            ["Freeze bank voltage plan before finalizing connector pin swaps."],
        )
    if "high_speed_link_bridge" in scenario_names:
        semantic = scenario_by_name.get("high_speed_link_bridge", {})
        protocol_candidates = semantic.get("protocol_candidates", [])
        lane_group_refs = semantic.get("lane_group_refs", [])
        protocol_suffix = f" Protocol candidates: {', '.join(protocol_candidates[:6])}." if protocol_candidates else ""
        lane_group_suffix = f" Lane groups: {', '.join(lane_group_refs[:8])}." if lane_group_refs else ""
        template_nets = [item.get("name") for item in semantic.get("nets", []) if item.get("name")]
        template_blocks = ["U1"] + [item.get("ref") for item in semantic.get("blocks", []) if item.get("ref")]
        template_connections = [
            {"from": "REFCLK", "to": "XO1", "note": "Fix the refclk source against the exported protocol candidates before routing or SI review."},
            {"from": "SERDES_RX", "to": "JHS", "note": "Document ingress lane ownership per exported lane group."},
            {"from": "SERDES_TX", "to": "JHS", "note": "Keep egress lanes adjacent to AC-coupling network placeholders and lane-group boundaries."},
        ]
        template_checklist = [
            "Freeze link standard, refclk frequency, and AC-coupling placement before layout.",
            *([f"Freeze protocol ownership for exported lane groups: {', '.join(lane_group_refs[:8])}."] if lane_group_refs else []),
            *([f"Review candidate protocols from export: {', '.join(protocol_candidates[:6])}."] if protocol_candidates else []),
        ]
        if "PCIE_REFCLK" in template_nets:
            template_connections.extend([
                {"from": "PCIE_REFCLK", "to": "XPCIE", "note": "Bind PCIe-capable groups to the explicit 100 MHz clock source or buffer boundary."},
                {"from": "PCIE_TXRX", "to": "JPCIE", "note": "Keep PCIe lane ownership visible at the connector or slot boundary and freeze lane width."},
            ])
            template_checklist.extend([
                "Freeze PCIe-capable lane-group ownership and REFCLK topology against the exported protocol candidates before sign-off.",
                "Review PCIe AC-coupling placement, reset/perst ownership, and connector-or-endpoint boundary.",
            ])
        if "ETH_REFCLK" in template_nets:
            template_connections.extend([
                {"from": "ETH_REFCLK", "to": "XO1/JETH/SFP/UETH", "note": "Bind Ethernet-capable groups to one of the exported Ethernet reference-clock candidates and make the attachment explicit."},
                {"from": "ETH_SERDES", "to": "JETH/SFP/UETH", "note": "Show whether Ethernet-capable groups land on SFP, PHY, or peer-link attachment."},
            ])
            template_checklist.extend([
                "Freeze Ethernet attachment style (PHY, backplane, direct link, or SFP cage) before schematic release.",
                "Review exported Ethernet reference-clock ownership and any required attachment sideband signals before sign-off.",
            ])
        if "SERDES_USER_REFCLK" in template_nets:
            template_connections.extend([
                {"from": "SERDES_USER_REFCLK", "to": "JHSUSR/XO1", "note": "Document the custom-link reference-clock producer and consumer explicitly."},
                {"from": "SERDES_USER_DATA", "to": "JHSUSR", "note": "Keep custom SerDes ownership explicit even when no standard protocol is frozen yet."},
            ])
            template_checklist.extend([
                "Freeze custom SerDes lane-group ownership, refclk producer/consumer, and polarity policy before layout review.",
            ])
        add_template(
            "high_speed_link_bridge",
            "High-Speed Link Bridge",
            "F4_high_speed_link_bridge",
            f"SerDes connector, AC-coupling, and refclk source grouped for signal-integrity review.{protocol_suffix}{lane_group_suffix}",
            "Use when exported high-speed lane groups require protocol/refclk ownership to be frozen early.",
            template_nets,
            template_blocks,
            template_connections,
            template_checklist,
        )
        templates[-1]["protocol_candidates"] = protocol_candidates
        templates[-1]["lane_group_refs"] = lane_group_refs
        templates[-1]["bundle_tags"] = semantic.get("bundle_tags", [])
        templates[-1]["use_case_tags"] = semantic.get("use_case_tags", [])
    if "ddr_memory_interface" in scenario_names:
        add_template(
            "ddr_memory_interface",
            "DDR Memory Interface",
            "F5_ddr_memory_interface",
            "Memory footprint and byte-lane grouping captured as a dedicated first-pass FPGA memory sheet.",
            "Use when the device acts as a frame buffer, soft CPU, or bandwidth-heavy compute node.",
            ["DDR_CLK", "DDR_ADDR", "DDR_DQ", "DDR_DQS"],
            ["U1", "UDDR", "RTERM_DDR"],
            [
                {"from": "DDR_CLK", "to": "UDDR", "note": "Lock the memory clock topology before byte-lane routing starts."},
                {"from": "DDR_DQ", "to": "UDDR", "note": "Preserve byte-lane grouping between schematic and PCB placement."},
                {"from": "DDR_DQS", "to": "UDDR", "note": "Keep strobe ownership visible for timing review."},
            ],
            ["Freeze memory width and bank mapping before finalizing pin constraints."],
        )
    return templates


def build_design_intent(device: dict, datasheet_design_context: dict | None = None) -> dict:
    if device.get("_type") == "fpga":
        return _build_fpga_design_intent(device, datasheet_design_context=datasheet_design_context)
    return _build_normal_ic_design_intent(device, datasheet_design_context=datasheet_design_context)


def _append_net_once(nets: list[dict], name: str, purpose: str) -> None:
    if any(net.get("name") == name for net in nets):
        return
    nets.append({"name": name, "purpose": purpose})


def _append_block_once(blocks: list[dict], ref: str, block_type: str, role: str, **extra) -> None:
    if any(block.get("ref") == ref for block in blocks):
        return
    record = {"ref": ref, "type": block_type, "role": role}
    record.update(extra)
    blocks.append(record)


def _is_decoder_like(device: dict) -> bool:
    text = " ".join(
        [
            device.get("mpn") or "",
            device.get("category") or "",
            device.get("description") or "",
        ]
    ).lower()
    if "translator" in text and "decoder" not in text and "deserializer" not in text:
        return False
    return any(keyword in text for keyword in ("decoder", "deserializer", "gmsl", "csi-2", "csi2", "mipi", "hd-tvi", "cvbs", "fpd-link", "parallel cmos"))


def _is_signal_switch_like(device: dict) -> bool:
    category = (device.get("category") or "").lower()
    if category != "switch":
        return False

    text = " ".join(
        [
            device.get("mpn") or "",
            device.get("description") or "",
            device.get("category") or "",
        ]
    ).lower()
    if any(
        token in text
        for token in (
            "efuse",
            "load switch",
            "power switch",
            "power mux",
            "power multiplexer",
            "ideal diode",
            "high-side",
            "current-limited",
            "power-distribution",
            "reverse polarity",
        )
    ):
        return False
    if any(token in text for token in ("usb", "pcie", "displayport", "superspeed")):
        return False

    preferred_package = _pick_preferred_package(device)
    package_data = device.get("packages", {}).get(preferred_package or "", {}) if preferred_package else {}
    pins = package_data.get("pins", {})
    names = [pin.get("name") or "" for pin in pins.values()]
    source_count = sum(1 for name in names if re.match(r"^S\d+[A-Z]?$", name.upper()))
    drain_count = sum(1 for name in names if re.match(r"^D\d+[A-Z]?$", name.upper()) or name.upper() in {"D", "DA", "DB"})

    return (source_count >= 4 and drain_count >= 1) or any(
        token in text for token in ("analog switch", "matrix switch", "multiplexer", "demultiplexer", "spst switch")
    )


def _infer_switch_traits(device: dict, datasheet_context: dict | None = None) -> dict:
    preferred_package = _pick_preferred_package(device)
    package_data = device.get("packages", {}).get(preferred_package or "", {}) if preferred_package else {}
    pins = package_data.get("pins", {})
    datasheet_context = datasheet_context or {}

    def record(pin_number: str, pin_data: dict) -> dict:
        return {
            "pin": pin_number,
            "name": pin_data.get("name"),
            "description": pin_data.get("description"),
            "direction": pin_data.get("direction"),
        }

    power_pins = []
    ground_pins = []
    negative_supply_pins = []
    source_pins = []
    drain_pins = []
    common_pins = []
    normally_open_pins = []
    normally_closed_pins = []
    address_pins = []
    select_bank_pins = []
    enable_pins = []
    reset_pins = []
    serial_clock_pins = []
    serial_data_pins = []
    serial_output_pins = []
    sync_pins = []
    i2c_support = False

    for pin_number, pin_data in pins.items():
        item = record(pin_number, pin_data)
        name = (pin_data.get("name") or "").upper()
        desc = (pin_data.get("description") or "").lower()

        is_no_connect = (item.get("direction") == "NC") or ("no internal connection" in desc)

        if name in {"VDD", "VCC", "AVDD", "DVDD", "V+", "VDD+"}:
            power_pins.append(item)
        elif name in {"GND", "AGND", "DGND"}:
            ground_pins.append(item)
        elif name in {"VSS", "VEE", "V-", "-VCC", "-VDD"}:
            negative_supply_pins.append(item)

        if re.match(r"^S\d+[A-Z]?$", name):
            source_pins.append(item)
        if re.match(r"^D\d+[A-Z]?$", name) or name in {"D", "DA", "DB"}:
            drain_pins.append(item)
            common_pins.append(item)
        if (name == "COM" or re.match(r"^COM\d+$", name)) and not is_no_connect:
            common_pins.append(item)
        if (name == "NO" or re.match(r"^NO\d+$", name)) and not is_no_connect:
            normally_open_pins.append(item)
        if (name == "NC" or re.match(r"^NC\d+$", name)) and not is_no_connect:
            normally_closed_pins.append(item)
        if re.match(r"^A\d+$", name):
            address_pins.append(item)
        elif re.match(r"^SEL\d+$", name) or (re.match(r"^S\d+$", name) and item.get("direction") == "INPUT" and "select" in desc):
            select_bank_pins.append(item)
        elif (name == "IN" or re.match(r"^IN\d+(?:-\d+)?$", name)) and item.get("direction") == "INPUT" and any(token in desc for token in ("control", "select", "connect com", "logic control")):
            select_bank_pins.append(item)
        if name in {"EN", "ENABLE"}:
            enable_pins.append(item)
        if name in {"RESET", "RST", "RESETB", "RSTB"}:
            reset_pins.append(item)
        if name in {"SCLK", "SCL", "CLK"}:
            serial_clock_pins.append(item)
        if name in {"DIN", "SDA", "SDI"}:
            serial_data_pins.append(item)
        if name in {"DOUT", "SDO"}:
            serial_output_pins.append(item)
        if name in {"SYNC", "SYNCB", "CS", "CSB", "LE"}:
            sync_pins.append(item)

        if "i2c" in desc or "serial clock line" in desc or "serial data line" in desc or "open-drain" in desc:
            i2c_support = True

    topology_kind = "generic_signal_switch"
    channel_count = len(source_pins)
    if common_pins and (normally_open_pins or normally_closed_pins):
        topology_kind = "spdt_switch" if normally_closed_pins else "spst_switch"
        channel_count = max(len(common_pins), len(normally_open_pins), len(normally_closed_pins), 1)
    elif len(source_pins) >= 8 and len(drain_pins) <= 3:
        topology_kind = "mux_matrix"
    elif len(source_pins) >= 4 and len(drain_pins) >= 4:
        topology_kind = "independent_switch_bank"
        channel_count = max(len(source_pins), len(drain_pins))

    supports_shift_register = bool(
        any((item.get("name") or "").upper() in {"SCLK", "CLK"} for item in serial_clock_pins)
        and any((item.get("name") or "").upper() in {"DIN", "SDI"} for item in serial_data_pins)
    )
    supports_parallel_address = bool(address_pins)
    supports_direct_select_bank = bool(select_bank_pins)
    positive_supply_net = power_pins[0]["name"] if power_pins else "VDD"
    ground_net = ground_pins[0]["name"] if ground_pins else "GND"

    return {
        "preferred_package": preferred_package,
        "power_pins": power_pins,
        "ground_pins": ground_pins,
        "negative_supply_pins": negative_supply_pins,
        "source_pins": source_pins,
        "drain_pins": drain_pins,
        "common_pins": common_pins,
        "normally_open_pins": normally_open_pins,
        "normally_closed_pins": normally_closed_pins,
        "address_pins": address_pins,
        "select_bank_pins": select_bank_pins,
        "enable_pins": enable_pins,
        "reset_pins": reset_pins,
        "serial_clock_pins": serial_clock_pins,
        "serial_data_pins": serial_data_pins,
        "serial_output_pins": serial_output_pins,
        "sync_pins": sync_pins,
        "supports_i2c": i2c_support,
        "supports_shift_register": supports_shift_register,
        "supports_parallel_address": supports_parallel_address,
        "supports_direct_select_bank": supports_direct_select_bank,
        "topology_kind": topology_kind,
        "channel_count": channel_count,
        "positive_supply_net": positive_supply_net,
        "ground_net": ground_net,
        "supply_nets": list(dict.fromkeys(item["name"] for item in power_pins + negative_supply_pins + ground_pins)),
        "source": "sch_review_export.packages.pins",
        "source_refs": [
            ref
            for ref in [
                _pin_source_ref(preferred_package, power_pins, ground_pins, negative_supply_pins, note="supply pins from official package pin table"),
                _pin_source_ref(preferred_package, address_pins, select_bank_pins, enable_pins, reset_pins, serial_clock_pins, serial_data_pins, serial_output_pins, sync_pins, note="control pins from official package pin table"),
                _pin_source_ref(preferred_package, source_pins, drain_pins, common_pins, normally_open_pins, normally_closed_pins, note="analog path pins from official package pin table"),
            ]
            if ref
        ],
        "official_source_documents": _official_source_documents(datasheet_context),
    }


def _switch_external_components(switch_context: dict) -> list[dict]:
    components = [
        {
            "role": "supply_decoupling",
            "designator": "CBYP",
            "status": "required",
            "connect_between": [switch_context.get("positive_supply_net", "VDD"), switch_context.get("ground_net", "GND")],
            "why": "Low-charge-injection analog switches still need local bypassing close to the supply pins.",
        }
    ]

    if switch_context.get("supports_parallel_address"):
        components.append(
            {
                "role": "address_source_or_straps",
                "designator": "RADDR/JSEL",
                "status": "design_specific",
                "connect_between": ["ADDR_BUS", "logic_controller_or_straps"],
                "why": "Binary selector pins should not float during bring-up; tie them to a controller or deterministic straps.",
            }
        )
    if switch_context.get("supports_direct_select_bank"):
        components.append(
            {
                "role": "control_header_or_gpio",
                "designator": "JCTRL/RSEL",
                "status": "design_specific",
                "connect_between": ["SEL_BANK", "gpio_or_straps"],
                "why": "Per-channel select pins should be assigned to a deterministic GPIO or strap bank before schematic freeze.",
            }
        )
    if switch_context.get("enable_pins"):
        components.append(
            {
                "role": "enable_bias",
                "designator": "REN",
                "status": "optional",
                "connect_between": ["EN", "logic_default"],
                "why": "Enable state should be deterministic before the controller firmware is alive.",
            }
        )
    if switch_context.get("reset_pins"):
        components.append(
            {
                "role": "reset_bias",
                "designator": "RRESET",
                "status": "recommended",
                "connect_between": ["RESET_N", "logic_default"],
                "why": "Reset/control pins should come up in a known OFF state.",
            }
        )
    if switch_context.get("supports_i2c"):
        components.append(
            {
                "role": "i2c_pullups",
                "designator": "RPU_SCL/RPU_SDA",
                "status": "required_if_i2c_used",
                "connect_between": ["I2C_SCL", "I2C_SDA", "logic_pullup_rail"],
                "why": "Open-drain serial control requires pull-ups sized for the chosen logic rail and bus speed.",
            }
        )
    if switch_context.get("supports_shift_register"):
        components.append(
            {
                "role": "control_header_or_mcu",
                "designator": "JCTRL",
                "status": "design_specific",
                "connect_between": ["SPI_SCLK", "SPI_MOSI", "SYNC_N", "controller_domain"],
                "why": "The switch control interface should be partitioned to a stable MCU/FPGA boundary early.",
            }
        )

    if switch_context.get("topology_kind") == "mux_matrix":
        components.append(
            {
                "role": "analog_channel_breakout",
                "designator": "JANA",
                "status": "design_specific",
                "connect_between": ["MUX_COM", "MUX_CH"],
                "why": "Keep the common node and channel bank visible at the schematic boundary for signal ownership review.",
            }
        )
    elif switch_context.get("topology_kind") in {"spdt_switch", "spst_switch"}:
        breakout_nets = ["SW_COM", "SW_NO"] + (["SW_NC"] if switch_context.get("normally_closed_pins") else [])
        components.append(
            {
                "role": "analog_channel_breakout",
                "designator": "JANA",
                "status": "design_specific",
                "connect_between": breakout_nets,
                "why": "Keep COM / NO / NC path ownership explicit at the schematic boundary for review.",
            }
        )
    elif switch_context.get("topology_kind") == "independent_switch_bank":
        components.append(
            {
                "role": "switch_bank_breakout",
                "designator": "JSW",
                "status": "design_specific",
                "connect_between": ["SIG_PORT_A", "SIG_PORT_B"],
                "why": "Multi-channel switch banks are easier to route when the two signal sides are grouped explicitly.",
            }
        )

    return components


def _switch_starter_nets(switch_context: dict) -> list[dict]:
    nets = []
    seen = set()

    def add(name: str, purpose: str) -> None:
        if name in seen:
            return
        seen.add(name)
        nets.append({"name": name, "purpose": purpose})

    add(switch_context.get("positive_supply_net", "VDD"), "analog_switch_positive_supply")
    if switch_context.get("negative_supply_pins"):
        add((switch_context.get("negative_supply_pins") or [{"name": "VSS"}])[0]["name"], "analog_switch_negative_supply_or_ground")
    add(switch_context.get("ground_net", "GND"), "module_ground")
    if switch_context.get("supports_parallel_address"):
        add("ADDR_BUS", "switch_binary_address_lines")
    if switch_context.get("supports_direct_select_bank"):
        add("SEL_BANK", "switch_direct_channel_select_lines")
    if switch_context.get("enable_pins"):
        add("EN", "switch_enable_control")
    if switch_context.get("reset_pins"):
        add("RESET_N", "switch_reset_control")
    if switch_context.get("supports_i2c"):
        add("I2C_SCL", "i2c_clock")
        add("I2C_SDA", "i2c_data")
    elif switch_context.get("supports_shift_register"):
        add("SPI_SCLK", "serial_control_clock")
        add("SPI_MOSI", "serial_control_data")
        if switch_context.get("serial_output_pins"):
            add("SPI_MISO", "serial_readback_data")
        if switch_context.get("sync_pins"):
            add("SYNC_N", "serial_frame_sync")
    if switch_context.get("topology_kind") == "mux_matrix":
        add("MUX_COM", "common_analog_node")
        add("MUX_CH", "switched_channel_bank")
    elif switch_context.get("topology_kind") in {"spdt_switch", "spst_switch"}:
        add("SW_COM", "common_analog_node")
        add("SW_NO", "normally_open_path")
        if switch_context.get("normally_closed_pins"):
            add("SW_NC", "normally_closed_path")
    elif switch_context.get("topology_kind") == "independent_switch_bank":
        add("SIG_PORT_A", "switch_bank_side_a")
        add("SIG_PORT_B", "switch_bank_side_b")
    return nets


def _choose_default_switch_template(switch_templates: list[dict]) -> str | None:
    template_names = {item.get("name") for item in switch_templates}
    for preferred in ("i2c_switch_matrix", "serial_switch_bank", "addressable_analog_mux", "spdt_analog_switch", "direct_control_switch_bank", "switch_bank_breakout"):
        if preferred in template_names:
            return preferred
    return switch_templates[0].get("name") if switch_templates else None


def _switch_standard_templates(device: dict, switch_context: dict) -> list[dict]:
    templates = []

    def add_template(name: str, label: str, sheet_name: str, recommended_when: str, summary: str, nets: list[str], blocks: list[str], connections: list[dict], checklist: list[str]) -> None:
        templates.append(
            {
                "name": name,
                "label": label,
                "sheet_name": sheet_name,
                "recommended_when": recommended_when,
                "summary": summary,
                "nets": nets,
                "blocks": blocks,
                "default_refdes_map": {block: block for block in blocks},
                "connections": connections,
                "checklist": checklist,
            }
        )

    if switch_context.get("topology_kind") == "mux_matrix" and switch_context.get("supports_parallel_address"):
        add_template(
            "addressable_analog_mux",
            "Addressable Analog Mux",
            "S1_addressable_analog_mux",
            "Use when one common analog node is steered across a channel bank with direct address pins.",
            "Groups bypassing, address straps, and analog common/channel boundaries for first-pass schematic capture.",
            ["VDD", "GND", "MUX_COM", "MUX_CH", "ADDR_BUS"] + (["EN"] if switch_context.get("enable_pins") else []),
            ["U1", "CBYP", "RADDR", "JANA"],
            [
                {"from": "MUX_COM", "to": "JANA", "note": "Keep the common node obvious for upstream/downstream ownership."},
                {"from": "MUX_CH", "to": "JANA", "note": "Bundle switched channels as one reviewable boundary."},
                {"from": "ADDR_BUS", "to": "RADDR", "note": "Document selector polarity before firmware and schematic diverge."},
            ],
            ["Freeze the default selected channel and any break-before-make assumptions before review."],
        )
        templates[-1]["source"] = switch_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(switch_context.get("preferred_package"), switch_context.get("address_pins"), switch_context.get("enable_pins"), note="selector pins from official package pin table"),
                _pin_source_ref(switch_context.get("preferred_package"), switch_context.get("source_pins"), switch_context.get("drain_pins"), note="analog mux channels from official package pin table"),
            ]
            if ref
        ]

    if switch_context.get("supports_i2c") and switch_context.get("topology_kind") == "mux_matrix":
        add_template(
            "i2c_switch_matrix",
            "I2C-Controlled Analog Matrix",
            "S2_i2c_switch_matrix",
            "Use when the switch is controlled over a 2-wire bus and needs address straps or reset management.",
            "Partitions I2C pull-ups, address pins, and the analog common/channel matrix around the switch IC.",
            ["VDD", "GND", "I2C_SCL", "I2C_SDA", "MUX_COM", "MUX_CH"] + (["RESET_N"] if switch_context.get("reset_pins") else []) + (["ADDR_BUS"] if switch_context.get("address_pins") else []),
            ["U1", "CBYP", "RPU_SCL", "RPU_SDA", "RADDR", "JANA"],
            [
                {"from": "I2C_SCL", "to": "RPU_SCL", "note": "Pull the clock line to the selected logic rail."},
                {"from": "I2C_SDA", "to": "RPU_SDA", "note": "Keep open-drain data ownership clear for host integration."},
                {"from": "MUX_COM", "to": "JANA", "note": "Expose the common analog node at a stable connector boundary."},
            ],
            ["Freeze I2C address map, reset default, and analog source impedance before layout."],
        )
        templates[-1]["source"] = switch_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(switch_context.get("preferred_package"), switch_context.get("serial_clock_pins"), switch_context.get("serial_data_pins"), switch_context.get("address_pins"), switch_context.get("reset_pins"), note="I2C and control pins from official package pin table"),
                _pin_source_ref(switch_context.get("preferred_package"), switch_context.get("source_pins"), switch_context.get("drain_pins"), note="analog matrix pins from official package pin table"),
            ]
            if ref
        ]

    if switch_context.get("supports_shift_register"):
        add_template(
            "serial_switch_bank",
            "Serial-Controlled Switch Bank",
            "S3_serial_switch_bank",
            "Use when an MCU/FPGA shifts switch state into a bank of independent SPST channels.",
            "Groups the serial control bus, reset/frame sync, and the two switch-bank signal sides for quick implementation.",
            ["VDD", "GND", "SPI_SCLK", "SPI_MOSI", "SIG_PORT_A", "SIG_PORT_B"] + (["SPI_MISO"] if switch_context.get("serial_output_pins") else []) + (["SYNC_N"] if switch_context.get("sync_pins") else []) + (["RESET_N"] if switch_context.get("reset_pins") else []),
            ["U1", "CBYP", "JCTRL", "JSW"],
            [
                {"from": "SPI_SCLK", "to": "JCTRL", "note": "Tie the control clock to the owning MCU or FPGA domain."},
                {"from": "SPI_MOSI", "to": "JCTRL", "note": "Keep serial data ownership visible at the module boundary."},
                {"from": "SIG_PORT_A", "to": "JSW", "note": "Group one side of the switch bank together to simplify routing review."},
                {"from": "SIG_PORT_B", "to": "JSW", "note": "Group the switched outputs on the opposite boundary."},
            ],
            ["Freeze reset behavior, frame-sync polarity, and off-state leakage expectations before review."],
        )
        templates[-1]["source"] = switch_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(switch_context.get("preferred_package"), switch_context.get("serial_clock_pins"), switch_context.get("serial_data_pins"), switch_context.get("serial_output_pins"), switch_context.get("sync_pins"), switch_context.get("reset_pins"), note="serial control pins from official package pin table"),
                _pin_source_ref(switch_context.get("preferred_package"), switch_context.get("source_pins"), switch_context.get("drain_pins"), note="switch-bank signal pins from official package pin table"),
            ]
            if ref
        ]

    if switch_context.get("topology_kind") in {"spdt_switch", "spst_switch"}:
        starter_nets = [switch_context.get("positive_supply_net", "VDD"), switch_context.get("ground_net", "GND"), "SW_COM", "SW_NO"]
        if switch_context.get("normally_closed_pins"):
            starter_nets.append("SW_NC")
        if switch_context.get("supports_direct_select_bank"):
            starter_nets.append("SEL_BANK")
        if switch_context.get("enable_pins"):
            starter_nets.append("EN")
        add_template(
            "spdt_analog_switch",
            "SPDT Analog Switch",
            "S4_spdt_analog_switch",
            "Use when one common analog node is switched between normally-open and normally-closed throws.",
            "Captures COM/NO/NC ownership, default state, and enable control for first-pass schematic capture.",
            starter_nets,
            ["U1", "CBYP", "JANA"] + (["JCTRL"] if switch_context.get("supports_direct_select_bank") else []) + (["REN"] if switch_context.get("enable_pins") else []),
            [
                {"from": "SW_COM", "to": "JANA", "note": "Keep the common analog node explicit at the upstream/downstream boundary."},
                {"from": "SW_NO", "to": "JANA", "note": "Label the normally-open path before control polarity diverges from the schematic."},
            ] + ([{"from": "SW_NC", "to": "JANA", "note": "Label the normally-closed path so the default conduction state is reviewable."}] if switch_context.get("normally_closed_pins") else []) + ([{"from": "SEL_BANK", "to": "JCTRL", "note": "Keep grouped select-line ownership visible when one control pin drives multiple throws."}] if switch_context.get("supports_direct_select_bank") else []),
            ["Freeze default conduction state, enable polarity, and COM / NO / NC naming before review."],
        )
        templates[-1]["source"] = switch_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(switch_context.get("preferred_package"), switch_context.get("select_bank_pins"), switch_context.get("enable_pins"), note="control pins from official package pin table"),
                _pin_source_ref(switch_context.get("preferred_package"), switch_context.get("common_pins"), switch_context.get("normally_open_pins"), switch_context.get("normally_closed_pins"), note="COM / NO / NC pins from official package pin table"),
            ]
            if ref
        ]

    if switch_context.get("topology_kind") == "independent_switch_bank" and switch_context.get("supports_direct_select_bank") and not switch_context.get("supports_shift_register"):
        add_template(
            "direct_control_switch_bank",
            "Direct-Control Switch Bank",
            "S5_direct_control_switch_bank",
            "Use when each channel in the switch bank has its own dedicated select line from an MCU/FPGA/GPIO bank.",
            "Captures per-channel select ownership together with the two switched signal sides for first-pass schematic capture.",
            [switch_context.get("positive_supply_net", "VDD"), switch_context.get("ground_net", "GND"), "SEL_BANK", "SIG_PORT_A", "SIG_PORT_B"] + (["EN"] if switch_context.get("enable_pins") else []),
            ["U1", "CBYP", "JCTRL", "JSW"] + (["REN"] if switch_context.get("enable_pins") else []),
            [
                {"from": "SEL_BANK", "to": "JCTRL", "note": "Keep per-channel select ownership visible at the controller boundary."},
                {"from": "SIG_PORT_A", "to": "JSW", "note": "Group one side of the switch bank together to simplify routing review."},
                {"from": "SIG_PORT_B", "to": "JSW", "note": "Group the switched outputs on the opposite boundary."},
            ],
            ["Freeze per-channel default state, select polarity, and channel naming before schematic release."],
        )
        templates[-1]["source"] = switch_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(switch_context.get("preferred_package"), switch_context.get("select_bank_pins"), switch_context.get("enable_pins"), note="per-channel select pins from official package pin table"),
                _pin_source_ref(switch_context.get("preferred_package"), switch_context.get("source_pins"), switch_context.get("drain_pins"), note="switch-bank signal pins from official package pin table"),
            ]
            if ref
        ]

    if switch_context.get("topology_kind") == "independent_switch_bank" and not switch_context.get("supports_shift_register"):
        add_template(
            "switch_bank_breakout",
            "Switch Bank Breakout",
            "S5_switch_bank_breakout",
            "Use when independent switched channels need only direct control and a clean signal partition.",
            "Captures bypassing and side-A/side-B signal ownership for a multi-channel analog switch bank.",
            [switch_context.get("positive_supply_net", "VDD"), switch_context.get("ground_net", "GND"), "SIG_PORT_A", "SIG_PORT_B"],
            ["U1", "CBYP", "JSW"],
            [
                {"from": "SIG_PORT_A", "to": "JSW", "note": "Keep source-side signals grouped by connector or upstream analog block."},
                {"from": "SIG_PORT_B", "to": "JSW", "note": "Keep destination-side signals grouped for review and labeling."},
            ],
            ["Freeze normally-on/off expectations and channel naming before schematic release."],
        )
        templates[-1]["source"] = switch_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(switch_context.get("preferred_package"), switch_context.get("source_pins"), switch_context.get("drain_pins"), note="switch-bank signal pins from official package pin table"),
            ]
            if ref
        ]

    return templates


def _is_interface_switch_like(device: dict) -> bool:
    category = (device.get("category") or "").lower()
    if category != "switch":
        return False

    text = " ".join(
        [
            device.get("mpn") or "",
            device.get("description") or "",
            device.get("category") or "",
        ]
    ).lower()
    if any(
        token in text
        for token in (
            "efuse",
            "load switch",
            "power switch",
            "power mux",
            "power multiplexer",
            "ideal diode",
            "high-side",
            "current-limited",
            "power-distribution",
            "reverse polarity",
        )
    ):
        return False

    preferred_package = _pick_preferred_package(device)
    package_data = device.get("packages", {}).get(preferred_package or "", {}) if preferred_package else {}
    pins = package_data.get("pins", {})
    names = [(pin.get("name") or "").upper() for pin in pins.values()]

    return any(token in text for token in ("usb", "pcie", "superspeed", "displayport", "display port", "bus switch")) or any(
        re.match(r"^\d+[AB]$", name)
        or re.match(r"^[ABC]\d+[+-]$", name)
        or re.match(r"^D\d+[+-][-_]?[AB]$", name)
        or re.match(r"^D\d+[+-]$", name)
        or name in {"D+", "D-", "SEL", "OE", "/OE", "HPD", "AUX+", "AUX-"}
        or name.endswith("_A")
        or name.endswith("_B")
        or "SSRX" in name
        or "SSTX" in name
        for name in names
    )


def _infer_interface_switch_traits(device: dict, datasheet_context: dict | None = None) -> dict:
    preferred_package = _pick_preferred_package(device)
    package_data = device.get("packages", {}).get(preferred_package or "", {}) if preferred_package else {}
    pins = package_data.get("pins", {})
    datasheet_context = datasheet_context or {}

    def record(pin_number: str, pin_data: dict) -> dict:
        return {
            "pin": pin_number,
            "name": pin_data.get("name"),
            "description": pin_data.get("description"),
            "direction": pin_data.get("direction"),
        }

    text = " ".join([device.get("mpn") or "", device.get("description") or ""]).lower()
    design_page_text = " ".join((page.get("preview") or "") for page in datasheet_context.get("design_page_candidates", [])).lower()
    power_pins = []
    ground_pins = []
    select_pins = []
    enable_pins = []
    reset_pins = []
    common_pins = []
    branch_a_pins = []
    branch_b_pins = []
    aux_pins = []
    sideband_common_pins = []
    sideband_a_pins = []
    sideband_b_pins = []
    diff_groups = {"A": [], "B": [], "C": []}
    bus_a_pins = []
    bus_b_pins = []
    bus_common_pins = []
    bus_mux_channel_pins = []
    usb_common = []
    usb_port1 = []
    usb_port2 = []
    usb_audio_common = []
    usb_audio_path0 = []
    usb_audio_path1 = []
    usb_audio_lr = []
    ss_common = []
    ss_port1 = []
    ss_port2 = []
    dp_common = []
    dp_port_a = []
    dp_port_b = []

    for pin_number, pin_data in pins.items():
        item = record(pin_number, pin_data)
        name = (pin_data.get("name") or "").upper()
        desc = (pin_data.get("description") or "").lower()

        if name in {"VCC", "VDD", "AVDD", "DVDD"}:
            power_pins.append(item)
        elif name in {"GND", "AGND", "DGND", "EP", "EP GND"} or name.endswith(" GND"):
            ground_pins.append(item)
        elif name in {"S", "SEL"} or re.match(r"^S\d+$", name) or re.match(r"^SEL\d+$", name):
            select_pins.append(item)
        elif name in {"OE", "/OE", "OEB", "EN"} or re.match(r"^/?OE\d*$", name) or re.match(r"^OEB\d*$", name):
            enable_pins.append(item)
        elif name in {"RESET", "RST", "RESETB", "RSTB"}:
            reset_pins.append(item)

        if name in {"D+", "D-"}:
            usb_common.append(item)
        elif re.match(r"^[12]D[+-]$", name):
            if name.startswith("1"):
                usb_port1.append(item)
            else:
                usb_port2.append(item)
        elif name in {"D+/R", "D-/L"} or "common connector" in desc:
            usb_audio_common.append(item)
        elif re.match(r"^D0[+-]$", name) and any(token in desc for token in ("usb", "mhl", "uart", "audio")):
            usb_audio_path0.append(item)
        elif re.match(r"^D1[+-]$", name) and any(token in desc for token in ("usb", "mhl", "uart", "audio")):
            usb_audio_path1.append(item)
        elif name in {"R", "L"} and "audio" in desc:
            usb_audio_lr.append(item)
        elif "COM" in name and ("SSRX" in name or "SSTX" in name):
            ss_common.append(item)
        elif ("SSRX1" in name or "SSTX1" in name):
            ss_port1.append(item)
        elif ("SSRX2" in name or "SSTX2" in name):
            ss_port2.append(item)

        if re.match(r"^D\d+[+-]$", name) and "common port" in desc:
            dp_common.append(item)
        elif re.match(r"^D\d+[+-][-_]?[AB]$", name) and "port a" in desc:
            dp_port_a.append(item)
        elif re.match(r"^D\d+[+-][-_]?[AB]$", name) and "port b" in desc:
            dp_port_b.append(item)

        if name in {"SCL", "SDA", "HPD", "CEC", "AUX+", "AUX-"} and "common port" in desc:
            sideband_common_pins.append(item)
        elif (name.endswith("_A") or name.endswith("A")) and any(token in name for token in {"SCL", "SDA", "HPD", "CEC", "AUX"}) and "port a" in desc:
            sideband_a_pins.append(item)
        elif (name.endswith("_B") or name.endswith("B")) and any(token in name for token in {"SCL", "SDA", "HPD", "CEC", "AUX"}) and "port b" in desc:
            sideband_b_pins.append(item)

        diff_match = re.match(r"^([ABC])(\d+)[+-]$", name)
        if diff_match:
            diff_groups[diff_match.group(1)].append(item)
        bus_match = re.match(r"^(\d+)([AB])$", name)
        if bus_match:
            if bus_match.group(2) == "A":
                bus_a_pins.append(item)
            else:
                bus_b_pins.append(item)
        if name == "A":
            bus_common_pins.append(item)
        if re.match(r"^B\d+$", name):
            bus_mux_channel_pins.append(item)

    interface_kind = "generic_interface_switch"
    topology_kind = "interface_switch"
    channel_count = 0
    if dp_common or dp_port_a or dp_port_b or "displayport" in text or "display port" in design_page_text:
        interface_kind = "displayport"
        topology_kind = "displayport_mux"
        common_pins = dp_common
        branch_a_pins = dp_port_a
        branch_b_pins = dp_port_b
        aux_pins = sideband_common_pins + sideband_a_pins + sideband_b_pins
        channel_count = max(len(common_pins) // 2, len(branch_a_pins) // 2, len(branch_b_pins) // 2, 1)
    elif usb_common or usb_port1 or usb_port2:
        interface_kind = "usb2"
        topology_kind = "usb2_mux"
        common_pins = usb_common
        branch_a_pins = usb_port1
        branch_b_pins = usb_port2
        channel_count = max(len(usb_common) // 2, 1)
    elif usb_audio_common or usb_audio_path0 or usb_audio_path1 or usb_audio_lr:
        interface_kind = "usb2_audio"
        topology_kind = "usb2_audio_sp3t"
        common_pins = usb_audio_common
        branch_a_pins = usb_audio_path0
        branch_b_pins = usb_audio_path1
        aux_pins = usb_audio_lr
        channel_count = max(len(common_pins), len(branch_a_pins), len(branch_b_pins), len(aux_pins), 1)
    elif ss_common or ss_port1 or ss_port2:
        interface_kind = "superspeed"
        topology_kind = "superspeed_mux"
        common_pins = ss_common
        branch_a_pins = ss_port1
        branch_b_pins = ss_port2
        channel_count = max(len(ss_common) // 2, 1)
    elif diff_groups["C"] or diff_groups["A"] or diff_groups["B"]:
        interface_kind = "pcie"
        topology_kind = "pcie_diff_mux"
        common_pins = diff_groups["C"]
        branch_a_pins = diff_groups["A"]
        branch_b_pins = diff_groups["B"]
        channel_count = max(len(common_pins) // 2, 1) if common_pins else max(len(branch_a_pins) // 2, len(branch_b_pins) // 2, 1)
    elif bus_common_pins and bus_mux_channel_pins:
        interface_kind = "bus"
        topology_kind = "bus_mux"
        common_pins = bus_common_pins
        branch_a_pins = bus_mux_channel_pins
        branch_b_pins = []
        channel_count = len(bus_mux_channel_pins)
    elif bus_a_pins or bus_b_pins or "bus switch" in text:
        interface_kind = "bus"
        topology_kind = "bus_switch"
        common_pins = []
        branch_a_pins = bus_a_pins
        branch_b_pins = bus_b_pins
        channel_count = max(len(bus_a_pins), len(bus_b_pins), 1)
    else:
        for pin_number, item in pins.items():
            name = (item.get("name") or "").upper()
            if name not in {"VCC", "VDD", "GND", "AGND", "DGND", "S", "SEL", "OE", "/OE", "OEB", "EN"}:
                aux_pins.append(record(pin_number, item))

    return {
        "preferred_package": preferred_package,
        "power_pins": power_pins,
        "ground_pins": ground_pins,
        "select_pins": select_pins,
        "enable_pins": enable_pins,
        "reset_pins": reset_pins,
        "common_pins": common_pins,
        "branch_a_pins": branch_a_pins,
        "branch_b_pins": branch_b_pins,
        "aux_pins": aux_pins,
        "sideband_common_pins": sideband_common_pins,
        "sideband_a_pins": sideband_a_pins,
        "sideband_b_pins": sideband_b_pins,
        "interface_kind": interface_kind,
        "topology_kind": topology_kind,
        "channel_count": channel_count,
        "supply_nets": [item["name"] for item in power_pins + ground_pins],
        "source": "sch_review_export.packages.pins",
        "source_refs": [
            ref
            for ref in [
                _pin_source_ref(preferred_package, power_pins, ground_pins, note="supply pins from official package pin table"),
                _pin_source_ref(preferred_package, select_pins, enable_pins, reset_pins, note="control pins from official package pin table"),
                _pin_source_ref(preferred_package, common_pins, branch_a_pins, branch_b_pins, sideband_common_pins, sideband_a_pins, sideband_b_pins, note="signal path pins from official package pin table"),
            ]
            if ref
        ],
        "official_source_documents": _official_source_documents(datasheet_context),
    }


def _interface_switch_external_components(interface_context: dict) -> list[dict]:
    components = [
        {
            "role": "supply_decoupling",
            "designator": "CBYP",
            "status": "required",
            "connect_between": ["VDD_OR_VCC", "GND"],
            "why": "High-speed and bus switches still need local supply bypassing at the package pins.",
        }
    ]
    if interface_context.get("select_pins"):
        components.append(
            {
                "role": "select_bias",
                "designator": "RSEL",
                "status": "recommended",
                "connect_between": ["SEL", "logic_default"],
                "why": "Selection pins should not float during reset or cable hot-plug events.",
            }
        )
    if interface_context.get("enable_pins"):
        components.append(
            {
                "role": "enable_bias",
                "designator": "ROE",
                "status": "recommended",
                "connect_between": ["OE_N", "logic_default"],
                "why": "Output-enable polarity should be deterministic before the host controller takes over.",
            }
        )
    if interface_context.get("interface_kind") in {"usb2", "usb2_audio", "superspeed"}:
        components.append(
            {
                "role": "esd_review",
                "designator": "DESD",
                "status": "design_specific",
                "connect_between": ["high_speed_connector", "switch_lanes"],
                "why": "USB-facing ports usually need coordinated ESD protection and lane ownership review.",
            }
        )
    if interface_context.get("interface_kind") in {"superspeed", "pcie", "displayport"}:
        components.append(
            {
                "role": "ac_coupling_review",
                "designator": "CAC",
                "status": "design_specific",
                "connect_between": ["common_diff_lanes", "branch_diff_lanes"],
                "why": "High-speed differential paths need an explicit decision on AC-coupling placement and ownership.",
            }
        )
    components.append(
        {
            "role": "signal_path_breakout",
            "designator": "JPATH",
            "status": "design_specific",
            "connect_between": ["common_path", "branch_paths"],
            "why": "Keep common and branch-side path ownership explicit before schematic and layout diverge.",
        }
    )
    return components


def _interface_switch_starter_nets(interface_context: dict) -> list[dict]:
    nets = []
    seen = set()

    def add(name: str, purpose: str) -> None:
        if name in seen:
            return
        seen.add(name)
        nets.append({"name": name, "purpose": purpose})

    add("VCC", "interface_switch_supply")
    add("GND", "module_ground")
    if interface_context.get("select_pins"):
        add("SEL", "path_select_control")
    if interface_context.get("enable_pins"):
        add("OE_N", "output_enable_control")
    kind = interface_context.get("interface_kind")
    if kind == "usb2":
        add("USB2_COM", "common_usb2_pair")
        add("USB2_PORT_A", "usb2_branch_a_pair")
        add("USB2_PORT_B", "usb2_branch_b_pair")
    elif kind == "usb2_audio":
        add("USB_AUDIO_COM", "common_usb2_or_audio_pair")
        add("USB_PATH_0", "usb2_or_mhl_path_0")
        add("USB_PATH_1", "usb2_or_mhl_path_1")
        add("AUDIO_LR", "stereo_audio_pair")
    elif kind == "superspeed":
        add("SS_TXRX_COM", "superspeed_common_lanes")
        add("SS_PORT_A", "superspeed_branch_a_lanes")
        add("SS_PORT_B", "superspeed_branch_b_lanes")
    elif kind == "displayport":
        add("DP_COM", "displayport_common_mainlink")
        add("DP_PORT_A", "displayport_branch_a_mainlink")
        add("DP_PORT_B", "displayport_branch_b_mainlink")
        add("DP_CTRL_COM", "displayport_common_sideband")
        add("DP_CTRL_A", "displayport_branch_a_sideband")
        add("DP_CTRL_B", "displayport_branch_b_sideband")
    elif kind == "pcie":
        add("PCIE_COM", "pcie_common_lanes")
        add("PCIE_PORT_A", "pcie_branch_a_lanes")
        add("PCIE_PORT_B", "pcie_branch_b_lanes")
    elif kind == "bus" and interface_context.get("topology_kind") == "bus_mux":
        add("BUS_COM", "bus_common_node")
        add("BUS_CH", "bus_mux_channel_bank")
    elif kind == "bus":
        add("BUS_A", "bus_side_a")
        add("BUS_B", "bus_side_b")
    return nets


def _choose_default_interface_switch_template(interface_switch_templates: list[dict]) -> str | None:
    names = {item.get("name") for item in interface_switch_templates}
    for preferred in ("displayport_data_switch", "superspeed_data_switch", "pcie_diff_switch", "usb2_audio_switch", "usb2_data_switch", "bus_mux_bridge", "bus_switch_bridge"):
        if preferred in names:
            return preferred
    return interface_switch_templates[0].get("name") if interface_switch_templates else None


def _interface_switch_standard_templates(device: dict, interface_context: dict) -> list[dict]:
    templates = []

    def add_template(name: str, label: str, sheet_name: str, recommended_when: str, summary: str, nets: list[str], blocks: list[str], connections: list[dict], checklist: list[str]) -> None:
        templates.append(
            {
                "name": name,
                "label": label,
                "sheet_name": sheet_name,
                "recommended_when": recommended_when,
                "summary": summary,
                "nets": nets,
                "blocks": blocks,
                "default_refdes_map": {block: block for block in blocks},
                "connections": connections,
                "checklist": checklist,
            }
        )

    kind = interface_context.get("interface_kind")
    common_ctrl = (["SEL"] if interface_context.get("select_pins") else []) + (["OE_N"] if interface_context.get("enable_pins") else [])

    if kind == "usb2":
        add_template(
            "usb2_data_switch",
            "USB2 Data Switch",
            "H1_usb2_data_switch",
            "Use when one USB2 D+/D- pair is switched between two downstream or upstream paths.",
            "Captures common/branch USB2 pairs, control pins, bypassing, and ESD review in one place.",
            ["VCC", "GND", "USB2_COM", "USB2_PORT_A", "USB2_PORT_B"] + common_ctrl,
            ["U1", "CBYP", "RSEL", "ROE", "DESD", "JPATH"],
            [
                {"from": "USB2_COM", "to": "JPATH", "note": "Keep the common D+/D- pair visible at the shared connector or controller boundary."},
                {"from": "USB2_PORT_A", "to": "JPATH", "note": "Document the first switched USB2 path explicitly."},
                {"from": "USB2_PORT_B", "to": "JPATH", "note": "Document the second switched USB2 path explicitly."},
            ],
            ["Freeze select polarity and ESD placement before USB compliance review."],
        )
        templates[-1]["source"] = interface_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("select_pins"), interface_context.get("enable_pins"), note="control pins from official package pin table"),
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("common_pins"), interface_context.get("branch_a_pins"), interface_context.get("branch_b_pins"), note="USB2 path pins from official package pin table"),
            ]
            if ref
        ]
    elif kind == "usb2_audio":
        add_template(
            "usb2_audio_switch",
            "USB2 / Audio Switch",
            "H1a_usb2_audio_switch",
            "Use when one common connector pair is steered between two USB/MHL paths or a stereo audio path by shared select pins.",
            "Captures the shared connector pair, two switched high-speed paths, stereo audio branch, and select ownership from the official pin table.",
            ["VCC", "GND", "USB_AUDIO_COM", "USB_PATH_0", "USB_PATH_1", "AUDIO_LR"] + common_ctrl,
            ["U1", "CBYP", "RSEL", "DESD", "JPATH"],
            [
                {"from": "USB_AUDIO_COM", "to": "JPATH", "note": "Keep the common connector pair explicit at the downstream connector boundary."},
                {"from": "USB_PATH_0", "to": "JPATH", "note": "Document the first switched USB/MHL/UART path as a paired route."},
                {"from": "USB_PATH_1", "to": "JPATH", "note": "Document the second switched USB/MHL/UART path as a paired route."},
                {"from": "AUDIO_LR", "to": "JPATH", "note": "Keep the stereo audio branch explicit so mode-dependent ownership is reviewable."},
            ],
            ["Freeze SEL1/SEL2 truth-table ownership and connector mode naming before release."],
        )
        templates[-1]["source"] = interface_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("select_pins"), note="control pins from official package pin table"),
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("common_pins"), interface_context.get("branch_a_pins"), interface_context.get("branch_b_pins"), interface_context.get("aux_pins"), note="USB/audio path pins from official package pin table"),
            ]
            if ref
        ]
    elif kind == "displayport":
        add_template(
            "displayport_data_switch",
            "DisplayPort Data Switch",
            "H2a_displayport_data_switch",
            "Use when one DisplayPort main-link group and sideband channel set are switched between two source or sink branches.",
            "Captures common DisplayPort Main Link lanes, branch lanes, sideband ownership, select pins, and AC-coupling review from the official pin table and application pages.",
            ["VCC", "GND", "DP_COM", "DP_PORT_A", "DP_PORT_B", "DP_CTRL_COM", "DP_CTRL_A", "DP_CTRL_B"] + common_ctrl,
            ["U1", "CBYP", "RSEL", "ROE", "CAC", "JPATH"],
            [
                {"from": "DP_COM", "to": "JPATH", "note": "Keep the common Main Link lanes grouped at the shared connector or GPU boundary."},
                {"from": "DP_PORT_A", "to": "JPATH", "note": "Document branch A Main Link ownership before connector mapping shifts."},
                {"from": "DP_PORT_B", "to": "JPATH", "note": "Document branch B Main Link ownership before connector mapping shifts."},
                {"from": "DP_CTRL_COM", "to": "JPATH", "note": "Keep AUX / HPD / DDC sideband ownership explicit at the common port boundary."},
            ],
            ["Freeze select polarity, Main Link lane ownership, and AUX / HPD coupling placement before SI review."],
        )
        templates[-1]["source"] = interface_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("select_pins"), interface_context.get("enable_pins"), note="control pins from official package pin table"),
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("common_pins"), interface_context.get("branch_a_pins"), interface_context.get("branch_b_pins"), interface_context.get("sideband_common_pins"), interface_context.get("sideband_a_pins"), interface_context.get("sideband_b_pins"), note="DisplayPort signal and sideband pins from official package pin table"),
            ]
            if ref
        ]
    elif kind == "superspeed":
        add_template(
            "superspeed_data_switch",
            "SuperSpeed Data Switch",
            "H2_superspeed_data_switch",
            "Use when a SuperSpeed common lane group is switched between two branch ports.",
            "Groups TX/RX common lanes, branch lanes, control pins, AC-coupling review, and ESD ownership.",
            ["VCC", "GND", "SS_TXRX_COM", "SS_PORT_A", "SS_PORT_B"] + common_ctrl,
            ["U1", "CBYP", "RSEL", "ROE", "DESD", "CAC", "JPATH"],
            [
                {"from": "SS_TXRX_COM", "to": "JPATH", "note": "Keep common SuperSpeed lanes adjacent in the schematic hierarchy."},
                {"from": "SS_PORT_A", "to": "JPATH", "note": "Lock the first branch lane ownership before layout."},
                {"from": "SS_PORT_B", "to": "JPATH", "note": "Lock the second branch lane ownership before layout."},
            ],
            ["Freeze AC-coupling ownership, lane polarity, and select default before SI review."],
        )
        templates[-1]["source"] = interface_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("select_pins"), interface_context.get("enable_pins"), note="control pins from official package pin table"),
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("common_pins"), interface_context.get("branch_a_pins"), interface_context.get("branch_b_pins"), note="SuperSpeed path pins from official package pin table"),
            ]
            if ref
        ]
    elif kind == "pcie":
        add_template(
            "pcie_diff_switch",
            "PCIe Differential Switch",
            "H3_pcie_diff_switch",
            "Use when common PCIe lanes are muxed between two branches or slots.",
            "Captures common/branch differential lane ownership, select pins, and AC-coupling review for PCIe fabrics.",
            ["VCC", "GND", "PCIE_COM", "PCIE_PORT_A", "PCIE_PORT_B"] + common_ctrl,
            ["U1", "CBYP", "RSEL", "ROE", "CAC", "JPATH"],
            [
                {"from": "PCIE_COM", "to": "JPATH", "note": "Keep common PCIe lanes grouped to the root complex or common slot boundary."},
                {"from": "PCIE_PORT_A", "to": "JPATH", "note": "Document branch A lane ownership before connector mapping shifts."},
                {"from": "PCIE_PORT_B", "to": "JPATH", "note": "Document branch B lane ownership before connector mapping shifts."},
            ],
            ["Freeze enable/select polarity and AC-coupling placement before PCIe layout review."],
        )
        templates[-1]["source"] = interface_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("select_pins"), interface_context.get("enable_pins"), note="control pins from official package pin table"),
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("common_pins"), interface_context.get("branch_a_pins"), interface_context.get("branch_b_pins"), note="PCIe path pins from official package pin table"),
            ]
            if ref
        ]
    elif kind == "bus" and interface_context.get("topology_kind") == "bus_mux":
        add_template(
            "bus_mux_bridge",
            "Bus Mux Bridge",
            "H4_bus_mux_bridge",
            "Use when one common bus node is muxed across a numbered channel bank by select pins.",
            "Groups common bus node, numbered channels, select pins, and OE control for bus-mux review.",
            ["VCC", "GND", "BUS_COM", "BUS_CH"] + common_ctrl + (["SEL"] if interface_context.get("select_pins") else []),
            ["U1", "CBYP", "RSEL", "ROE", "JPATH"],
            [
                {"from": "BUS_COM", "to": "JPATH", "note": "Keep the common bus node explicit at the upstream/downstream boundary."},
                {"from": "BUS_CH", "to": "JPATH", "note": "Group numbered bus channels as one reviewable boundary."},
                {"from": "SEL", "to": "RSEL", "note": "Freeze mux select ownership before firmware and schematic diverge."},
            ],
            ["Freeze select polarity, OE default state, and common-to-channel naming before release."],
        )
        templates[-1]["source"] = interface_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("select_pins"), interface_context.get("enable_pins"), note="mux control pins from official package pin table"),
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("common_pins"), interface_context.get("branch_a_pins"), note="common bus and channel pins from official package pin table"),
            ]
            if ref
        ]
    elif kind == "bus":
        add_template(
            "bus_switch_bridge",
            "Bus Switch Bridge",
            "H5_bus_switch_bridge",
            "Use when a simple digital bus is transparently gated or bridged across two sides.",
            "Groups bus-side A/B naming and OE control so the boundary is clear for bring-up and review.",
            ["VCC", "GND", "BUS_A", "BUS_B"] + common_ctrl,
            ["U1", "CBYP", "ROE", "JPATH"],
            [
                {"from": "BUS_A", "to": "JPATH", "note": "Keep side-A signal ownership grouped together."},
                {"from": "BUS_B", "to": "JPATH", "note": "Keep side-B signal ownership grouped together."},
            ],
            ["Freeze OE default state and side-A/side-B naming before release."],
        )
        templates[-1]["source"] = interface_context.get("source")
        templates[-1]["source_refs"] = [
            ref
            for ref in [
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("enable_pins"), note="enable pins from official package pin table"),
                _pin_source_ref(interface_context.get("preferred_package"), interface_context.get("branch_a_pins"), interface_context.get("branch_b_pins"), note="bus path pins from official package pin table"),
            ]
            if ref
        ]

    return templates


def _infer_decoder_traits(device: dict, pin_groups: dict, datasheet_context: dict | None = None) -> dict:
    preferred_package = _pick_preferred_package(device)
    package_data = device.get("packages", {}).get(preferred_package or "", {}) if preferred_package else {}
    pins = package_data.get("pins", {})
    datasheet_context = datasheet_context or {}

    haystack_parts = [device.get("description") or "", device.get("mpn") or ""]
    for page in datasheet_context.get("design_page_candidates", [])[:12]:
        haystack_parts.append(page.get("preview") or "")
    for item in datasheet_context.get("recommended_external_components", [])[:12]:
        haystack_parts.append(item.get("snippet") or "")
    for item in datasheet_context.get("layout_hints", [])[:8]:
        haystack_parts.append(item.get("hint") or "")
    haystack = " ".join(haystack_parts)
    haystack_lower = haystack.lower()

    def placeholder(name: str, description: str) -> dict:
        return {"pin": None, "name": name, "description": description, "direction": None}

    power_rails = []
    seen_rails: set[str] = set()
    for item in pin_groups.get("power_inputs", []):
        rail_name = item.get("name") or "VIN"
        if rail_name in seen_rails:
            continue
        seen_rails.add(rail_name)
        power_rails.append(
            {
                "name": rail_name,
                "purpose": item.get("description") or "device_power_rail",
                "pins": [pin.get("pin") for pin in pin_groups.get("power_inputs", []) if pin.get("name") == rail_name],
            }
        )

    analog_video_inputs = []
    serial_links = []
    mipi_outputs = []
    parallel_video_outputs = []
    ref_clock_pins = []
    config_pins = []
    reset_pins = []
    status_pins = []
    i2c_pins = []
    i2c_available = False
    poc_support = any(token in haystack_lower for token in ("power over coax", "poc", "vpoc"))

    for pin_number, pin_data in pins.items():
        name = pin_data.get("name") or ""
        desc = pin_data.get("description") or ""
        lower = f"{name} {desc}".lower()
        record = {"pin": pin_number, "name": name, "description": desc, "direction": pin_data.get("direction")}

        if name.upper() in {"SCL", "SDA"}:
            i2c_pins.append(record)
            i2c_available = True
        elif "i2c" in lower:
            i2c_available = True

        if re.search(r"\b(X1|X2|XTI|XTO|OSC|CLKIN|REFCLK)\b", name, re.IGNORECASE) or "oscillator" in lower or "crystal" in lower:
            ref_clock_pins.append(record)
        if "video input" in lower or name.upper().startswith("VIN"):
            analog_video_inputs.append(record)
        if any(token in lower for token in ("serial-data", "serial data", "coax", "twisted-pair", "gmsl", "fpd-link", "rin+", "rin-", "rin0", "rin1", "rxin")):
            serial_links.append(record)
        if pin_data.get("direction") == "OUTPUT" and any(token in lower for token in ("mipi", "csi-2", "csi2", "lane")):
            mipi_outputs.append(record)
        if re.match(r"^VD\d", name.upper()) or "video data" in lower or "parallel" in lower or "hsync" in lower or "vsync" in lower or "pclk" in lower:
            parallel_video_outputs.append(record)
        if "cfg" in name.lower() or "configuration pin" in lower or re.search(r"\bMODE\b|\bIDX\b", f"{name} {desc}", re.IGNORECASE):
            config_pins.append(record)
        if re.search(r"\b(?:RST|RESET|RSTB|RESETB|PWDN|PWDNB|PDN|PDNB|PDB)\b", f"{name} {desc}", re.IGNORECASE):
            reset_pins.append(record)
        if re.search(r"\b(IRQ|LOCK|ERRB|INT)\b", f"{name} {desc}", re.IGNORECASE):
            status_pins.append(record)

    if not power_rails:
        for rail_name in re.findall(r"\b(VDDIO|VDD18(?:_[A-Z0-9]+)?|VDD11(?:_[A-Z0-9]+)?|VDD33|VDD_FPD\d?|AVDD\d*|DVDD\d*|IOVDD|VDD)\b", haystack):
            if rail_name in seen_rails:
                continue
            seen_rails.add(rail_name)
            power_rails.append({"name": rail_name, "purpose": "inferred_power_rail", "pins": []})
            if len(power_rails) >= 6:
                break
        if not power_rails:
            power_rails.append({"name": "VDD", "purpose": "inferred_power_rail", "pins": []})

    if not serial_links and any(token in haystack_lower for token in ("fpd-link", "coax", "stp", "serialized", "deserializer")):
        serial_links.append(placeholder("FPD_LINK_IN", "Serialized video link inferred from datasheet text."))
    if not mipi_outputs and any(token in haystack_lower for token in ("csi-2", "csi2", "mipi")):
        mipi_outputs.append(placeholder("CSI2_TX", "MIPI CSI-2 output inferred from datasheet text."))
    if not parallel_video_outputs and any(token in haystack_lower for token in ("parallel cmos", "parallel output", "hsync", "vsync", "pclk", "parallel interface")):
        parallel_video_outputs.append(placeholder("PIX_OUT", "Parallel video output inferred from datasheet text."))
    if not analog_video_inputs and any(token in haystack_lower for token in ("cvbs", "hdtvi", "ahd", "analog video", "composite")):
        analog_video_inputs.append(placeholder("VIDEO_IN", "Analog video input inferred from datasheet text."))
    if not ref_clock_pins and (
        any(token in haystack_lower for token in ("refclk", "crystal", "oscillator", "25mhz", "clock source"))
        or (serial_links and any(token in haystack_lower for token in ("fpd-link", "deserializer", "camera")))
    ):
        ref_clock_pins.extend([
            placeholder("REFCLK", "Reference clock inferred from datasheet text."),
            placeholder("XTAL", "Optional crystal source inferred from datasheet text."),
        ])
    if not config_pins and any(token in haystack_lower for token in ("mode", "idx", "strap", "configuration", "local config")):
        config_pins.append(placeholder("MODE/IDX", "Configuration straps inferred from datasheet text."))
    if not reset_pins and any(token in haystack_lower for token in ("pdb", "reset", "power-down")):
        reset_pins.append(placeholder("PDB", "Reset or power-down control inferred from datasheet text."))
    if not status_pins and any(token in haystack_lower for token in ("lock", "interrupt", "intb", "errb")):
        status_pins.append(placeholder("LOCK", "Status indication inferred from datasheet text."))
    if not i2c_available and any(token in haystack_lower for token in ("i2c", "scl", "sda", "control channel", "register programming", "local config")):
        i2c_available = True
    if i2c_available and not i2c_pins:
        i2c_pins.extend([
            placeholder("I2C_SCL", "Control bus clock inferred from datasheet text."),
            placeholder("I2C_SDA", "Control bus data inferred from datasheet text."),
        ])

    return {
        "preferred_package": preferred_package,
        "power_rails": power_rails,
        "analog_video_inputs": analog_video_inputs,
        "serial_links": serial_links,
        "mipi_outputs": mipi_outputs,
        "parallel_video_outputs": parallel_video_outputs,
        "ref_clock_pins": ref_clock_pins,
        "config_pins": config_pins,
        "reset_pins": reset_pins,
        "status_pins": status_pins,
        "i2c_pins": i2c_pins,
        "i2c_available": i2c_available,
        "poc_support": poc_support,
    }


def _decoder_external_components(decoder_context: dict) -> list[dict]:
    components = []
    for rail in decoder_context.get("power_rails", [])[:6]:
        designator = f"C{_sanitize_name(rail['name']).upper()}"
        components.append(
            {
                "role": "rail_decoupling",
                "designator": designator,
                "status": "required",
                "connect_between": [rail["name"], "GND"],
                "why": f"{rail['name']} needs local bypassing near the package pins.",
            }
        )

    if decoder_context.get("ref_clock_pins"):
        if len(decoder_context["ref_clock_pins"]) >= 2:
            components.append(
                {
                    "role": "clock_source_or_crystal",
                    "designator": "Y1/CXO1",
                    "status": "required_if_no_external_clock",
                    "connect_between": [decoder_context["ref_clock_pins"][0]["name"], decoder_context["ref_clock_pins"][1]["name"]],
                    "why": "Decoder/deserializer timing must be closed with a crystal or known-good oscillator source.",
                }
            )
        else:
            components.append(
                {
                    "role": "clock_source_or_crystal",
                    "designator": "XO1",
                    "status": "required_if_no_upstream_clock",
                    "connect_between": [decoder_context["ref_clock_pins"][0]["name"]],
                    "why": "Bring-up usually depends on a stable reference clock input.",
                }
            )

    if decoder_context.get("analog_video_inputs"):
        components.append(
            {
                "role": "ac_coupling_capacitors",
                "designator": "CAC_VIDEO",
                "status": "required_if_analog_input",
                "connect_between": ["VIDEO_IN", "decoder_input"],
                "why": "Analog video input paths in this class typically require AC-coupling at the decoder input.",
            }
        )

    if decoder_context.get("i2c_available"):
        components.append(
            {
                "role": "i2c_pullups",
                "designator": "RPU_SCL/RPU_SDA",
                "status": "recommended",
                "connect_between": ["I2C_SCL/I2C_SDA", "VDD_IO"],
                "why": "Most decoder/deserializer bring-up flows rely on an I2C control bus with defined pull-ups.",
            }
        )

    if decoder_context.get("config_pins"):
        components.append(
            {
                "role": "configuration_straps",
                "designator": "RCFG",
                "status": "recommended",
                "connect_between": ["CFG_pins", "VDDIO_or_GND"],
                "why": "Configuration pins should be frozen early so boot mode and link mapping stay deterministic.",
            }
        )

    if decoder_context.get("reset_pins"):
        components.append(
            {
                "role": "reset_bias",
                "designator": "RRESET/CRESET",
                "status": "recommended",
                "connect_between": [decoder_context["reset_pins"][0]["name"], "VDDIO_or_GND"],
                "why": "Reset/power-down pins should have a deterministic power-up state.",
            }
        )

    if decoder_context.get("mipi_outputs"):
        components.append(
            {
                "role": "csi_breakout",
                "designator": "JCSI",
                "status": "design_specific",
                "connect_between": ["CSI2_TX", "downstream_soc"],
                "why": "Expose MIPI CSI-2 lanes to the downstream processor or interposer with controlled routing.",
            }
        )
    if decoder_context.get("parallel_video_outputs"):
        components.append(
            {
                "role": "pixel_breakout",
                "designator": "JPIX",
                "status": "design_specific",
                "connect_between": ["PIX_OUT", "downstream_processor_or_fpga"],
                "why": "Parallel video outputs should be grouped at a defined schematic boundary with clock and sync ownership documented.",
            }
        )

    if decoder_context.get("serial_links"):
        components.append(
            {
                "role": "link_connector",
                "designator": "JLINK",
                "status": "design_specific",
                "connect_between": ["SER_LINK", "coax_or_stp_harness"],
                "why": "Serializer/deserializer links need a defined connector/harness boundary in the schematic partition.",
            }
        )
    if decoder_context.get("poc_support"):
        components.append(
            {
                "role": "poc_filter_network",
                "designator": "LPOC/CPOC/FBPOC",
                "status": "design_specific",
                "connect_between": ["VPOC", "SER_LINK"],
                "why": "PoC-capable deserializer links need the coax power filter network captured explicitly during schematic partitioning.",
            }
        )

    return components


def _decoder_starter_nets(decoder_context: dict) -> list[dict]:
    nets = [{"name": "GND", "purpose": "module_ground"}]
    for rail in decoder_context.get("power_rails", [])[:6]:
        nets.append({"name": rail["name"], "purpose": "decoder_power_rail"})
    if decoder_context.get("i2c_available"):
        nets.append({"name": "I2C_SCL", "purpose": "control_bus_clock"})
        nets.append({"name": "I2C_SDA", "purpose": "control_bus_data"})
    if decoder_context.get("ref_clock_pins"):
        nets.append({"name": "REFCLK", "purpose": "decoder_reference_clock"})
    if decoder_context.get("analog_video_inputs"):
        nets.append({"name": "VIDEO_IN", "purpose": "analog_video_input"})
    if decoder_context.get("serial_links"):
        nets.append({"name": "SER_LINK", "purpose": "serialized_video_link"})
    if decoder_context.get("mipi_outputs"):
        nets.append({"name": "CSI2_TX", "purpose": "mipi_csi2_output"})
    if decoder_context.get("parallel_video_outputs"):
        nets.append({"name": "PIX_OUT", "purpose": "parallel_video_output"})
    if decoder_context.get("reset_pins"):
        nets.append({"name": "RESET_N", "purpose": "decoder_reset_or_powerdown"})
    return nets


def _decoder_topology_candidates(decoder_context: dict) -> list[dict]:
    candidates = []
    if decoder_context.get("analog_video_inputs") and (decoder_context.get("mipi_outputs") or decoder_context.get("parallel_video_outputs")):
        candidates.append(
            {
                "name": "analog_video_decoder_to_csi",
                "label": "Analog Video Decoder",
                "why": "Analog front-end, clock source, control bus, and downstream video output all need to be partitioned together.",
                "source_pages": [],
                "nets": [
                    {"name": "VIDEO_IN", "purpose": "analog_video_input"},
                    {"name": "I2C_SCL", "purpose": "control_bus_clock"},
                    {"name": "I2C_SDA", "purpose": "control_bus_data"},
                    {"name": "REFCLK", "purpose": "decoder_reference_clock"},
                    {"name": "CSI2_TX", "purpose": "mipi_csi2_output"},
                ],
                "blocks": [
                    {"ref": "Y1", "type": "timing_source", "role": "reference_clock"},
                    {"ref": "JVIDEO", "type": "connector", "role": "analog_video_input"},
                    {"ref": "JCSI", "type": "connector", "role": "video_output"},
                ],
                "todo": ["Freeze input video standard, lane mapping, and reference clock source before schematic release."],
            }
        )
    if decoder_context.get("serial_links") and decoder_context.get("mipi_outputs"):
        candidates.append(
            {
                "name": "serial_deserializer_to_csi",
                "label": "Deserializer to CSI-2 Bridge",
                "why": "Serialized coax/STP links, sideband control, and CSI-2 breakout must be reviewed as one module boundary.",
                "source_pages": [],
                "nets": [
                    {"name": "SER_LINK", "purpose": "serialized_video_link"},
                    {"name": "I2C_SCL", "purpose": "control_bus_clock"},
                    {"name": "I2C_SDA", "purpose": "control_bus_data"},
                    {"name": "REFCLK", "purpose": "decoder_reference_clock"},
                    {"name": "CSI2_TX", "purpose": "mipi_csi2_output"},
                ],
                "blocks": [
                    {"ref": "Y1", "type": "timing_source", "role": "reference_clock"},
                    {"ref": "JLINK", "type": "connector", "role": "serialized_link_input"},
                    {"ref": "JCSI", "type": "connector", "role": "video_output"},
                ],
                "todo": ["Freeze GMSL/link channel mapping, control-bus ownership, and CSI lane count before routing starts."],
            }
        )
    if decoder_context.get("serial_links") and decoder_context.get("parallel_video_outputs"):
        candidates.append(
            {
                "name": "serial_deserializer_to_parallel",
                "label": "Deserializer to Parallel Video",
                "why": "Serialized FPD-Link inputs, sideband control, reference timing, and pixel bus breakout need to be captured as one schematic module.",
                "source_pages": [],
                "nets": [
                    {"name": "SER_LINK", "purpose": "serialized_video_link"},
                    {"name": "I2C_SCL", "purpose": "control_bus_clock"},
                    {"name": "I2C_SDA", "purpose": "control_bus_data"},
                    {"name": "REFCLK", "purpose": "decoder_reference_clock"},
                    {"name": "PIX_OUT", "purpose": "parallel_video_output"},
                ],
                "blocks": [
                    {"ref": "Y1", "type": "timing_source", "role": "reference_clock"},
                    {"ref": "JLINK", "type": "connector", "role": "serialized_link_input"},
                    {"ref": "JPIX", "type": "connector", "role": "parallel_video_output"},
                ],
                "todo": ["Freeze pixel-bus width, sync polarity, and downstream receiver ownership before schematic review."],
            }
        )
    return candidates


def _choose_default_decoder_template(decoder_templates: list[dict], topology_candidates: list[dict]) -> str | None:
    if not decoder_templates:
        return None
    template_names = {item.get("name") for item in decoder_templates}
    for preferred in ("serial_deserializer_to_csi", "serial_deserializer_to_parallel", "analog_video_decoder_to_csi"):
        if preferred in template_names:
            return preferred
    return decoder_templates[0].get("name")


def _decoder_standard_templates(device: dict, decoder_context: dict, topology_candidates: list[dict]) -> list[dict]:
    templates = []
    candidate_map = {item["name"]: item for item in topology_candidates}

    def add_template(name: str, label: str, sheet_name: str, recommended_when: str, summary: str, nets: list[str], blocks: list[str], connections: list[dict], checklist: list[str], based_on: str | None = None) -> None:
        templates.append(
            {
                "name": name,
                "label": label,
                "sheet_name": sheet_name,
                "recommended_when": recommended_when,
                "summary": summary,
                "nets": nets,
                "blocks": blocks,
                "default_refdes_map": {block: block for block in blocks},
                "connections": connections,
                "checklist": checklist,
                "based_on_topology": based_on,
            }
        )

    if "analog_video_decoder_to_csi" in candidate_map:
        add_template(
            "analog_video_decoder_to_csi",
            "Analog Video Decoder to CSI-2",
            "V1_video_decoder",
            "Use when composite/HD analog video enters the decoder and exits toward a CSI-2 or pixel interface receiver.",
            "Partitions analog video input, reference clock, control bus, and downstream video output around one decoder IC.",
            ["VIDEO_IN", "I2C_SCL", "I2C_SDA", "REFCLK", "CSI2_TX", "RESET_N"],
            ["U1", "Y1", "CAC_VIDEO", "RPU_SCL", "RPU_SDA", "JVIDEO", "JCSI"],
            [
                {"from": "JVIDEO", "to": "VIDEO_IN", "note": "Bring analog video into the decoder through the protected input boundary."},
                {"from": "VIDEO_IN", "to": "CAC_VIDEO", "note": "Keep AC-coupling at the decoder side when required by the datasheet."},
                {"from": "REFCLK", "to": "Y1", "note": "Close the reference clock source before register bring-up work starts."},
                {"from": "I2C_SCL", "to": "RPU_SCL", "note": "Bias the control bus to the chosen IO domain."},
                {"from": "I2C_SDA", "to": "RPU_SDA", "note": "Bias the control bus to the chosen IO domain."},
                {"from": "CSI2_TX", "to": "JCSI", "note": "Break out the video stream toward the host processor or test header."},
            ],
            [
                "Freeze video input standard and CSI/pixel output mapping before schematic review.",
                "Tie reset/power-down pins to a deterministic boot state.",
            ],
            based_on="analog_video_decoder_to_csi",
        )

    if "serial_deserializer_to_csi" in candidate_map:
        add_template(
            "serial_deserializer_to_csi",
            "Deserializer to CSI-2",
            "V1_deserializer_bridge",
            "Use when a GMSL or serialized coax/STP link terminates at the decoder and forwards video over CSI-2.",
            "Partitions serializer link inputs, sideband control, reference clock, and CSI-2 output around one deserializer.",
            ["SER_LINK", "I2C_SCL", "I2C_SDA", "REFCLK", "CSI2_TX", "RESET_N"],
            ["U1", "Y1", "RPU_SCL", "RPU_SDA", "JLINK", "JCSI"],
            [
                {"from": "JLINK", "to": "SER_LINK", "note": "Land the incoming serialized video harness at a clear module boundary."},
                {"from": "REFCLK", "to": "Y1", "note": "Reference timing should be fixed before software bring-up."},
                {"from": "I2C_SCL", "to": "RPU_SCL", "note": "Provide control-bus pull-up to the selected IO rail."},
                {"from": "I2C_SDA", "to": "RPU_SDA", "note": "Provide control-bus pull-up to the selected IO rail."},
                {"from": "CSI2_TX", "to": "JCSI", "note": "Break out CSI-2 toward the downstream SoC with lane ownership documented."},
            ],
            [
                "Freeze link channel ownership and CSI lane mapping before routing.",
                "Verify power sequencing for core, IO, and MIPI rails.",
            ],
            based_on="serial_deserializer_to_csi",
        )

    if "serial_deserializer_to_parallel" in candidate_map:
        add_template(
            "serial_deserializer_to_parallel",
            "Deserializer to Parallel Video",
            "V1_deserializer_parallel",
            "Use when a serialized FPD-Link stream terminates at the decoder and exits through a parallel CMOS or pixel bus.",
            "Partitions serialized link input, control bus, reference timing, and pixel bus breakout around one deserializer.",
            ["SER_LINK", "I2C_SCL", "I2C_SDA", "REFCLK", "PIX_OUT", "RESET_N"],
            ["U1", "Y1", "RPU_SCL", "RPU_SDA", "JLINK", "JPIX"],
            [
                {"from": "JLINK", "to": "SER_LINK", "note": "Land the incoming serialized video harness at a clear module boundary."},
                {"from": "REFCLK", "to": "Y1", "note": "Reference timing should be fixed before software bring-up."},
                {"from": "I2C_SCL", "to": "RPU_SCL", "note": "Provide control-bus pull-up to the selected IO rail."},
                {"from": "I2C_SDA", "to": "RPU_SDA", "note": "Provide control-bus pull-up to the selected IO rail."},
                {"from": "PIX_OUT", "to": "JPIX", "note": "Break out pixel clock, sync, and video bus ownership toward the downstream receiver."},
            ],
            [
                "Freeze pixel-bus width and sync polarity before review.",
                "Verify power sequencing for core, IO, and parallel output rails.",
            ],
            based_on="serial_deserializer_to_parallel",
        )

    return templates


def _opamp_topology_candidates(design_intent: dict) -> list[dict]:
    datasheet_context = design_intent.get("datasheet_design_context", {})
    page_candidates = datasheet_context.get("design_page_candidates", [])
    external_roles = {item.get("role") for item in design_intent.get("external_components", [])}
    equation_text = " ".join(item.get("equation", "") for item in datasheet_context.get("design_equation_hints", []))

    candidates: list[dict] = []
    seen: set[str] = set()

    def add_candidate(name: str, label: str, why: str, source_pages: list[int], nets: list[dict], blocks: list[dict], todos: list[str]) -> None:
        if name in seen:
            return
        seen.add(name)
        candidates.append(
            {
                "name": name,
                "label": label,
                "why": why,
                "source_pages": source_pages,
                "nets": nets,
                "blocks": blocks,
                "todo": todos,
            }
        )

    for page in page_candidates:
        preview = (page.get("preview") or "").lower()
        source_pages = [page.get("page_num")]

        if "thermocouple amplifier" in preview:
            add_candidate(
                "thermocouple_frontend",
                "Thermocouple Front End",
                "Cold-junction compensation and gain staging are needed for thermocouple sensing.",
                source_pages,
                [
                    {"name": "TC_P", "purpose": "thermocouple_positive_input"},
                    {"name": "TC_N", "purpose": "thermocouple_negative_input"},
                    {"name": "CJ_SENSE", "purpose": "cold_junction_compensation_node"},
                    {"name": "VREF", "purpose": "analog_reference"},
                    {"name": "VOUT_ANA", "purpose": "conditioned_sensor_output"},
                ],
                [
                    {"ref": "XTC1", "type": "topology_block", "role": "thermocouple_sensor"},
                    {"ref": "XCJ1", "type": "topology_block", "role": "cold_junction_compensation"},
                    {"ref": "RGAIN_TC", "type": "support_component", "role": "gain_network"},
                ],
                ["Place the cold-junction compensation element close to the thermocouple termination."],
            )

        if "strain gage" in preview:
            add_candidate(
                "strain_gage_frontend",
                "Strain Gage Front End",
                "Bridge excitation, reference generation, and gain staging are all needed for strain-gage modules.",
                source_pages,
                [
                    {"name": "BRIDGE_EXC", "purpose": "bridge_excitation"},
                    {"name": "BRIDGE_P", "purpose": "bridge_positive_sense"},
                    {"name": "BRIDGE_N", "purpose": "bridge_negative_sense"},
                    {"name": "VREF", "purpose": "bridge_reference"},
                    {"name": "VOUT_ANA", "purpose": "amplified_bridge_output"},
                ],
                [
                    {"ref": "XBRIDGE1", "type": "topology_block", "role": "bridge_sensor"},
                    {"ref": "XREF1", "type": "topology_block", "role": "reference_buffer"},
                    {"ref": "RGAIN_BR", "type": "support_component", "role": "gain_network"},
                ],
                ["Freeze bridge excitation and reference polarity before PCB symbol pin-swap decisions."],
            )

        if "bandpass filter" in preview:
            add_candidate(
                "active_filter",
                "Active Filter",
                "Multiple-feedback RC networks are needed for the filter response shown in the datasheet.",
                source_pages,
                [
                    {"name": "VIN_SIG", "purpose": "analog_input_signal"},
                    {"name": "VREF", "purpose": "filter_reference"},
                    {"name": "FILTER_OUT", "purpose": "filtered_output"},
                ],
                [
                    {"ref": "XFILT1", "type": "topology_block", "role": "active_filter_core"},
                    {"ref": "RFILT", "type": "support_component", "role": "filter_resistor_network"},
                    {"ref": "CFILT", "type": "support_component", "role": "filter_capacitor_network"},
                ],
                ["Back-annotate target center frequency and Q into RFILT/CFILT before capture freeze."],
            )

        if "function generator" in preview or "voltage follower" in preview:
            add_candidate(
                "buffer_stage",
                "Buffer / Generator Stage",
                "The datasheet shows a buffered analog stage that benefits from a dedicated input, feedback, and reference partition.",
                source_pages,
                [
                    {"name": "VIN_SIG", "purpose": "analog_input_signal"},
                    {"name": "VREF", "purpose": "bias_reference"},
                    {"name": "BUF_OUT", "purpose": "buffered_output"},
                ],
                [
                    {"ref": "XBUF1", "type": "topology_block", "role": "buffer_stage"},
                    {"ref": "RFBUF", "type": "support_component", "role": "feedback_network"},
                ],
                ["Decide whether the op amp is used as a follower or gain stage before assigning passive values."],
            )

        if "capacitive load drive" in preview or "snubber network" in preview:
            add_candidate(
                "capacitive_load_driver",
                "Capacitive Load Driver",
                "The datasheet explicitly recommends an RC snubber when driving capacitive loads.",
                source_pages,
                [
                    {"name": "VOUT_ANA", "purpose": "driven_output"},
                    {"name": "LOAD_CAP", "purpose": "capacitive_load"},
                ],
                [
                    {"ref": "RSNUB", "type": "support_component", "role": "snubber_resistor"},
                    {"ref": "CSNUB", "type": "support_component", "role": "snubber_capacitor"},
                    {"ref": "CLOAD", "type": "support_component", "role": "output_capacitor"},
                ],
                ["Reserve layout room for the snubber RC close to the op amp output pin."],
            )

    if "rsense" in equation_text.lower() or "sense_resistor" in external_roles:
        add_candidate(
            "current_sense_frontend",
            "Current Sense Front End",
            "A sense resistor and gain path are present in the extracted equations and component hints.",
            [item.get("source_page") for item in datasheet_context.get("design_equation_hints", []) if "RSENSE" in item.get("equation", "")],
            [
                {"name": "SENSE_P", "purpose": "current_sense_positive"},
                {"name": "SENSE_N", "purpose": "current_sense_negative"},
                {"name": "MON_OUT", "purpose": "scaled_monitor_output"},
            ],
            [
                {"ref": "RSENSE", "type": "support_component", "role": "sense_resistor"},
                {"ref": "RGAIN_CS", "type": "support_component", "role": "gain_network"},
            ],
            ["Confirm sense resistor Kelvin routing before finalizing connector pinout."],
        )

    application_pages = [page.get("page_num") for page in page_candidates if page.get("kind") == "application" and page.get("page_num") is not None]
    if "filter_network" in external_roles:
        add_candidate(
            "active_filter",
            "Active Filter",
            "Extracted RC filter support parts indicate an active filter stage even when the preview text is too noisy to classify directly.",
            application_pages[:2],
            [
                {"name": "VIN_SIG", "purpose": "analog_input_signal"},
                {"name": "VREF", "purpose": "filter_reference"},
                {"name": "FILTER_OUT", "purpose": "filtered_output"},
            ],
            [
                {"ref": "XFILT1", "type": "topology_block", "role": "active_filter_core"},
                {"ref": "RFILT", "type": "support_component", "role": "filter_resistor_network"},
                {"ref": "CFILT", "type": "support_component", "role": "filter_capacitor_network"},
            ],
            ["Back-annotate target center frequency and Q into RFILT/CFILT before capture freeze."],
        )
        add_candidate(
            "buffer_stage",
            "Buffer / Generator Stage",
            "Filter-oriented application pages usually pair with a buffer or follower stage that is useful as a fast schematic starting point.",
            application_pages[:2],
            [
                {"name": "VIN_SIG", "purpose": "analog_input_signal"},
                {"name": "VREF", "purpose": "bias_reference"},
                {"name": "BUF_OUT", "purpose": "buffered_output"},
            ],
            [
                {"ref": "XBUF1", "type": "topology_block", "role": "buffer_stage"},
                {"ref": "RFBUF", "type": "support_component", "role": "feedback_network"},
            ],
            ["Decide whether the op amp is used as a follower or gain stage before assigning passive values."],
        )

    if not candidates and ({"gain_resistor", "feedback_network", "feedback_divider"} & external_roles):
        add_candidate(
            "generic_gain_stage",
            "Generic Gain Stage",
            "A conventional op-amp gain stage is implied by the feedback components extracted from the datasheet.",
            [],
            [
                {"name": "VIN_SIG", "purpose": "analog_input_signal"},
                {"name": "VREF", "purpose": "bias_reference"},
                {"name": "VOUT_ANA", "purpose": "amplified_output"},
            ],
            [
                {"ref": "RIN", "type": "support_component", "role": "input_resistor"},
                {"ref": "RFB", "type": "support_component", "role": "feedback_resistor"},
            ],
            ["Choose inverting or non-inverting topology before locking symbol pin names."],
        )

    return candidates


def _choose_default_opamp_template(opamp_templates: list[dict], topology_candidates: list[dict]) -> str | None:
    if not opamp_templates:
        return None
    preferred_by_topology = {
        "thermocouple_frontend": "thermocouple_frontend",
        "strain_gage_frontend": "strain_gage_frontend",
        "current_sense_frontend": "current_sense_frontend",
        "capacitive_load_driver": "capacitive_load_driver",
        "active_filter": "active_filter",
        "buffer_stage": "buffer_stage",
    }
    topology_names = [item.get("name") for item in topology_candidates]
    template_names = {item.get("name") for item in opamp_templates}
    for topology_name in topology_names:
        preferred = preferred_by_topology.get(topology_name)
        if preferred in template_names:
            return preferred
    for fallback in ("non_inverting_gain_stage", "inverting_gain_stage"):
        if fallback in template_names:
            return fallback
    return opamp_templates[0].get("name")


def _extract_opamp_channel_name(*values: str) -> str | None:
    text = " ".join(value or "" for value in values)
    for pattern in (
        r"\bchannel\s+([A-Z0-9])\b",
        r"\b(?:\+IN|-IN|OUT)\s*([A-Z0-9])\b",
        r"\b(?:non[- ]?inverting input|noninverting input|inverting input|output)\s*([A-Z0-9])\b",
        r"\b([A-Z0-9])\s*(?:output|inverting input|non[- ]?inverting input|noninverting input)\b",
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            token = match.group(1).upper()
            if token.isdigit():
                try:
                    return chr(ord('A') + int(token) - 1)
                except Exception:
                    return token
            return token
    return None


def _classify_opamp_pin_role(pin_data: dict) -> str | None:
    name = (pin_data.get("name") or "").strip()
    description = (pin_data.get("description") or "").strip()
    upper_name = name.upper()
    lower_name = name.lower()
    lower_desc = description.lower()

    if upper_name in {"NC", "NIC"} or "not internally connected" in lower_desc:
        return None
    if "+IN" in upper_name or "non-inverting input" in lower_name or "noninverting input" in lower_name:
        return "IN+"
    if "-IN" in upper_name or ("inverting input" in lower_name and "non-inverting" not in lower_name and "noninverting" not in lower_name):
        return "IN-"
    if re.search(r"\bOUT[A-Z0-9]*\b", upper_name) or lower_name.startswith("output"):
        return "OUT"

    if "negative power supply" in lower_desc or "negative supply voltage" in lower_desc or "ground" in lower_desc:
        return "PWR-"
    if "positive power supply" in lower_desc or "positive supply voltage" in lower_desc:
        return "PWR+"

    if re.fullmatch(r"(?:V\+|VCC|VDD|\+VS|VS\+)", upper_name) or lower_name in {"v+", "vcc", "vdd", "+vs", "vs+"}:
        return "PWR+"
    if re.fullmatch(r"(?:V-|VEE|VSS|-VS|GND|VEE/GND)", upper_name) or lower_name in {"v-", "vee", "vss", "-vs", "gnd", "vee/gnd"}:
        return "PWR-"
    return None


def _infer_opamp_traits(device: dict, design_intent: dict) -> dict:
    preferred_package = design_intent.get("device_ref", {}).get("preferred_package") or _pick_preferred_package(device)

    def analyze_package(package_name: str | None) -> dict:
        package_data = device.get("packages", {}).get(package_name or "", {}) if package_name else {}
        pins = package_data.get("pins", {})
        channel_map: dict[str, dict] = {}
        package_pin_lookup: dict[str, dict] = {}
        shared_power_pins = {"positive": [], "negative": []}

        for pin_number, pin_data in pins.items():
            pin_name = pin_data.get("name") or ""
            description = pin_data.get("description") or ""
            channel_name = _extract_opamp_channel_name(pin_name, description)
            pin_role = _classify_opamp_pin_role(pin_data)

            if channel_name:
                bucket = channel_map.setdefault(
                    channel_name,
                    {
                        "channel": channel_name,
                        "symbol_unit": f"U1{channel_name}",
                        "pins": [],
                        "package_bindings": {},
                        "package_pin_names": {},
                    },
                )
                if pin_number not in bucket["pins"]:
                    bucket["pins"].append(pin_number)
                if pin_role in {"IN+", "IN-", "OUT"}:
                    bucket["package_bindings"][pin_role] = pin_number
                    bucket["package_pin_names"][pin_role] = pin_name
                    package_pin_lookup[f"U1{channel_name}.{pin_role}"] = {
                        "pin": pin_number,
                        "name": pin_name,
                        "description": description,
                    }

            if pin_role == "PWR+":
                shared_power_pins["positive"].append({"pin": pin_number, "name": pin_name})
            elif pin_role == "PWR-":
                shared_power_pins["negative"].append({"pin": pin_number, "name": pin_name})

        channels = [channel_map[key] for key in sorted(channel_map)]
        if not channels:
            channels = [{"channel": "A", "symbol_unit": "U1A", "pins": [], "package_bindings": {}, "package_pin_names": {}}]
        return {
            "package_name": package_name,
            "channel_units": channels,
            "channel_count": len(channels),
            "package_pin_lookup": package_pin_lookup,
            "shared_power_pins": shared_power_pins,
            "pin_count": package_data.get("pin_count"),
        }

    preferred_analysis = analyze_package(preferred_package)
    channels = preferred_analysis["channel_units"]
    package_pin_lookup = preferred_analysis["package_pin_lookup"]
    shared_power_pins = preferred_analysis["shared_power_pins"]
    package_variants = []
    for package_name in sorted(device.get("packages", {}).keys()):
        variant = analyze_package(package_name)
        package_variants.append(
            {
                "package_name": package_name,
                "pin_count": variant.get("pin_count"),
                "channel_count": variant["channel_count"],
                "channel_units": [item["symbol_unit"] for item in variant["channel_units"]],
                "shared_power_pins": variant["shared_power_pins"],
            }
        )

    description = (device.get("description") or "").lower()
    power_pin_names = [
        (pin.get("name") or "")
        for pin in design_intent.get("pin_groups", {}).get("power_inputs", [])
    ]
    power_text = " ".join(power_pin_names).lower()

    if "single-supply" in description or "single supply" in description:
        supply_style = "single_supply"
    elif "dual-supply" in description or "dual supply" in description:
        supply_style = "dual_supply"
    elif "vee/gnd" in power_text or "ground" in power_text:
        supply_style = "single_supply"
    elif any(token in power_text for token in ("v-", "vee", "vss")):
        supply_style = "dual_supply_capable"
    else:
        supply_style = "unspecified"

    if supply_style == "single_supply":
        bias_strategy = "midrail_reference"
        negative_supply_net = "GND"
        reference_net = "VREF"
    elif supply_style in {"dual_supply", "dual_supply_capable"}:
        bias_strategy = "ground_centered_or_midrail_per_signal_swing"
        negative_supply_net = "V-"
        reference_net = "GND"
    else:
        bias_strategy = "decide_reference_from_signal_swing"
        negative_supply_net = "GND"
        reference_net = "VREF"

    return {
        "preferred_package": preferred_package,
        "channel_count": len(channels),
        "channel_units": channels,
        "primary_signal_unit": channels[0]["symbol_unit"],
        "supply_style": supply_style,
        "bias_strategy": bias_strategy,
        "shared_power_pins": shared_power_pins,
        "package_pin_lookup": package_pin_lookup,
        "package_variants": package_variants,
        "suggested_power_nets": {
            "positive": "V+",
            "negative": negative_supply_net,
            "reference": reference_net,
        },
    }


def _opamp_template_net_bindings(template_nets: list[str], opamp_traits: dict) -> list[dict]:
    bindings = []
    net_roles = {
        "VIN_SIG": "analog_input",
        "VOUT_ANA": "analog_output",
        "FILTER_OUT": "filtered_output",
        "BUF_OUT": "buffered_output",
        "VREF": "bias_reference",
        "LOAD_CAP": "load_representation",
        "BRIDGE_EXC": "bridge_excitation",
        "BRIDGE_P": "bridge_positive_input",
        "BRIDGE_N": "bridge_negative_input",
        "TC_P": "thermocouple_positive_input",
        "TC_N": "thermocouple_negative_input",
        "CJ_SENSE": "cold_junction_sense",
        "SENSE_P": "current_sense_positive",
        "SENSE_N": "current_sense_negative",
        "MON_OUT": "monitor_output",
    }
    for net_name in template_nets:
        role = net_roles.get(net_name, "application_net")
        binding = {"net": net_name, "role": role}
        if net_name == "VREF":
            binding["recommended_when"] = "single_supply_biasing"
        bindings.append(binding)

    bindings.extend(
        [
            {"net": opamp_traits["suggested_power_nets"]["positive"], "role": "positive_supply"},
            {"net": opamp_traits["suggested_power_nets"]["negative"], "role": "negative_supply"},
        ]
    )
    return bindings


def _opamp_template_pin_bindings(connections: list[dict], primary_unit: str, opamp_traits: dict) -> list[dict]:
    bindings = []
    seen: set[tuple[str, str]] = set()
    package_pin_lookup = opamp_traits.get("package_pin_lookup", {})
    shared_power_pins = opamp_traits.get("shared_power_pins", {})

    def attach_package_pin(record: dict) -> None:
        binding = package_pin_lookup.get(record["symbol_pin"])
        if not binding and record["symbol_pin"].endswith(".PWR+"):
            positive_pins = shared_power_pins.get("positive", [])
            if positive_pins:
                binding = dict(positive_pins[0])
                binding["shared_across_units"] = True
        if not binding and record["symbol_pin"].endswith(".PWR-"):
            negative_pins = shared_power_pins.get("negative", [])
            if negative_pins:
                binding = dict(negative_pins[0])
                binding["shared_across_units"] = True
        if not binding:
            return
        record["package_pin"] = binding.get("pin")
        record["package_pin_name"] = binding.get("name")
        if binding.get("shared_across_units"):
            record["shared_across_units"] = True

    for connection in connections:
        for endpoint_key in ("from", "to"):
            endpoint = connection.get(endpoint_key) or ""
            if not endpoint.startswith(primary_unit + "."):
                continue
            pin_name = endpoint.split(".", 1)[1]
            role = {
                "IN+": "non_inverting_input",
                "IN-": "inverting_input",
                "OUT": "output",
            }.get(pin_name, "signal_pin")
            note = connection.get("note")
            other = connection.get("to") if endpoint_key == "from" else connection.get("from")
            record = {
                "symbol_pin": endpoint,
                "role": role,
                "connect_to": other,
            }
            if note:
                record["note"] = note
            attach_package_pin(record)
            signature = (record["symbol_pin"], record["connect_to"] or "")
            if signature in seen:
                continue
            seen.add(signature)
            bindings.append(record)

    positive_binding = {
        "symbol_pin": f"{primary_unit}.PWR+",
        "role": "positive_supply",
        "connect_to": opamp_traits["suggested_power_nets"]["positive"],
    }
    attach_package_pin(positive_binding)
    bindings.append(positive_binding)

    negative_binding = {
        "symbol_pin": f"{primary_unit}.PWR-",
        "role": "negative_supply",
        "connect_to": opamp_traits["suggested_power_nets"]["negative"],
    }
    attach_package_pin(negative_binding)
    bindings.append(negative_binding)
    return bindings


def _opamp_sheet_instances(opamp_traits: dict, sheet_name: str) -> list[dict]:
    channels = opamp_traits.get("channel_units", [])
    if not channels:
        channels = [{"channel": "A", "symbol_unit": opamp_traits["primary_signal_unit"], "package_bindings": {}}]

    instances = [
        {
            "instance_name": "primary_signal_path",
            "sheet_name": sheet_name,
            "opamp_unit": channels[0]["symbol_unit"],
            "status": "default",
            "package_bindings": channels[0].get("package_bindings", {}),
        }
    ]
    for channel in channels[1:]:
        instances.append(
            {
                "instance_name": f"optional_clone_{channel['channel'].lower()}",
                "sheet_name": sheet_name,
                "opamp_unit": channel["symbol_unit"],
                "status": "optional_reuse",
                "package_bindings": channel.get("package_bindings", {}),
            }
        )
    return instances


def _opamp_standard_templates(device: dict, design_intent: dict, topology_candidates: list[dict]) -> list[dict]:
    opamp_traits = _infer_opamp_traits(device, design_intent)
    primary_unit = opamp_traits["primary_signal_unit"]
    templates = [
        {
            "name": "non_inverting_gain_stage",
            "label": "Non-Inverting Gain Stage",
            "sheet_name": "A1_non_inverting_gain",
            "recommended_when": "Use for sensor buffering or moderate gain where input impedance should stay high.",
            "summary": "Single op amp stage with feedback divider from output to inverting input and direct signal injection to non-inverting input.",
            "nets": ["VIN_SIG", "VREF", "VOUT_ANA"],
            "blocks": [primary_unit, "RIN_BIAS", "RFB_TOP", "RFB_BOT", "CBYP"],
            "connections": [
                {"from": "VIN_SIG", "to": f"{primary_unit}.IN+", "note": "Route source signal into the non-inverting input."},
                {"from": f"{primary_unit}.OUT", "to": "RFB_TOP", "note": "Feedback upper leg returns output to the inverting node."},
                {"from": "RFB_TOP", "to": f"{primary_unit}.IN-", "note": "Close the gain loop locally around the op amp."},
                {"from": f"{primary_unit}.IN-", "to": "RFB_BOT", "note": "Lower leg defines closed-loop gain against VREF or GND."},
                {"from": f"{primary_unit}.OUT", "to": "VOUT_ANA", "note": "Expose amplified signal to the next sheet or connector."},
            ],
            "checklist": [
                "Set closed-loop gain before choosing resistor ratio.",
                "Verify input common-mode range against VIN_SIG and VREF.",
            ],
        },
        {
            "name": "inverting_gain_stage",
            "label": "Inverting Gain Stage",
            "sheet_name": "A1_inverting_gain",
            "recommended_when": "Use when source impedance is controlled and polarity inversion is acceptable.",
            "summary": "Single op amp stage with input resistor into the inverting node and reference/bias on the non-inverting node.",
            "nets": ["VIN_SIG", "VREF", "VOUT_ANA"],
            "blocks": [primary_unit, "RIN", "RFB", "RBIAS", "CBYP"],
            "connections": [
                {"from": "VIN_SIG", "to": "RIN", "note": "Inject source through the input resistor."},
                {"from": "RIN", "to": f"{primary_unit}.IN-", "note": "Sum input current at the inverting node."},
                {"from": f"{primary_unit}.OUT", "to": "RFB", "note": "Feedback resistor sets gain with RIN."},
                {"from": "RFB", "to": f"{primary_unit}.IN-", "note": "Keep the feedback loop compact."},
                {"from": "VREF", "to": f"{primary_unit}.IN+", "note": "Bias the non-inverting input to the desired reference."},
            ],
            "checklist": [
                "Confirm source can drive RIN without bandwidth loss.",
                "Check output swing against required inverted amplitude.",
            ],
        },
    ]

    candidate_map = {item["name"]: item for item in topology_candidates}

    def add_template(name: str, label: str, sheet_name: str, recommended_when: str, summary: str, nets: list[str], blocks: list[str], connections: list[dict], checklist: list[str], based_on: str | None = None) -> None:
        refdes_map = {block: block for block in blocks}
        templates.append(
            {
                "name": name,
                "label": label,
                "sheet_name": sheet_name,
                "recommended_when": recommended_when,
                "summary": summary,
                "nets": nets,
                "blocks": blocks,
                "default_refdes_map": refdes_map,
                "sheet_instances": _opamp_sheet_instances(opamp_traits, sheet_name),
                "pin_bindings": _opamp_template_pin_bindings(connections, primary_unit, opamp_traits),
                "net_bindings": _opamp_template_net_bindings(nets, opamp_traits),
                "power_strategy": {
                    "supply_style": opamp_traits["supply_style"],
                    "bias_strategy": opamp_traits["bias_strategy"],
                    "positive_supply_net": opamp_traits["suggested_power_nets"]["positive"],
                    "negative_supply_net": opamp_traits["suggested_power_nets"]["negative"],
                    "reference_net": opamp_traits["suggested_power_nets"]["reference"],
                },
                "connections": connections,
                "checklist": checklist,
                "based_on_topology": based_on,
            }
        )

    for template in templates:
        template["default_refdes_map"] = {block: block for block in template["blocks"]}
        template["sheet_instances"] = _opamp_sheet_instances(opamp_traits, template["sheet_name"])
        template["pin_bindings"] = _opamp_template_pin_bindings(template["connections"], primary_unit, opamp_traits)
        template["net_bindings"] = _opamp_template_net_bindings(template["nets"], opamp_traits)
        template["power_strategy"] = {
            "supply_style": opamp_traits["supply_style"],
            "bias_strategy": opamp_traits["bias_strategy"],
            "positive_supply_net": opamp_traits["suggested_power_nets"]["positive"],
            "negative_supply_net": opamp_traits["suggested_power_nets"]["negative"],
            "reference_net": opamp_traits["suggested_power_nets"]["reference"],
        }

    if "active_filter" in candidate_map:
        add_template(
            "active_filter",
            "Multiple-Feedback Active Filter",
            "A1_active_filter",
            "Use when the datasheet shows bandpass or notch behavior that should be preserved in the first schematic draft.",
            "RC network around the op amp defines center frequency, Q, and gain for a bandpass/notch stage.",
            ["VIN_SIG", "VREF", "FILTER_OUT"],
            [primary_unit, "RFILT1", "RFILT2", "RFILT3", "CFILT1", "CFILT2"],
            [
                {"from": "VIN_SIG", "to": "RFILT1", "note": "Drive the filter input through the front-end resistor."},
                {"from": "RFILT1", "to": f"{primary_unit}.IN-", "note": "Land input current at the inverting node."},
                {"from": f"{primary_unit}.OUT", "to": "RFILT2", "note": "Feedback resistor shapes gain and Q."},
                {"from": "RFILT2", "to": f"{primary_unit}.IN-", "note": "Keep the loop compact and symmetric with CFILT parts."},
                {"from": "VREF", "to": f"{primary_unit}.IN+", "note": "Bias the filter around a mid-supply reference when single-supply."},
                {"from": f"{primary_unit}.OUT", "to": "FILTER_OUT", "note": "Expose filtered output to ADC or downstream stage."},
            ],
            ["Back-annotate target center frequency, Q, and gain into RFILT/CFILT values."],
            based_on="active_filter",
        )

    if "buffer_stage" in candidate_map:
        add_template(
            "buffer_stage",
            "Buffer / Follower",
            "A1_buffer_stage",
            "Use for impedance isolation, reference buffering, or a unity/near-unity analog stage.",
            "Minimal op amp stage with direct output feedback and optional series isolation at the output.",
            ["VIN_SIG", "VREF", "BUF_OUT"],
            [primary_unit, "RISO", "CBYP"],
            [
                {"from": "VIN_SIG", "to": f"{primary_unit}.IN+", "note": "Drive the high-impedance input directly from the source."},
                {"from": f"{primary_unit}.OUT", "to": f"{primary_unit}.IN-", "note": "Short feedback for follower mode, or replace with RFBUF for slight gain."},
                {"from": f"{primary_unit}.OUT", "to": "RISO", "note": "Optional series isolation helps with capacitive loads."},
                {"from": "RISO", "to": "BUF_OUT", "note": "Present the buffered output to the next stage."},
            ],
            ["Decide whether output isolation resistor is required for the load capacitance."],
            based_on="buffer_stage",
        )

    if "capacitive_load_driver" in candidate_map:
        add_template(
            "capacitive_load_driver",
            "Capacitive Load Driver",
            "A1_cap_load_driver",
            "Use when the load is capacitive or the datasheet recommends an RC snubber for stability.",
            "Output stage with snubber RC and explicit load capacitor placeholder near the op amp output.",
            ["VOUT_ANA", "LOAD_CAP"],
            [primary_unit, "RSNUB", "CSNUB", "CLOAD"],
            [
                {"from": f"{primary_unit}.OUT", "to": "VOUT_ANA", "note": "Main driven output node."},
                {"from": "VOUT_ANA", "to": "RSNUB", "note": "Place snubber resistor close to the op amp output."},
                {"from": "RSNUB", "to": "CSNUB", "note": "RC snubber damps ringing into capacitive loads."},
                {"from": "VOUT_ANA", "to": "CLOAD", "note": "Represent the external capacitive load explicitly."},
            ],
            ["Place RSNUB/CSNUB within the output loop and verify phase margin with actual load capacitance."],
            based_on="capacitive_load_driver",
        )

    if "strain_gage_frontend" in candidate_map:
        add_template(
            "strain_gage_frontend",
            "Strain Gage Front End",
            "A1_strain_gage_frontend",
            "Use for bridge sensors or weigh-scale front ends that need excitation and differential amplification.",
            "Bridge sensor, reference driver, and gain stage organized as a first schematic partition.",
            ["BRIDGE_EXC", "BRIDGE_P", "BRIDGE_N", "VREF", "VOUT_ANA"],
            [primary_unit, "U1B", "XBRIDGE1", "XREF1", "RGAIN_BR"],
            [
                {"from": "XREF1", "to": "BRIDGE_EXC", "note": "Drive the bridge excitation from a buffered reference."},
                {"from": "BRIDGE_P", "to": f"{primary_unit}.IN+", "note": "Sense the positive bridge node."},
                {"from": "BRIDGE_N", "to": f"{primary_unit}.IN-", "note": "Sense the negative bridge node or route via gain network."},
                {"from": f"{primary_unit}.OUT", "to": "RGAIN_BR", "note": "Closed-loop gain sets full-scale output swing."},
                {"from": f"{primary_unit}.OUT", "to": "VOUT_ANA", "note": "Present conditioned bridge output to ADC."},
            ],
            ["Freeze bridge resistance, excitation level, and ADC full-scale target before choosing RGAIN_BR."],
            based_on="strain_gage_frontend",
        )

    if "thermocouple_frontend" in candidate_map:
        add_template(
            "thermocouple_frontend",
            "Thermocouple Front End",
            "A1_thermocouple_frontend",
            "Use for low-level thermocouple signals that need cold-junction compensation and gain.",
            "Thermocouple pair, cold-junction sense element, and amplified single-ended output organized for first-pass capture.",
            ["TC_P", "TC_N", "CJ_SENSE", "VREF", "VOUT_ANA"],
            [primary_unit, "XTC1", "XCJ1", "RGAIN_TC", "RZERO_TC"],
            [
                {"from": "TC_P", "to": f"{primary_unit}.IN+", "note": "Route thermocouple positive lead with quiet analog return."},
                {"from": "TC_N", "to": f"{primary_unit}.IN-", "note": "Route thermocouple negative lead as a matched pair where practical."},
                {"from": "CJ_SENSE", "to": "XCJ1", "note": "Cold-junction element should sit near the terminal junction."},
                {"from": f"{primary_unit}.OUT", "to": "RGAIN_TC", "note": "Use gain network to scale to required mV/°C transfer."},
                {"from": f"{primary_unit}.OUT", "to": "VOUT_ANA", "note": "Deliver conditioned temperature signal downstream."},
            ],
            ["Place thermocouple connector and cold-junction sensor before finalizing board partitioning."],
            based_on="thermocouple_frontend",
        )

    if "current_sense_frontend" in candidate_map:
        add_template(
            "current_sense_frontend",
            "Current Sense Front End",
            "A1_current_sense_frontend",
            "Use when RSENSE-based monitoring is called out in the datasheet equations or examples.",
            "Sense resistor and gain network form a monitor output for current telemetry or fault detection.",
            ["SENSE_P", "SENSE_N", "MON_OUT", "VREF"],
            [primary_unit, "RSENSE", "RGAIN_CS", "RFILT_CS"],
            [
                {"from": "SENSE_P", "to": "RSENSE", "note": "Kelvin-sense the positive side of the shunt."},
                {"from": "SENSE_N", "to": "RSENSE", "note": "Kelvin-sense the negative side of the shunt."},
                {"from": "RSENSE", "to": f"{primary_unit}.IN+", "note": "Feed the measured differential signal into the gain stage."},
                {"from": f"{primary_unit}.OUT", "to": "RGAIN_CS", "note": "Set telemetry gain and any output scaling here."},
                {"from": f"{primary_unit}.OUT", "to": "MON_OUT", "note": "Export the monitored current signal."},
            ],
            ["Reserve Kelvin routing for RSENSE and keep high-current copper away from the op amp input loop."],
            based_on="current_sense_frontend",
        )

    return templates


def build_module_template(device: dict, design_intent: dict) -> dict:
    module_name = _sanitize_name(device.get("mpn") or "device") + "_module"
    nets = list(design_intent.get("starter_nets", []))
    blocks = [
        {
            "ref": "U1",
            "type": "device",
            "mpn": device.get("mpn"),
            "package": design_intent.get("device_ref", {}).get("preferred_package")
            or design_intent.get("device_ref", {}).get("package"),
        }
    ]
    for component in design_intent.get("external_components", []):
        blocks.append(
            {
                "ref": component.get("designator"),
                "type": "support_component",
                "role": component.get("role"),
                "status": component.get("status"),
                "connect_between": component.get("connect_between"),
            }
        )

    topology_candidates = []
    opamp_templates = []
    decoder_templates = []
    interface_switch_templates = []
    switch_templates = []
    fpga_scenarios = []
    fpga_templates = []
    opamp_device_context = None
    decoder_device_context = design_intent.get("decoder_device_context")
    interface_switch_device_context = design_intent.get("interface_switch_device_context")
    switch_device_context = design_intent.get("switch_device_context")
    mcu_device_context = design_intent.get("mcu_device_context")
    category = (device.get("category") or "").lower()
    mcu_templates = []
    default_mcu_template = None
    default_opamp_template = None
    default_decoder_template = None
    default_interface_switch_template = None
    default_switch_template = None
    default_fpga_template = None
    if device.get("_type") == "fpga":
        fpga_scenarios = design_intent.get("customer_scenarios", [])
        fpga_templates = _fpga_standard_templates(device, design_intent, fpga_scenarios)
        default_fpga_template = _choose_default_fpga_template(fpga_templates)
        for candidate in fpga_scenarios:
            for net in candidate.get("nets", []):
                _append_net_once(nets, net["name"], net["purpose"])
            for block in candidate.get("blocks", []):
                _append_block_once(blocks, block["ref"], block["type"], block["role"], scenario=candidate["name"])
    elif "opamp" in category or "amplifier" in category:
        opamp_device_context = _infer_opamp_traits(device, design_intent)
        topology_candidates = _opamp_topology_candidates(design_intent)
        opamp_templates = _opamp_standard_templates(device, design_intent, topology_candidates)
        default_opamp_template = _choose_default_opamp_template(opamp_templates, topology_candidates)
        for net_name, net_purpose in (
            (opamp_device_context["suggested_power_nets"]["positive"], "analog_positive_supply"),
            (opamp_device_context["suggested_power_nets"]["negative"], "analog_negative_supply_or_ground"),
            (opamp_device_context["suggested_power_nets"]["reference"], "analog_reference_or_bias"),
        ):
            _append_net_once(nets, net_name, net_purpose)
        for candidate in topology_candidates:
            for net in candidate.get("nets", []):
                _append_net_once(nets, net["name"], net["purpose"])
            for block in candidate.get("blocks", []):
                _append_block_once(
                    blocks,
                    block["ref"],
                    block["type"],
                    block["role"],
                    topology=candidate["name"],
                )
    elif decoder_device_context:
        topology_candidates = _decoder_topology_candidates(decoder_device_context)
        decoder_templates = _decoder_standard_templates(device, decoder_device_context, topology_candidates)
        default_decoder_template = _choose_default_decoder_template(decoder_templates, topology_candidates)
        for candidate in topology_candidates:
            for net in candidate.get("nets", []):
                _append_net_once(nets, net["name"], net["purpose"])
            for block in candidate.get("blocks", []):
                _append_block_once(
                    blocks,
                    block["ref"],
                    block["type"],
                    block["role"],
                    topology=candidate["name"],
                )
    elif interface_switch_device_context:
        interface_switch_templates = _interface_switch_standard_templates(device, interface_switch_device_context)
        default_interface_switch_template = _choose_default_interface_switch_template(interface_switch_templates)
        for template in interface_switch_templates:
            for net_name in template.get("nets", []):
                _append_net_once(nets, net_name, "interface_switch_template_placeholder")
            for block_name in template.get("blocks", []):
                if block_name == "U1":
                    continue
                _append_block_once(blocks, block_name, "topology_block", "interface_switch_template_block", template=template["name"])
    elif switch_device_context:
        switch_templates = _switch_standard_templates(device, switch_device_context)
        default_switch_template = _choose_default_switch_template(switch_templates)
        for template in switch_templates:
            for net_name in template.get("nets", []):
                _append_net_once(nets, net_name, "switch_template_placeholder")
            for block_name in template.get("blocks", []):
                if block_name == "U1":
                    continue
                _append_block_once(blocks, block_name, "topology_block", "switch_template_block", template=template["name"])
    elif mcu_device_context:
        mcu_templates = _mcu_standard_templates(device, mcu_device_context)
        default_mcu_template = _choose_default_mcu_template(mcu_templates)
        for template in mcu_templates:
            for net_name in template.get("nets", []):
                _append_net_once(nets, net_name, "mcu_template_placeholder")
            for block_name in template.get("blocks", []):
                if block_name == "U1":
                    continue
                _append_block_once(blocks, block_name, "topology_block", "mcu_template_block", template=template["name"])
            for net_name in template.get("nets", []):
                _append_net_once(nets, net_name, "switch_template_placeholder")
            for block_name in template.get("blocks", []):
                if block_name == "U1":
                    continue
                _append_block_once(blocks, block_name, "topology_block", "switch_template_block", template=template["name"])

    todos = [
        "Confirm preferred package against footprint library and assembly constraints.",
        "Replace placeholder values with datasheet-approved component values.",
        "Review all attention_items before schematic release.",
    ]
    if device.get("_type") == "fpga":
        todos.append("Map IO banks, configuration mode, and JTAG access before pin assignment freeze.")
        for candidate in fpga_scenarios:
            for item in candidate.get("todo", []):
                if item not in todos:
                    todos.append(item)
    else:
        todos.append("Close the power loop layout early for power devices before PCB placement starts.")
    for candidate in topology_candidates:
        for item in candidate.get("todo", []):
            if item not in todos:
                todos.append(item)

    return {
        "_schema": BUNDLE_SCHEMA,
        "bundle_layer": "L3_module_template",
        "module_name": module_name,
        "device": {
            "mpn": device.get("mpn"),
            "category": device.get("category"),
            "manufacturer": device.get("manufacturer"),
        },
        "nets": nets,
        "blocks": blocks,
        "opamp_device_context": opamp_device_context,
        "decoder_device_context": decoder_device_context,
        "interface_switch_device_context": interface_switch_device_context,
        "switch_device_context": switch_device_context,
        "mcu_device_context": mcu_device_context,
        "topology_candidates": topology_candidates,
        "opamp_templates": opamp_templates,
        "decoder_templates": decoder_templates,
        "interface_switch_templates": interface_switch_templates,
        "switch_templates": switch_templates,
        "mcu_templates": mcu_templates,
        "fpga_scenarios": fpga_scenarios,
        "fpga_templates": fpga_templates,
        "high_speed_semantic_context": design_intent.get("high_speed_semantic_context"),
        "default_opamp_template": default_opamp_template,
        "default_decoder_template": default_decoder_template,
        "default_interface_switch_template": default_interface_switch_template,
        "default_switch_template": default_switch_template,
        "default_mcu_template": default_mcu_template,
        "default_fpga_template": default_fpga_template,
        "todo": todos,
    }


def build_quickstart_markdown(device: dict, design_intent: dict) -> str:
    lines = [
        f"# {device.get('mpn')} design quickstart",
        "",
        f"- Type: `{device.get('_type')}`",
        f"- Category: `{device.get('category')}`",
        f"- Manufacturer: `{device.get('manufacturer')}`",
    ]

    device_ref = design_intent.get("device_ref", {})
    if device_ref.get("preferred_package"):
        lines.append(f"- Preferred package: `{device_ref['preferred_package']}`")
    if device_ref.get("package"):
        lines.append(f"- Package: `{device_ref['package']}`")

    lines.extend(["", "## First-pass checklist", ""])

    for component in design_intent.get("external_components", []):
        role = component.get("role")
        status = component.get("status")
        why = component.get("why")
        lines.append(f"- Add `{component.get('designator')}` for `{role}` (`{status}`): {why}")

    constraints = design_intent.get("constraints", {})
    if constraints:
        lines.extend(["", "## Key constraints", ""])
        for name, entry in constraints.items():
            value_bits = []
            for key in ("min", "typ", "max"):
                if entry.get(key) is not None:
                    value_bits.append(f"{key}={entry[key]}")
            if entry.get("unit"):
                value_bits.append(f"unit={entry['unit']}")
            lines.append(f"- `{name}`: {entry.get('parameter')} ({', '.join(value_bits)})")

    attention_items = design_intent.get("attention_items", [])
    if attention_items:
        lines.extend(["", "## Attention items", ""])
        for item in attention_items[:12]:
            lines.append(f"- `{item.get('name')}` / pin `{item.get('pin')}`: {item.get('action')}")

    customer_scenarios = design_intent.get("customer_scenarios", [])
    if customer_scenarios:
        lines.extend(["", "## Customer scenarios", ""])
        for scenario in customer_scenarios[:8]:
            lines.append(f"- `{scenario.get('label')}`: {scenario.get('why')}")

        high_speed_context = design_intent.get("high_speed_semantic_context", {}) or {}
        if high_speed_context:
            lines.extend(["", "## High-speed semantics", ""])
            if high_speed_context.get("protocol_candidates"):
                lines.append(f"- Protocol candidates: `{', '.join(high_speed_context.get('protocol_candidates', [])[:8])}`")
            lane_groups = high_speed_context.get("lane_groups") or []
            for group in lane_groups[:6]:
                group_id = group.get("group_id")
                protocols = ", ".join(group.get("candidate_protocols", [])[:6])
                refs = ", ".join(group.get("refclk_pair_names", [])[:4])
                lines.append(f"- Lane group `{group_id}` → protocols `{protocols}`; refclk `{refs}`")

        lines.extend(["", "## L3 Templates", ""])
        default_name = _choose_default_fpga_template(_fpga_standard_templates(device, design_intent, customer_scenarios))
        for template in _fpga_standard_templates(device, design_intent, customer_scenarios):
            prefix = "Start here: " if template.get("name") == default_name else ""
            semantic_suffix = ""
            if template.get("protocol_candidates"):
                semantic_suffix = f" Protocols: {', '.join(template.get('protocol_candidates', [])[:6])}."
            if template.get("lane_group_refs"):
                semantic_suffix += f" Lane groups: {', '.join(template.get('lane_group_refs', [])[:8])}."
            lines.append(f"- {prefix}`{template.get('name')}` — {template.get('recommended_when')}{semantic_suffix}")

    vendor_design_rules = design_intent.get("vendor_design_rules", {})
    if vendor_design_rules:
        lines.extend(["", "## Vendor design rules", ""])
        for title, items in (("Power", vendor_design_rules.get("power_rules", [])), ("Config", vendor_design_rules.get("config_rules", [])), ("Clock", vendor_design_rules.get("clock_rules", [])), ("IO", vendor_design_rules.get("io_rules", []))):
            if not items:
                continue
            lines.append(f"- `{title}`: {items[0]}")
            for extra in items[1:3]:
                lines.append(f"- `{title}`: {extra}")

    reference_assets = design_intent.get("reference_design_assets", [])
    if reference_assets:
        lines.extend(["", "## Reference assets", ""])
        for asset in reference_assets[:6]:
            topics = ", ".join(asset.get("topics", [])[:6])
            topic_suffix = f" Topics: {topics}." if topics else ""
            lines.append(
                f"- `{asset.get('title')}` (`{asset.get('source_path')}`): {asset.get('summary')}{topic_suffix}"
            )

    pin_groups = design_intent.get("pin_groups", {})
    if pin_groups:
        lines.extend(["", "## Pin groups", ""])
        for group_name, pins in pin_groups.items():
            if not pins:
                continue
            labels = []
            for pin in pins[:10]:
                pin_label = pin.get("name") or pin.get("pin")
                if pin.get("pin"):
                    pin_label = f"{pin_label}({pin['pin']})"
                labels.append(pin_label)
            suffix = " ..." if len(pins) > 10 else ""
            lines.append(f"- `{group_name}`: {', '.join(labels)}{suffix}")

    datasheet_context = design_intent.get("datasheet_design_context", {})
    topology_candidates = []
    opamp_templates = []
    decoder_templates = []
    interface_switch_templates = []
    switch_templates = []
    mcu_templates = []
    opamp_device_context = None
    decoder_device_context = design_intent.get("decoder_device_context")
    interface_switch_device_context = design_intent.get("interface_switch_device_context")
    switch_device_context = design_intent.get("switch_device_context")
    mcu_device_context = design_intent.get("mcu_device_context")
    category = (device.get("category") or "").lower()
    if "opamp" in category or "amplifier" in category:
        opamp_device_context = _infer_opamp_traits(device, design_intent)
        topology_candidates = _opamp_topology_candidates(design_intent)
        opamp_templates = _opamp_standard_templates(device, design_intent, topology_candidates)
    elif decoder_device_context:
        topology_candidates = _decoder_topology_candidates(decoder_device_context)
        decoder_templates = _decoder_standard_templates(device, decoder_device_context, topology_candidates)
    elif interface_switch_device_context:
        interface_switch_templates = _interface_switch_standard_templates(device, interface_switch_device_context)
    elif switch_device_context:
        switch_templates = _switch_standard_templates(device, switch_device_context)
    elif mcu_device_context:
        mcu_templates = _mcu_standard_templates(device, mcu_device_context)

    default_opamp_template = _choose_default_opamp_template(opamp_templates, topology_candidates)
    default_decoder_template = _choose_default_decoder_template(decoder_templates, topology_candidates)
    default_interface_switch_template = _choose_default_interface_switch_template(interface_switch_templates)
    default_switch_template = _choose_default_switch_template(switch_templates)
    default_mcu_template = _choose_default_mcu_template(mcu_templates)

    if opamp_device_context:
        lines.extend(["", "## OpAmp implementation notes", ""])
        lines.append(f"- Channels: `{opamp_device_context['channel_count']}` ({', '.join(item['symbol_unit'] for item in opamp_device_context.get('channel_units', []))})")
        lines.append(f"- Supply style: `{opamp_device_context['supply_style']}`")
        lines.append(f"- Bias strategy: `{opamp_device_context['bias_strategy']}`")
        lines.append(
            f"- Suggested rails: `+={opamp_device_context['suggested_power_nets']['positive']}` `-={opamp_device_context['suggested_power_nets']['negative']}` `ref={opamp_device_context['suggested_power_nets']['reference']}`"
        )
        anchors = []
        for channel in opamp_device_context.get('channel_units', []):
            for signal_name in ('OUT', 'IN-', 'IN+'):
                pin_num = channel.get('package_bindings', {}).get(signal_name)
                if pin_num:
                    anchors.append(f"{channel['symbol_unit']}.{signal_name}={pin_num}")
        if opamp_device_context.get('shared_power_pins', {}).get('negative'):
            anchors.append(f"PWR-={opamp_device_context['shared_power_pins']['negative'][0]['pin']}")
        if opamp_device_context.get('shared_power_pins', {}).get('positive'):
            anchors.append(f"PWR+={opamp_device_context['shared_power_pins']['positive'][0]['pin']}")
        if anchors:
            lines.append(f"- Preferred package anchors: {' '.join(f'`{item}`' for item in anchors[:10])}")
        package_variants = opamp_device_context.get('package_variants', [])
        alternate_variants = [
            item for item in package_variants
            if item.get('package_name') != opamp_device_context.get('preferred_package')
        ]
        if alternate_variants:
            summary = []
            for item in alternate_variants[:4]:
                summary.append(f"{item['package_name']}:{item['channel_count']}ch")
            lines.append(f"- Alternate package variants: {' '.join(f'`{item}`' for item in summary)}")

    if decoder_device_context:
        lines.extend(["", "## Decoder implementation notes", ""])
        lines.append(f"- Preferred package: `{decoder_device_context['preferred_package']}`")
        if decoder_device_context.get('power_rails'):
            lines.append(f"- Power rails: {' '.join(f'`{item['name']}`' for item in decoder_device_context['power_rails'][:6])}")
        if decoder_device_context.get('reset_pins'):
            lines.append(f"- Reset/powerdown pins: {' '.join(f'`{item['name']}({item['pin']})`' for item in decoder_device_context['reset_pins'][:4])}")
        if decoder_device_context.get('ref_clock_pins'):
            lines.append(f"- Reference clock pins: {' '.join(f'`{item['name']}({item['pin']})`' for item in decoder_device_context['ref_clock_pins'][:4])}")
        interface_bits = []
        if decoder_device_context.get('analog_video_inputs'):
            interface_bits.append(f"analog_video={len(decoder_device_context['analog_video_inputs'])}")
        if decoder_device_context.get('serial_links'):
            interface_bits.append(f"serial_links={len(decoder_device_context['serial_links'])}")
        if decoder_device_context.get('mipi_outputs'):
            interface_bits.append(f"mipi_outputs={len(decoder_device_context['mipi_outputs'])}")
        if decoder_device_context.get('parallel_video_outputs'):
            interface_bits.append(f"parallel_video={len(decoder_device_context['parallel_video_outputs'])}")
        if interface_bits:
            lines.append(f"- Suggested interfaces: {' '.join(f'`{item}`' for item in interface_bits)}")

    if interface_switch_device_context:
        lines.extend(["", "## Interface switch implementation notes", ""])
        lines.append(f"- Preferred package: `{interface_switch_device_context['preferred_package']}`")
        lines.append(f"- Interface kind: `{interface_switch_device_context['interface_kind']}` topology=`{interface_switch_device_context['topology_kind']}` channels=`{interface_switch_device_context['channel_count']}`")
        if interface_switch_device_context.get("supply_nets"):
            lines.append(f"- Supply nets: {' '.join(f'`{item}`' for item in interface_switch_device_context['supply_nets'][:6])}")
        control_bits = []
        if interface_switch_device_context.get("select_pins"):
            control_bits.append("select")
        if interface_switch_device_context.get("enable_pins"):
            control_bits.append("enable")
        if control_bits:
            lines.append(f"- Control pins: {' '.join(f'`{item}`' for item in control_bits)}")

    official_source_documents = design_intent.get("official_source_documents", [])

    if official_source_documents:
        lines.extend(["", "## Official source documents", ""])
        for item in official_source_documents[:6]:
            sha = item.get("sha256")
            sha_suffix = f" sha256=`{sha[:12]}`" if sha else ""
            lines.append(f"- `{item.get("path")}` `{item.get("doc_type")}`{sha_suffix}")

    if mcu_device_context:
        lines.extend(["", "## MCU implementation notes", ""])
        if mcu_device_context.get("reset_pins"):
            lines.append(f"- Reset pins: {' '.join(f'`{item['name']}({item['pin']})`' for item in mcu_device_context['reset_pins'][:4])}")
        if mcu_device_context.get("boot_pins"):
            lines.append(f"- Boot straps: {' '.join(f'`{item['name']}({item['pin']})`' for item in mcu_device_context['boot_pins'][:4])}")
        if mcu_device_context.get("debug_pins"):
            lines.append(f"- Debug pins: {' '.join(f'`{item['name']}({item['pin']})`' for item in mcu_device_context['debug_pins'][:6])}")
        if mcu_device_context.get("hse_pins"):
            lines.append(f"- HSE clock pins: {' '.join(f'`{item['name']}({item['pin']})`' for item in mcu_device_context['hse_pins'][:4])}")
        if mcu_device_context.get("analog_supply_pins"):
            lines.append(f"- Analog rails: {' '.join(f'`{item['name']}({item['pin']})`' for item in mcu_device_context['analog_supply_pins'][:6])}")
        if mcu_device_context.get("vcap_pins"):
            lines.append(f"- VCAP pins: {' '.join(f'`{item['name']}({item['pin']})`' for item in mcu_device_context['vcap_pins'][:4])}")

    if switch_device_context:
        lines.extend(["", "## Analog switch implementation notes", ""])
        lines.append(f"- Preferred package: `{switch_device_context['preferred_package']}`")
        lines.append(f"- Topology: `{switch_device_context['topology_kind']}` channels=`{switch_device_context['channel_count']}`")
        if switch_device_context.get("supply_nets"):
            lines.append(f"- Supply nets: {' '.join(f'`{item}`' for item in switch_device_context['supply_nets'][:6])}")
        control_modes = []
        if switch_device_context.get("supports_parallel_address"):
            control_modes.append("parallel_address")
        if switch_device_context.get("supports_direct_select_bank"):
            control_modes.append("direct_select_bank")
        if switch_device_context.get("supports_shift_register"):
            control_modes.append("serial_shift")
        if switch_device_context.get("supports_i2c"):
            control_modes.append("i2c")
        if control_modes:
            lines.append(f"- Control modes: {' '.join(f'`{item}`' for item in control_modes)}")
        if switch_device_context.get("address_pins"):
            lines.append(f"- Address pins: {' '.join(f'`{item['name']}({item['pin']})`' for item in switch_device_context['address_pins'][:6])}")
        if switch_device_context.get("reset_pins"):
            lines.append(f"- Reset pins: {' '.join(f'`{item['name']}({item['pin']})`' for item in switch_device_context['reset_pins'][:4])}")

    if topology_candidates:
        lines.extend(["", "## Suggested topologies", ""])
        for candidate in topology_candidates[:6]:
            pages = ", ".join(str(page) for page in candidate.get("source_pages", []) if page is not None) or "derived"
            lines.append(f"- `{candidate.get('label')}` (pages: {pages}): {candidate.get('why')}")

    if opamp_templates:
        lines.extend(["", "## L3 Templates", ""])
        for template in opamp_templates[:8]:
            prefix = "Start here: " if template.get("name") == default_opamp_template else ""
            lines.append(f"- {prefix}`{template.get('sheet_name')}` `{template.get('label')}`: {template.get('recommended_when')}")
    elif decoder_templates:
        lines.extend(["", "## L3 Templates", ""])
        for template in decoder_templates[:8]:
            prefix = "Start here: " if template.get("name") == default_decoder_template else ""
            lines.append(f"- {prefix}`{template.get('sheet_name')}` `{template.get('label')}`: {template.get('recommended_when')}")
    elif interface_switch_templates:
        lines.extend(["", "## L3 Templates", ""])
        for template in interface_switch_templates[:8]:
            prefix = "Start here: " if template.get("name") == default_interface_switch_template else ""
            lines.append(f"- {prefix}`{template.get('sheet_name')}` `{template.get('label')}`: {template.get('recommended_when')}")
    elif mcu_templates:
        lines.extend(["", "## MCU templates", ""])
        for template in mcu_templates[:8]:
            prefix = "Start here: " if template.get("name") == default_mcu_template else ""
            lines.append(f"- {prefix}`{template.get('sheet_name')}` `{template.get('label')}`: {template.get('recommended_when')}")
    elif switch_templates:
        lines.extend(["", "## L3 Templates", ""])
        for template in switch_templates[:8]:
            prefix = "Start here: " if template.get("name") == default_switch_template else ""
            lines.append(f"- {prefix}`{template.get('sheet_name')}` `{template.get('label')}`: {template.get('recommended_when')}")

    if datasheet_context.get("design_page_candidates"):
        lines.extend(["", "## Datasheet design pages", ""])
        for page in datasheet_context["design_page_candidates"][:8]:
            lines.append(f"- Page `{page.get('page_num')}` `{page.get('kind')}`: {page.get('preview')}")

    if datasheet_context.get("design_range_hints"):
        lines.extend(["", "## Datasheet operating windows", ""])
        seen_ranges = set()
        for item in datasheet_context["design_range_hints"][:8]:
            key = (item.get("name"), item.get("min"), item.get("max"), item.get("unit"))
            if key in seen_ranges:
                continue
            seen_ranges.add(key)
            lines.append(
                f"- Page `{item.get('source_page')}`: `{item.get('name')}` = {item.get('min')} to {item.get('max')} {item.get('unit')}"
            )

    if datasheet_context.get("component_value_hints"):
        lines.extend(["", "## Typical application values", ""])
        for item in datasheet_context["component_value_hints"][:6]:
            lines.append(
                f"- Page `{item.get('source_page')}`: {', '.join(item.get('values', [])[:6])}"
            )

    if datasheet_context.get("design_equation_hints"):
        lines.extend(["", "## Equation hints", ""])
        for item in datasheet_context["design_equation_hints"][:6]:
            lines.append(f"- Page `{item.get('source_page')}`: `{item.get('equation')}`")

    if datasheet_context.get("layout_hints"):
        lines.extend(["", "## Layout hints", ""])
        for item in datasheet_context["layout_hints"][:6]:
            lines.append(f"- Page `{item.get('source_page')}`: {item.get('hint')}")

    lines.extend(["", "## Suggested next action", "", "- Open `L3_module_template.json`, replace placeholders, then draft the first schematic sheet around `U1`."])
    return "\n".join(lines) + "\n"


def export_device_bundle(device_path: Path, output_dir: Path, extracted_index: dict[str, Path], pdf_dir: Path) -> Path:
    device = json.loads(device_path.read_text(encoding="utf-8"))
    bundle_key = device.get("mpn") or device_path.stem
    if device.get("package"):
        bundle_key = f"{bundle_key}_{device['package']}"
    bundle_name = _sanitize_name(bundle_key)
    bundle_dir = output_dir / bundle_name
    bundle_dir.mkdir(parents=True, exist_ok=True)

    l0_path = bundle_dir / "L0_device.json"
    shutil.copyfile(device_path, l0_path)

    datasheet_design_context = _load_datasheet_design_context(device, extracted_index, pdf_dir)
    design_intent = build_design_intent(device, datasheet_design_context=datasheet_design_context)
    design_intent["official_source_documents"] = _official_source_documents(datasheet_design_context)
    module_template = build_module_template(device, design_intent)
    quickstart_text = build_quickstart_markdown(device, design_intent)

    (bundle_dir / "L1_design_intent.json").write_text(
        json.dumps(design_intent, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (bundle_dir / "L2_quickstart.md").write_text(quickstart_text, encoding="utf-8")
    (bundle_dir / "L3_module_template.json").write_text(
        json.dumps(module_template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "_schema": BUNDLE_SCHEMA,
        "bundle_layer": "manifest",
        "device": {
            "mpn": device.get("mpn"),
            "type": device.get("_type"),
            "category": device.get("category"),
        },
        "source_export": str(device_path.name),
        "datasheet_source_mode": datasheet_design_context.get("source_mode"),
        "datasheet_source_record": datasheet_design_context.get("source_record"),
        "official_source_documents": design_intent.get("official_source_documents", []),
        "reference_files": [item["source_path"] for item in design_intent.get("reference_design_assets", [])],
        "files": [
            "L0_device.json",
            "L1_design_intent.json",
            "L2_quickstart.md",
            "L3_module_template.json",
        ],
    }
    (bundle_dir / "bundle_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return bundle_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--extracted-dir", type=Path, default=DEFAULT_EXTRACTED_DIR)
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--device",
        action="append",
        default=[],
        help="MPN or export stem to generate. Can be passed multiple times.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Generate only the first N bundles.")
    return parser.parse_args()


def _selected_files(input_dir: Path, devices: list[str]) -> list[Path]:
    files = sorted(input_dir.glob("*.json"))
    if not devices:
        return files

    wanted = {_sanitize_name(item) for item in devices}
    selected = []
    for path in files:
        stem = _sanitize_name(path.stem)
        selected_mpn = stem in wanted
        if not selected_mpn:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            selected_mpn = _sanitize_name(data.get("mpn") or "") in wanted
        if selected_mpn:
            selected.append(path)
    return selected


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir
    extracted_index = _index_extracted_records(args.extracted_dir)
    pdf_dir = args.pdf_dir
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    files = _selected_files(input_dir, args.device)
    if args.limit is not None:
        files = files[: args.limit]

    if not files:
        print("No matching device exports found.")
        return 1

    for device_path in files:
        bundle_dir = export_device_bundle(device_path, output_dir, extracted_index, pdf_dir)
        print(f"generated {bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
