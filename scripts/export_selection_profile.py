#!/usr/bin/env python3
"""Export Selection Profiles from extracted datasheet JSON.

Generates per-device selection profile cards and a comparative index
for component selection and comparison workflows.

Reads extracted JSON files (supporting both v1 flat and v2 domains-based
formats) and produces:
  - One selection card per device: {mpn}_selection.json
  - One comparative index: selection_index.json

Usage:
    python3 scripts/export_selection_profile.py                     # process all
    python3 scripts/export_selection_profile.py path/to/file.json   # single file
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_EXTRACTED_DIR = Path(__file__).resolve().parent.parent / "data" / "extracted"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "selection_profile"

SCHEMA_VERSION = "selection-profile/1.0"
INDEX_SCHEMA_VERSION = "selection-index/1.0"


# ─── Format Detection & Accessors ──────────────────────────────────


def detect_input_format(data: dict) -> str:
    """Detect whether input is flat (v1) or domains-based (v2).
    Returns 'flat' or 'domains'.
    """
    if "domains" in data and isinstance(data["domains"], dict):
        return "domains"
    return "flat"


def get_extraction(data: dict) -> dict:
    """Get electrical extraction from either format."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        return data["domains"].get("electrical", {})
    return data.get("extraction", {})


def get_pin_data(data: dict) -> dict:
    """Get pin extraction from either format."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        return data["domains"].get("pin", {})
    return data.get("pin_extraction", {})


def get_pin_index(data: dict) -> dict:
    """Get pin index from either format."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        pin = data["domains"].get("pin", {})
        return pin.get("pin_index", pin)
    return data.get("pin_index", {})


def get_thermal_data(data: dict) -> dict:
    """Get thermal data from either format."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        return data["domains"].get("thermal", {})
    return {}


def get_design_context(data: dict) -> dict:
    """Get design context from either format."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        return data["domains"].get("design_context", {})
    return data.get("design_extraction", {})


def get_register_data(data: dict) -> dict:
    """Get register data (only available in domains format)."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        return data["domains"].get("register", {})
    return {}


def get_timing_data(data: dict) -> dict:
    """Get timing data from either format."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        return data["domains"].get("timing", {})
    return data.get("timing", {})


def get_power_sequence_data(data: dict) -> dict:
    """Get power sequence data (only available in domains format)."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        return data["domains"].get("power_sequence", {})
    return {}


def get_parametric_data(data: dict) -> dict:
    """Get parametric data (only available in domains format)."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        return data["domains"].get("parametric", {})
    return {}


