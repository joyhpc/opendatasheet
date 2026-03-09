#!/usr/bin/env python3
"""Export selection profiles from sch_review_export data.

Generates per-device selection cards and a comparative index
optimized for component selection and comparison.

Each device gets a JSON file with normalized key specs, operating
conditions, packages, and thermal data.  A comparative _index.json
groups devices by category for quick filtering.

Usage:
    python3 scripts/export_selection_profile.py [--summary] [--output-dir DIR]
    python3 scripts/export_selection_profile.py  # uses default paths
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_EXPORT_DIR = Path(__file__).resolve().parent.parent / "data/sch_review_export"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data/selection_profile"

SCHEMA_VERSION = "selection-profile/1.0"
INDEX_SCHEMA_VERSION = "selection-index/1.0"


# ─── Parameter Classification ────────────────────────────────────────
#
# Each pattern tuple:  (spec_key, symbol_patterns, parameter_patterns, unit_hint)
# symbol_patterns match against the electrical_parameters dict key / symbol.
# parameter_patterns match against the "parameter" description field.
# unit_hint is used to prefer certain units when available.

SPEC_PATTERNS = [
    (
        "input_voltage",
        [r"^V[_\(]?IN", r"^VCC$", r"^VDD$", r"^VSUP"],
        [r"input.*volt.*range", r"input.*operat", r"supply.*volt.*range",
         r"^input\s+volt"],
        ("V",),
        [r"dropout", r"VIN\s*-\s*V", r"VIN-VO"],  # exclude dropout entries
    ),
    (
        "output_voltage",
        [r"^V[_\(]?OUT"],
        [r"output\s+volt.*range", r"output\s+volt.*adjust",
         r"^output\s+volt"],
        ("V",),
    ),
    (
        "output_current",
        [r"^I[_\(]?OUT", r"^I[_\(]?LOAD", r"^I[_\(]?LIM", r"^I[_\(]?OCL"],
        [r"output\s+current", r"load\s+current", r"current\s+limit",
         r"source\s+current\s+limit"],
        ("A", "mA"),
    ),
    (
        "quiescent_current",
        [r"^I[_\(]?Q\b", r"^I[_\(]?GND\b", r"^I[_\(]?SUPPLY"],
        [r"quiescent\s+curr", r"supply\s+curr.*operat",
         r"VDD\s+supply\s+curr"],
        ("uA", "µA", "μA", "mA"),
    ),
    (
        "shutdown_current",
        [r"^I[_\(]?SD", r"^I[_\(]?SHDN", r"^I[_\(]?STBY"],
        [r"shutdown.*curr", r"standby.*curr"],
        ("uA", "µA", "μA", "nA"),
    ),
    (
        "switching_frequency",
        [r"^f[_\(]?SW", r"^F[_\(]?OSC", r"^f[_\(]?CLK"],
        [r"switch.*freq", r"oscillat.*freq", r"PWM.*freq"],
        ("kHz", "MHz", "Hz"),
    ),
    (
        "reference_voltage",
        [r"^V[_\(]?REF", r"^V[_\(]?FB\b", r"^VFEEDBACK"],
        [r"reference\s+volt", r"feedback.*volt.*regul",
         r"feedback.*volt"],
        ("V", "mV"),
    ),
    (
        "dropout_voltage",
        [r"^V[_\(]?DO\b", r"^VIN\-VO", r"^V[_\(]?DROP"],
        [r"dropout\s+volt", r"drop.?out"],
        ("V", "mV"),
    ),
    (
        "enable_threshold",
        [r"^V.*EN", r"^VTH.*EN", r"^VIH.*EN", r"^VIL.*EN"],
        [r"enable.*thresh", r"enable.*volt.*ris", r"enable.*high"],
        ("V",),
    ),
    (
        "uvlo_threshold",
        [r"^V[_\(]?UVLO"],
        [r"UVLO\s+thresh", r"under.?volt.*lock"],
        ("V",),
    ),
    (
        "line_regulation",
        [],
        [r"line\s+regulat"],
        ("%/V", "mV/V", "%"),
    ),
    (
        "load_regulation",
        [],
        [r"load\s+regulat"],
        ("%/mA", "mV/A", "%"),
    ),
    (
        "efficiency",
        [r"^EFF", r"^η"],
        [r"^efficien"],
        ("%",),
    ),
    (
        "output_voltage_accuracy",
        [r"^ΔVO$", r"^VOUT_ACC"],
        [r"output\s+volt.*toler", r"output\s+volt.*accur"],
        ("%", "%VNOM", "mV"),
    ),
    (
        "power_good_threshold",
        [r"^V[_\(]?PG", r"^V[_\(]?POK"],
        [r"power.?good.*thresh"],
        ("V", "%"),
    ),
    (
        "soft_start_time",
        [r"^t[_\(]?SS"],
        [r"soft.?start\s+time"],
        ("ms", "us", "µs"),
    ),
    (
        "thermal_shutdown",
        [r"^T[_\(]?SD", r"^TSDN"],
        [r"thermal\s+shut", r"over.?temp.*shut"],
        ("°C", "C"),
    ),
]

# Patterns for absolute maximum ratings temperature extraction
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


def _match_symbol(key: str, patterns: list[str]) -> bool:
    """Check if a dict key matches any of the symbol regex patterns."""
    # Strip trailing condition suffixes added by deduplication (e.g. "VIN_VIN_rising")
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
        return True  # Missing unit is accepted (might still be correct)
    normalized = unit.strip().replace("°", "").replace("℃", "C")
    for a in allowed:
        a_norm = a.strip().replace("°", "").replace("℃", "C")
        if normalized.lower() == a_norm.lower():
            return True
    return False


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


# ─── Spec Extraction ─────────────────────────────────────────────────


def _extract_specs_from_params(params: dict) -> dict:
    """Extract key specs from electrical_parameters dict.

    Returns dict of spec_key -> {min, typ, max, unit}.
    For each spec type the first good match wins.
    """
    specs: dict[str, dict] = {}

    for pattern_tuple in SPEC_PATTERNS:
        spec_key = pattern_tuple[0]
        sym_pats = pattern_tuple[1]
        param_pats = pattern_tuple[2]
        unit_hint = pattern_tuple[3]
        exclude_pats = pattern_tuple[4] if len(pattern_tuple) > 4 else []

        if spec_key in specs:
            continue
        best_entry = None
        best_score = -1

        for key, entry in params.items():
            if not isinstance(entry, dict):
                continue
            param_name = entry.get("parameter", "")
            unit = entry.get("unit", "")

            # Check exclusion patterns against key and parameter name
            if exclude_pats:
                haystack = f"{key} {param_name}"
                excluded = any(
                    re.search(ep, haystack, re.IGNORECASE)
                    for ep in exclude_pats
                )
                if excluded:
                    continue

            sym_match = _match_symbol(key, sym_pats) if sym_pats else False
            param_match = _match_param(param_name, param_pats) if param_pats else False

            if not sym_match and not param_match:
                continue

            if not _unit_ok(unit, unit_hint):
                continue

            # Score: prefer entries with more numeric values filled in
            score = 0
            for vk in ("min", "typ", "max"):
                if _safe_numeric(entry.get(vk)) is not None:
                    score += 1
            if sym_match:
                score += 3
            if param_match:
                score += 2
            # Prefer first occurrence (no condition suffix in key)
            if "_" not in key:
                score += 1

            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry is not None:
            spec_record: dict = {}
            for vk in ("min", "typ", "max"):
                v = _safe_numeric(best_entry.get(vk))
                if v is not None:
                    spec_record[vk] = v
            if best_entry.get("unit"):
                spec_record["unit"] = best_entry["unit"]
            if spec_record:
                specs[spec_key] = spec_record

    return specs


def _extract_specs_from_drc_hints(hints: dict) -> dict:
    """Extract / supplement key specs from drc_hints.

    drc_hints already has pre-extracted values like vin_operating, vout, etc.
    """
    mapping = {
        "vin_operating": "input_voltage",
        "vout": "output_voltage",
        "iout_max": "output_current",
        "iout_operating": "output_current",
        "iq": "quiescent_current",
        "fsw": "switching_frequency",
        "vref": "reference_voltage",
        "dropout": "dropout_voltage",
        "enable_threshold": "enable_threshold",
        "uvlo": "uvlo_threshold",
        "soft_start": "soft_start_time",
        "thermal_shutdown": "thermal_shutdown",
    }
    specs: dict[str, dict] = {}
    for hint_key, spec_key in mapping.items():
        hint = hints.get(hint_key)
        if not isinstance(hint, dict):
            continue
        spec_record: dict = {}
        for vk in ("min", "typ", "max"):
            v = _safe_numeric(hint.get(vk))
            if v is not None:
                spec_record[vk] = v
        # drc_hints vin_abs_max has "value" instead of min/typ/max
        if "value" in hint:
            v = _safe_numeric(hint["value"])
            if v is not None:
                spec_record["max"] = v
        if hint.get("unit"):
            spec_record["unit"] = hint["unit"]
        if spec_record:
            specs[spec_key] = spec_record

    return specs


def _extract_temp_range(abs_max_ratings: dict, elec_params: dict) -> dict:
    """Extract operating temperature range from absolute maximum ratings
    and electrical parameters."""
    result: dict = {}

    # Search absolute_maximum_ratings first
    for temp_type, sym_pats, param_pats in TEMP_AMR_PATTERNS:
        for key, entry in abs_max_ratings.items():
            if not isinstance(entry, dict):
                continue
            param_name = entry.get("parameter", "")
            if _match_symbol(key, sym_pats) or _match_param(param_name, param_pats):
                t_min = _safe_numeric(entry.get("min"))
                t_max = _safe_numeric(entry.get("max"))
                if temp_type == "operating" and (t_min is not None or t_max is not None):
                    if "temp_min" not in result and t_min is not None:
                        result["temp_min"] = t_min
                    if "temp_max" not in result and t_max is not None:
                        result["temp_max"] = t_max
                elif temp_type == "junction" and t_max is not None:
                    result["tj_max"] = t_max
                break

    # Also search electrical_parameters for operating junction temperature
    for key, entry in elec_params.items():
        if not isinstance(entry, dict):
            continue
        param_name = entry.get("parameter", "")
        unit = entry.get("unit") or ""
        if ("°" in unit or unit == "C") and _match_param(param_name, [r"operat.*junction.*temp", r"operat.*temp"]):
            t_min = _safe_numeric(entry.get("min"))
            t_max = _safe_numeric(entry.get("max"))
            if t_min is not None and "temp_min" not in result:
                result["temp_min"] = t_min
            if t_max is not None and "temp_max" not in result:
                result["temp_max"] = t_max

    return result


def _extract_thermal(thermal_data: dict) -> dict:
    """Extract thermal resistance data from the thermal dict."""
    result: dict = {}
    for key, entry in thermal_data.items():
        if not isinstance(entry, dict):
            continue
        record: dict = {}
        for vk in ("min", "typ", "max"):
            v = _safe_numeric(entry.get(vk))
            if v is not None:
                record[vk] = v
        # Some thermal entries use "value" instead of min/typ/max
        if not record:
            v = _safe_numeric(entry.get("value"))
            if v is not None:
                record["typ"] = v
        if entry.get("unit"):
            record["unit"] = entry["unit"]
        if record:
            # Normalize key: theta_ja, theta_jc, theta_jb, psi_jt, psi_jb, etc.
            result[key] = record
    return result


def _extract_packages(packages_data: dict) -> tuple[list[str], int]:
    """Extract package names and maximum pin count."""
    if not isinstance(packages_data, dict):
        return [], 0
    names = sorted(packages_data.keys())
    max_pin = 0
    for _pkg_name, pkg_info in packages_data.items():
        if isinstance(pkg_info, dict):
            pc = pkg_info.get("pin_count", 0)
            if isinstance(pc, int) and pc > max_pin:
                max_pin = pc
    return names, max_pin


def _extract_features(device_data: dict) -> list[str]:
    """Extract notable feature flags from device data."""
    features: list[str] = []

    hints = device_data.get("drc_hints", {})

    # Topology
    topo = hints.get("topology")
    if topo:
        features.append(f"topology:{topo}")

    # Output type
    ot = hints.get("output_type")
    if ot:
        features.append(f"output:{ot}")

    # Fixed output voltage
    fv = hints.get("output_voltage_fixed")
    if isinstance(fv, dict) and fv.get("value") is not None:
        features.append(f"fixed_vout:{fv['value']}{fv.get('unit', 'V')}")

    # Device function
    df = hints.get("device_function")
    if df:
        features.append(f"function:{df}")

    # Requires external MOSFET
    if hints.get("requires_external_mosfet"):
        features.append("external_mosfet")

    # Register domains (I2C / SPI programmable)
    domains = device_data.get("domains", {})
    if isinstance(domains, dict) and "register" in domains:
        features.append("register_interface")

    return features


# ─── Selection Card Builder ──────────────────────────────────────────


def build_selection_card(device_data: dict) -> dict | None:
    """Build a selection card from a sch_review_export device JSON.

    Returns None if the device lacks a valid MPN.
    """
    mpn = device_data.get("mpn")
    if not mpn:
        return None

    category = device_data.get("category", "Other")
    manufacturer = device_data.get("manufacturer")
    description = device_data.get("description")

    elec_params = device_data.get("electrical_parameters", {})
    abs_max = device_data.get("absolute_maximum_ratings", {})
    hints = device_data.get("drc_hints", {})
    thermal_data = device_data.get("thermal", {})
    packages_data = device_data.get("packages", {})

    # --- Key specs: merge from electrical params and drc_hints ---
    key_specs = _extract_specs_from_params(elec_params)

    # Supplement with drc_hints (fills gaps only)
    hint_specs = _extract_specs_from_drc_hints(hints)
    for sk, sv in hint_specs.items():
        if sk not in key_specs:
            key_specs[sk] = sv

    # Also pull input voltage abs max from drc_hints
    vin_abs = hints.get("vin_abs_max")
    if isinstance(vin_abs, dict) and vin_abs.get("value") is not None:
        if "input_voltage_abs_max" not in key_specs:
            key_specs["input_voltage_abs_max"] = {
                "max": _safe_numeric(vin_abs["value"]),
                "unit": vin_abs.get("unit", "V"),
            }

    # --- Operating conditions ---
    operating: dict = {}
    iv = key_specs.get("input_voltage", {})
    if iv.get("min") is not None or iv.get("max") is not None:
        vin_range = [iv.get("min"), iv.get("max")]
        if vin_range[0] is not None or vin_range[1] is not None:
            operating["vin_range"] = vin_range

    ov = key_specs.get("output_voltage", {})
    if ov.get("min") is not None or ov.get("max") is not None:
        vout_range = [ov.get("min"), ov.get("max")]
        if vout_range[0] is not None or vout_range[1] is not None:
            operating["vout_range"] = vout_range
    elif ov.get("typ") is not None:
        operating["vout_typ"] = ov["typ"]

    oc = key_specs.get("output_current", {})
    iout_max = oc.get("max") or oc.get("typ")
    if iout_max is not None:
        operating["iout_max"] = iout_max

    temp = _extract_temp_range(abs_max, elec_params)
    if temp.get("temp_min") is not None or temp.get("temp_max") is not None:
        operating["temp_range"] = [temp.get("temp_min"), temp.get("temp_max")]
        operating["temp_unit"] = "C"
    if temp.get("tj_max") is not None:
        operating["tj_max"] = temp["tj_max"]

    # --- Packages ---
    packages, pin_count = _extract_packages(packages_data)

    # --- Thermal ---
    thermal = _extract_thermal(thermal_data)

    # --- Features ---
    features = _extract_features(device_data)

    card = {
        "_schema": SCHEMA_VERSION,
        "mpn": mpn,
        "manufacturer": manufacturer,
        "category": category,
        "description": description,
        "key_specs": key_specs,
        "operating_conditions": operating,
        "packages": packages,
        "pin_count": pin_count,
        "thermal": thermal,
        "features": features,
    }
    return card


# ─── Comparative Index ───────────────────────────────────────────────


def build_index(cards: list[dict]) -> dict:
    """Build the comparative index from all selection cards."""
    categories: dict[str, list[str]] = defaultdict(list)
    devices: list[dict] = []

    for card in cards:
        mpn = card["mpn"]
        cat = card.get("category", "Other")
        categories[cat].append(mpn)

        ks = card.get("key_specs", {})
        oc = card.get("operating_conditions", {})

        # Build compact index entry
        vin_max = None
        vin_range = oc.get("vin_range")
        if isinstance(vin_range, list) and len(vin_range) >= 2:
            vin_max = vin_range[1]

        vout_range_str = None
        vout_range = oc.get("vout_range")
        if isinstance(vout_range, list) and len(vout_range) >= 2:
            parts = []
            if vout_range[0] is not None:
                parts.append(str(vout_range[0]))
            if vout_range[1] is not None:
                parts.append(str(vout_range[1]))
            if parts:
                vout_range_str = "-".join(parts) + "V"
        elif oc.get("vout_typ") is not None:
            vout_range_str = f"{oc['vout_typ']}V"

        devices.append({
            "mpn": mpn,
            "manufacturer": card.get("manufacturer"),
            "category": cat,
            "vin_max": vin_max,
            "vout_range": vout_range_str,
            "iout_max": oc.get("iout_max"),
            "iq_typ": ks.get("quiescent_current", {}).get("typ"),
            "packages": card.get("packages", []),
        })

    # Sort categories alphabetically, devices by category then MPN
    return {
        "_schema": INDEX_SCHEMA_VERSION,
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_devices": len(cards),
        "categories": dict(sorted(categories.items())),
        "devices": sorted(
            devices, key=lambda d: (d.get("category", ""), d.get("mpn", ""))
        ),
    }


# ─── Main ────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Export selection profiles from sch_review_export data."
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help="Directory containing sch_review_export JSON files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write selection profile JSON files",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a summary of exported devices by category",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load and process all sch_review_export files
    cards: list[dict] = []
    skipped = 0
    errors = 0

    export_files = sorted(args.export_dir.glob("*.json"))
    if not export_files:
        print(f"No JSON files found in {args.export_dir}", file=sys.stderr)
        sys.exit(1)

    for path in export_files:
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  WARN: skipping {path.name}: {exc}", file=sys.stderr)
            errors += 1
            continue

        # Skip FPGA devices (selection profile targets ICs only for now)
        if data.get("_type") == "fpga":
            skipped += 1
            continue

        card = build_selection_card(data)
        if card is None:
            skipped += 1
            continue

        card["source_file"] = path.name
        cards.append(card)

        # Write per-device card
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", card["mpn"])
        out_path = args.output_dir / f"{safe_name}.json"
        out_path.write_text(
            json.dumps(card, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # Build and write comparative index
    index = build_index(cards)
    index_path = args.output_dir / "_index.json"
    index_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Print summary
    if args.summary:
        print("Selection Profile Export")
        print(f"  Total devices exported: {len(cards)}")
        print(f"  Skipped: {skipped}")
        print(f"  Errors: {errors}")
        for cat, mpns in sorted(index["categories"].items()):
            print(f"  {cat}: {len(mpns)} devices")

    print(
        f"\nExported {len(cards)} selection profiles to {args.output_dir}/"
    )


if __name__ == "__main__":
    main()