def get_component(data: dict) -> dict:
    """Get component metadata from either format."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        elec = data["domains"].get("electrical", {})
        comp = elec.get("component", {})
        if not comp:
            # Fallback: component may be at top level in some v2 extractions
            comp = data.get("component", {})
        return comp
    ext = data.get("extraction", {})
    return ext.get("component", {})


# ─── Spec Extraction Helpers ────────────────────────────────────────


# Pattern tuples: (spec_key, symbol_patterns, parameter_patterns, unit_hints, exclude_patterns)
SPEC_PATTERNS = [
    (
        "input_voltage",
        [r"^V[_\(]?IN", r"^VCC$", r"^VDD$", r"^VSUP"],
        [r"input.*volt.*range", r"input.*operat", r"supply.*volt.*range",
         r"^input\s+volt"],
        ("V",),
        [r"dropout", r"VIN\s*-\s*V", r"VIN-VO"],
    ),
    (
        "output_voltage",
        [r"^V[_\(]?OUT"],
        [r"output\s+volt.*range", r"output\s+volt.*adjust",
         r"^output\s+volt"],
        ("V",),
        [],
    ),
    (
        "output_current",
        [r"^I[_\(]?OUT", r"^I[_\(]?LOAD", r"^I[_\(]?LIM", r"^I[_\(]?OCL"],
        [r"output\s+current", r"load\s+current", r"current\s+limit",
         r"source\s+current\s+limit"],
        ("A", "mA"),
        [],
    ),
    (
        "quiescent_current",
        [r"^I[_\(]?Q\b", r"^I[_\(]?GND\b", r"^I[_\(]?SUPPLY"],
        [r"quiescent\s+curr", r"supply\s+curr.*operat",
         r"VDD\s+supply\s+curr"],
        ("uA", "\u00b5A", "\u03bcA", "mA"),
        [],
    ),
    (
        "switching_frequency",
        [r"^f[_\(]?SW", r"^F[_\(]?OSC", r"^f[_\(]?CLK"],
        [r"switch.*freq", r"oscillat.*freq", r"PWM.*freq"],
        ("kHz", "MHz", "Hz"),
        [],
    ),
    (
        "dropout_voltage",
        [r"^V[_\(]?DO\b", r"^VIN\-VO", r"^V[_\(]?DROP"],
        [r"dropout\s+volt", r"drop.?out"],
        ("V", "mV"),
        [],
    ),
    (
        "reference_voltage",
        [r"^V[_\(]?REF", r"^V[_\(]?FB\b", r"^VFEEDBACK"],
        [r"reference\s+volt", r"feedback.*volt.*regul",
         r"feedback.*volt"],
        ("V", "mV"),
        [],
    ),
    (
        "enable_threshold",
        [r"^V.*EN", r"^VTH.*EN", r"^VIH.*EN", r"^VIL.*EN"],
        [r"enable.*thresh", r"enable.*volt.*ris", r"enable.*high"],
        ("V",),
        [],
    ),
    (
        "uvlo_threshold",
        [r"^V[_\(]?UVLO"],
        [r"UVLO\s+thresh", r"under.?volt.*lock"],
        ("V",),
        [],
    ),
    (
        "thermal_shutdown",
        [r"^T[_\(]?SD", r"^TSDN"],
        [r"thermal\s+shut", r"over.?temp.*shut"],
        ("\u00b0C", "C"),
        [],
    ),
]

# Patterns for temperature range extraction from absolute maximum ratings
TEMP_AMR_PATTERNS = [
    (
        "operating",
        [r"^T[_\(]?A$", r"^T[_\(]?OP", r"^T[_\(]?AMB"],
        [r"operat.*temp", r"ambient.*temp.*operat", r"ambient.*temp.*range"],
    ),
    (
        "junction",
        [r"^T[_\(]?J", r"^TJmax"],
        [r"junction\s+temp", r"maximum\s+junction"],
    ),
    (
        "storage",
        [r"^T[_\(]?S", r"^T[_\(]?STG"],
        [r"storage\s+temp"],
    ),
]


def _safe_numeric(value) -> float | int | None:
    """Convert a value to a number, returning None on failure."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _match_symbol(key: str | None, patterns: list[str]) -> bool:
    """Check if a dict key matches any symbol regex patterns."""
    if not key:
        return False
    base_key = key.split("_")[0] if "_" in key else key
    for pat in patterns:
        if re.match(pat, base_key, re.IGNORECASE):
            return True
        if re.match(pat, key, re.IGNORECASE):
            return True
    return False


def _match_param(param_desc: str, patterns: list[str]) -> bool:
    """Check if a parameter description matches any patterns."""
    if not param_desc:
        return False
    for pat in patterns:
        if re.search(pat, param_desc, re.IGNORECASE):
            return True
    return False


def _unit_ok(unit: str | None, allowed: tuple[str, ...]) -> bool:
    """Check whether the unit is compatible with the expected spec."""
    if not allowed:
        return True
    if not unit:
        return True
    normalized = unit.strip().replace("\u00b0", "").replace("\u2103", "C")
    for a in allowed:
        a_norm = a.strip().replace("\u00b0", "").replace("\u2103", "C")
        if normalized.lower() == a_norm.lower():
            return True
    return False


def _sanitize(s: str) -> str:
    """Sanitize a string for use as a filename or dict key."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", s)


def _format_range(lo, hi, unit: str = "V") -> str | None:
    """Format a min-max range as a string like '3.0-5.5V'."""
    if lo is not None and hi is not None:
        return f"{lo}-{hi}{unit}"
    if hi is not None:
        return f"<={hi}{unit}"
    if lo is not None:
        return f">={lo}{unit}"
    return None


def _format_value_unit(value, unit: str = "") -> str | None:
    """Format a single value with its unit."""
    if value is None:
        return None
    return f"{value}{unit}"


# ─── Key Spec Extraction from Raw Electrical Data ───────────────────


def _extract_key_specs_from_raw(elec_chars: list, abs_max: list) -> list[dict]:
    """Extract key specs from raw electrical_characteristics and
    absolute_maximum_ratings lists (v1 flat format).

    Returns a list of spec dicts with name, value, min, typ, max, unit.
    """
    specs = []
    found_keys = set()

    for pattern_tuple in SPEC_PATTERNS:
        spec_key = pattern_tuple[0]
        sym_pats = pattern_tuple[1]
        param_pats = pattern_tuple[2]
        unit_hint = pattern_tuple[3]
        exclude_pats = pattern_tuple[4] if len(pattern_tuple) > 4 else []

        if spec_key in found_keys:
            continue

        best_entry = None
        best_score = -1

        for item in elec_chars:
            if not isinstance(item, dict):
                continue
            sym = item.get("symbol", "")
            param_name = item.get("parameter", "")
            unit = item.get("unit", "")

            # Check exclusion
            if exclude_pats:
                haystack = f"{sym} {param_name}"
                if any(re.search(ep, haystack, re.IGNORECASE) for ep in exclude_pats):
                    continue

            sym_match = _match_symbol(sym, sym_pats) if sym_pats else False
            param_match = _match_param(param_name, param_pats) if param_pats else False

            if not sym_match and not param_match:
                continue
            if not _unit_ok(unit, unit_hint):
                continue

            score = 0
            for vk in ("min", "typ", "max"):
                if _safe_numeric(item.get(vk)) is not None:
                    score += 1
            if sym_match:
                score += 3
            if param_match:
                score += 2

            if score > best_score:
                best_score = score
                best_entry = item

        if best_entry is not None:
            spec = {"name": spec_key}
            for vk in ("min", "typ", "max"):
                v = _safe_numeric(best_entry.get(vk))
                if v is not None:
                    spec[vk] = v
            if best_entry.get("unit"):
                spec["unit"] = best_entry["unit"]
            if best_entry.get("parameter"):
                spec["parameter"] = best_entry["parameter"]
            if spec.get("min") is not None or spec.get("typ") is not None or spec.get("max") is not None:
                specs.append(spec)
                found_keys.add(spec_key)

    return specs


def _extract_key_specs_from_params(params: dict) -> list[dict]:
    """Extract key specs from electrical_parameters dict (keyed by symbol).

    Returns a list of spec dicts with name, value, min, typ, max, unit.
    """
    specs = []
    found_keys = set()

    for pattern_tuple in SPEC_PATTERNS:
        spec_key = pattern_tuple[0]
        sym_pats = pattern_tuple[1]
        param_pats = pattern_tuple[2]
        unit_hint = pattern_tuple[3]
        exclude_pats = pattern_tuple[4] if len(pattern_tuple) > 4 else []

        if spec_key in found_keys:
            continue

        best_entry = None
        best_score = -1

        for key, entry in params.items():
            if not isinstance(entry, dict):
                continue
            param_name = entry.get("parameter", "")
            unit = entry.get("unit", "")

            if exclude_pats:
                haystack = f"{key} {param_name}"
                if any(re.search(ep, haystack, re.IGNORECASE) for ep in exclude_pats):
                    continue

            sym_match = _match_symbol(key, sym_pats) if sym_pats else False
            param_match = _match_param(param_name, param_pats) if param_pats else False

            if not sym_match and not param_match:
                continue
            if not _unit_ok(unit, unit_hint):
                continue

            score = 0
            for vk in ("min", "typ", "max"):
                if _safe_numeric(entry.get(vk)) is not None:
                    score += 1
            if sym_match:
                score += 3
            if param_match:
                score += 2
            if "_" not in key:
                score += 1

            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry is not None:
            spec = {"name": spec_key}
            for vk in ("min", "typ", "max"):
                v = _safe_numeric(best_entry.get(vk))
                if v is not None:
                    spec[vk] = v
            if best_entry.get("unit"):
                spec["unit"] = best_entry["unit"]
            if best_entry.get("parameter"):
                spec["parameter"] = best_entry["parameter"]
            if spec.get("min") is not None or spec.get("typ") is not None or spec.get("max") is not None:
                specs.append(spec)
                found_keys.add(spec_key)

    return specs


# ─── Operating Conditions Extraction ────────────────────────────────


def _extract_operating_conditions(elec_chars, abs_max_ratings) -> dict:
    """Extract operating conditions (temperature range, voltage range, etc.)
    from raw lists or dicts of electrical characteristics and abs max ratings.
    """
    operating = {}

    # Handle both list (v1) and dict (v2) formats for abs max
    abs_items = []
    if isinstance(abs_max_ratings, list):
        abs_items = abs_max_ratings
    elif isinstance(abs_max_ratings, dict):
        abs_items = [
            {**v, "symbol": k} for k, v in abs_max_ratings.items()
            if isinstance(v, dict)
        ]

    elec_items = []
    if isinstance(elec_chars, list):
        elec_items = elec_chars
    elif isinstance(elec_chars, dict):
        elec_items = [
            {**v, "symbol": k} for k, v in elec_chars.items()
            if isinstance(v, dict)
        ]

    # Temperature range from absolute maximum ratings
    for temp_type, sym_pats, param_pats in TEMP_AMR_PATTERNS:
        for item in abs_items:
            if not isinstance(item, dict):
                continue
            sym = item.get("symbol", "")
            param_name = item.get("parameter", "")
            if _match_symbol(sym, sym_pats) or _match_param(param_name, param_pats):
                t_min = _safe_numeric(item.get("min"))
                t_max = _safe_numeric(item.get("max"))
                if temp_type == "operating":
                    if t_min is not None:
                        operating.setdefault("temp_min", t_min)
                    if t_max is not None:
                        operating.setdefault("temp_max", t_max)
                elif temp_type == "junction" and t_max is not None:
                    operating.setdefault("tj_max", t_max)
                break

    # VIN operating range
    for item in elec_items:
        if not isinstance(item, dict):
            continue
        sym = item.get("symbol", "")
        param_name = item.get("parameter", "")
        if _match_symbol(sym, [r"^V[_\(]?IN", r"^VCC$", r"^VDD$"]) or \
           _match_param(param_name, [r"input.*volt.*range", r"supply.*volt.*range"]):
            # Skip dropout entries
            haystack = f"{sym} {param_name}"
            if re.search(r"dropout|VIN\s*-\s*V", haystack, re.IGNORECASE):
                continue
            vin_min = _safe_numeric(item.get("min"))
            vin_max = _safe_numeric(item.get("max"))
            if vin_min is not None or vin_max is not None:
                operating.setdefault("vin_min", vin_min)
                operating.setdefault("vin_max", vin_max)
                break

    return operating


# ─── Thermal Summary ────────────────────────────────────────────────


def _classify_thermal_key(item: dict) -> str | None:
    """Classify a thermal parameter into a normalized key."""
    symbol = (item.get("symbol") or "").upper().replace(" ", "")
    parameter = (item.get("parameter") or "").lower()
    conditions = (item.get("conditions") or "").lower()
    haystack = f"{symbol} {parameter} {conditions}"

    if "power dissipation capacitance" in parameter:
        return None
    if "power dissipation" in parameter or re.match(r"^P[Dd]$", symbol):
        return "power_dissipation"
    if re.search(r"(PSI|\u03a8)\s*JT", symbol) or "junction-to-top" in parameter:
        return "psi_jt"
    if re.search(r"(PSI|\u03a8)\s*JB", symbol) or "junction-to-board characterization" in parameter:
        return "psi_jb"
    if re.search(r"(R|\u03b8|\u0398).*JC", symbol) or "junction-to-case" in parameter:
        if "bottom" in haystack or "bot" in symbol:
            return "theta_jc_bottom"
        if "top" in haystack:
            return "theta_jc_top"
        return "theta_jc"
    if re.search(r"(R|\u03b8|\u0398).*JB", symbol) or "junction-to-board" in parameter:
        return "theta_jb"
    if re.search(r"(R|\u03b8|\u0398).*JA", symbol) or "junction-to-ambient" in parameter:
        return "theta_ja"
    if "thermal resistance" in parameter:
        return "theta_ja"
    return None


def _build_thermal_summary(raw_elec, raw_abs, thermal_domain: dict) -> dict:
    """Build a thermal summary from raw electrical/abs-max lists and
    thermal domain data.
    """
    thermal = {}

    # Extract from raw lists (v1 format)
    for source_items in (raw_elec or [], raw_abs or []):
        items = source_items if isinstance(source_items, list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            key = _classify_thermal_key(item)
            if key and key not in thermal:
                record = {}
                for vk in ("min", "typ", "max"):
                    v = _safe_numeric(item.get(vk))
                    if v is not None:
                        record[vk] = v
                if not record:
                    v = _safe_numeric(item.get("value"))
                    if v is not None:
                        record["typ"] = v
                if item.get("unit"):
                    record["unit"] = item["unit"]
                if record:
                    thermal[key] = record

    # Merge in thermal domain data (v2 format)
    if isinstance(thermal_domain, dict):
        for key, entry in thermal_domain.items():
            if not isinstance(entry, dict):
                continue
            if key in thermal:
                continue
            record = {}
            for vk in ("min", "typ", "max"):
                v = _safe_numeric(entry.get(vk))
                if v is not None:
                    record[vk] = v
            if not record:
                v = _safe_numeric(entry.get("value"))
                if v is not None:
                    record["typ"] = v
            if entry.get("unit"):
                record["unit"] = entry["unit"]
            if record:
                thermal[key] = record

    return thermal


# ─── Register Summary ───────────────────────────────────────────────


def _build_register_summary(register_data: dict) -> dict:
    """Extract register summary: bus_type and register_count."""
    if not register_data:
        return {}

    summary = register_data.get("register_map_summary", {})
    registers = register_data.get("registers", [])

    result = {}
    bus_type = summary.get("bus_type")
    if bus_type:
        result["bus_type"] = bus_type

    register_count = summary.get("total_registers")
    if register_count is None and isinstance(registers, list):
        register_count = len(registers)
    if register_count is not None and register_count > 0:
        result["register_count"] = register_count

    addr_range = summary.get("address_range")
    if addr_range:
        result["address_range"] = addr_range

    return result


# ─── Package & Pin Count Extraction ─────────────────────────────────


def _extract_packages_and_pin_count(pin_index: dict, design_ctx: dict) -> tuple[list[str], int]:
    """Extract package names and pin count from pin index and design context."""
    packages = []
    pin_count = 0

    # From pin_index (v1 and v2)
    pkgs = pin_index.get("packages", {})
    if isinstance(pkgs, dict):
        for pkg_name, pkg_info in pkgs.items():
            packages.append(pkg_name)
            if isinstance(pkg_info, dict):
                pc = pkg_info.get("pin_count")
                if isinstance(pc, int) and pc > pin_count:
                    pin_count = pc

                # If pin_count not present, check for nested "pins" dict (v2)
                if not isinstance(pc, int) or pc == 0:
                    pins = pkg_info.get("pins", {})
                    if isinstance(pins, dict) and len(pins) > pin_count:
                        pin_count = len(pins)

                # v1 flat format: pkg_info IS the pins dict directly
                # (keyed by pin number like "1", "2", "3")
                if not isinstance(pc, int) and "pins" not in pkg_info:
                    # Check if the values look like pin entries (have "name" key)
                    pin_entries = [
                        v for v in pkg_info.values()
                        if isinstance(v, dict) and "name" in v
                    ]
                    if pin_entries and len(pin_entries) > pin_count:
                        pin_count = len(pin_entries)

    # Supplement from design_context if no packages found
    if not packages and isinstance(design_ctx, dict):
        # design_context may have package info in supply_recommendations or topology
        pass  # No standard location; leave empty

    return sorted(set(packages)), pin_count


# ─── Selection Profile Card ────────────────────────────────────────


def build_selection_card(data: dict, source_file: str = "") -> dict | None:
    """Build a selection profile card from extracted JSON data.

    Handles both v1 (flat) and v2 (domains-based) input formats.
    Returns None if the device lacks a valid MPN.
    """
    fmt = detect_input_format(data)
    comp = get_component(data)

    mpn = comp.get("mpn")
    if not mpn:
        return None

    manufacturer = comp.get("manufacturer")
    category = comp.get("category", "Unknown")

    # --- Extract key specs ---
    parametric = get_parametric_data(data)
    key_specs = []
    operating_conditions = {}

    if parametric:
        # Use parametric domain data if available (from Worker-9)
        key_specs = parametric.get("key_specs", [])
        operating_conditions = parametric.get("operating_conditions", {})
    else:
        # Fall back to extracting from raw electrical data
        ext = get_extraction(data)

        if fmt == "flat":
            raw_elec = ext.get("electrical_characteristics", [])
            raw_abs = ext.get("absolute_maximum_ratings", [])
            key_specs = _extract_key_specs_from_raw(raw_elec, raw_abs)
            operating_conditions = _extract_operating_conditions(raw_elec, raw_abs)
        else:
            # v2 domains format: electrical domain has dict-keyed params
            elec_params = ext.get("electrical_parameters", {})
            abs_max = ext.get("absolute_maximum_ratings", {})
            key_specs = _extract_key_specs_from_params(elec_params)
            operating_conditions = _extract_operating_conditions(elec_params, abs_max)

    # --- Pin count and packages ---
    pin_index = get_pin_index(data)
    design_ctx = get_design_context(data)
    packages, pin_count = _extract_packages_and_pin_count(pin_index, design_ctx)

    # --- Thermal summary ---
    ext = get_extraction(data)
    thermal_domain = get_thermal_data(data)
    if fmt == "flat":
        raw_elec = ext.get("electrical_characteristics", [])
        raw_abs = ext.get("absolute_maximum_ratings", [])
    else:
        raw_elec = []
        raw_abs = []
    thermal_summary = _build_thermal_summary(raw_elec, raw_abs, thermal_domain)

    # --- Register summary ---
    register_data = get_register_data(data)
    register_summary = _build_register_summary(register_data)

    # --- Timing and power sequence presence ---
    timing_data = get_timing_data(data)
    has_timing_data = bool(timing_data) and bool(
        timing_data.get("timing_parameters") or
        timing_data.get("timing_summary")
    )

    power_seq_data = get_power_sequence_data(data)
    has_power_sequence = bool(power_seq_data) and bool(
        power_seq_data.get("power_stages") or
        power_seq_data.get("power_rails") or
        power_seq_data.get("power_sequence_summary")
    )

    card = {
        "_schema": SCHEMA_VERSION,
        "mpn": mpn,
        "manufacturer": manufacturer,
        "category": category,
        "key_specs": key_specs,
        "operating_conditions": operating_conditions,
        "pin_count": pin_count,
        "packages": packages,
        "thermal_summary": thermal_summary,
        "register_summary": register_summary,
        "has_timing_data": has_timing_data,
        "has_power_sequence": has_power_sequence,
        "extraction_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source_file": source_file or data.get("pdf_name", ""),
    }

    return card


# ─── Comparative Index ──────────────────────────────────────────────


def build_selection_index(cards: list[dict]) -> dict:
    """Build the comparative selection index from all cards."""
    devices = []

    for card in cards:
        mpn = card["mpn"]
        category = card.get("category", "Unknown")

        # Extract vin_range string
        vin_range = None
        oc = card.get("operating_conditions", {})
        vin_min = oc.get("vin_min")
        vin_max = oc.get("vin_max")
        if vin_min is not None or vin_max is not None:
            vin_range = _format_range(vin_min, vin_max, "V")
        else:
            # Try to find from key_specs
            for spec in card.get("key_specs", []):
                if isinstance(spec, dict) and spec.get("name") == "input_voltage":
                    vin_range = _format_range(
                        spec.get("min"), spec.get("max"),
                        spec.get("unit", "V")
                    )
                    break

        # Extract iout_max string
        iout_max = None
        iout_val = oc.get("iout_max")
        if iout_val is not None:
            iout_max = _format_value_unit(iout_val, "A")
        else:
            for spec in card.get("key_specs", []):
                if isinstance(spec, dict) and spec.get("name") == "output_current":
                    val = spec.get("max") or spec.get("typ")
                    if val is not None:
                        iout_max = _format_value_unit(val, spec.get("unit", "A"))
                    break

        key_spec_count = len(card.get("key_specs", []))
        safe_name = _sanitize(mpn)

        devices.append({
            "mpn": mpn,
            "category": category,
            "vin_range": vin_range,
            "iout_max": iout_max,
            "key_spec_count": key_spec_count,
            "profile_file": f"{safe_name}_selection.json",
        })

    # Sort by category then MPN
    devices.sort(key=lambda d: (d.get("category", ""), d.get("mpn", "")))

    return {
        "_schema": INDEX_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "device_count": len(cards),
        "devices": devices,
    }


# ─── File Processing ────────────────────────────────────────────────


def process_file(path: Path) -> dict | None:
    """Process a single extracted JSON file into a selection card."""
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  ERROR reading {path.name}: {exc}")
        return None

    # Skip FPGA datasheets
    if data.get("is_fpga"):
        return None

    card = build_selection_card(data, source_file=path.name)
    return card


# ─── Main ───────────────────────────────────────────────────────────


def main():
    # Determine input: single file or directory
    single_file = None
    extracted_dir = DEFAULT_EXTRACTED_DIR
    output_dir = DEFAULT_OUTPUT_DIR

    if len(sys.argv) > 1:
        arg = Path(sys.argv[1])
        if arg.is_file():
            single_file = arg
        elif arg.is_dir():
            extracted_dir = arg
        else:
            print(f"Error: {arg} is not a file or directory", file=sys.stderr)
            sys.exit(1)

    # If the default extracted dir does not exist, try extracted_v2
    if single_file is None and not extracted_dir.exists():
        alt_dir = extracted_dir.parent / "extracted_v2"
        if alt_dir.exists():
            extracted_dir = alt_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    cards: list[dict] = []
    errors = 0
    skipped = 0

    if single_file:
        # Process single file
        input_files = [single_file]
    else:
        input_files = sorted(extracted_dir.glob("*.json"))

    if not input_files:
        print(f"No JSON files found in {extracted_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"=== Selection Profile Export ===")
    print(f"Input: {single_file or extracted_dir}")
    print(f"Output: {output_dir}")
    print()

    for path in input_files:
        if path.name.startswith("_"):
            continue

        card = process_file(path)
        if card is None:
            skipped += 1
            continue

        mpn = card["mpn"]
        safe_name = _sanitize(mpn)
        out_path = output_dir / f"{safe_name}_selection.json"

        try:
            with open(out_path, "w", encoding="utf-8") as fp:
                json.dump(card, fp, indent=2, ensure_ascii=False)
                fp.write("\n")
        except OSError as exc:
            print(f"  ERROR writing {out_path.name}: {exc}")
            errors += 1
            continue

        n_specs = len(card.get("key_specs", []))
        n_pkgs = len(card.get("packages", []))
        print(f"  {mpn:25s} {card['category']:12s} {n_specs} specs, {n_pkgs} pkgs -> {out_path.name}")
        cards.append(card)

    # Build and write comparative index
    index = build_selection_index(cards)
    index_path = output_dir / "selection_index.json"
    try:
        with open(index_path, "w", encoding="utf-8") as fp:
            json.dump(index, fp, indent=2, ensure_ascii=False)
            fp.write("\n")
    except OSError as exc:
        print(f"  ERROR writing index: {exc}")
        errors += 1

    # Summary
    print()
    print(f"{'=' * 60}")
    print(f"Exported: {len(cards)}, Skipped: {skipped}, Errors: {errors}")
    print(f"Selection profiles: {output_dir}")
    print(f"Index: {index_path} ({index['device_count']} devices)")


if __name__ == "__main__":
    main()
