#!/usr/bin/env python3
"""Export OpenDatasheet extracted data to sch-review compatible format.

Converts per-device datasheet JSON + FPGA pinout JSON into a unified
device knowledge base that sch-review's DRC engine can consume.

Output schema: one JSON file per device, keyed by MPN.

Usage:
    python export_for_sch_review.py [--extracted-dir DIR] [--fpga-pinout-dir DIR] [--output-dir DIR]
    python export_for_sch_review.py  # uses default paths
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_EXTRACTED_DIR = Path(__file__).parent.parent / "data/extracted_v2"
DEFAULT_FPGA_PINOUT_DIR = Path(__file__).parent.parent / "data/extracted_v2/fpga/pinout"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data/sch_review_export"

# ─── Normal IC Export ───────────────────────────────────────────────


def export_normal_ic(data: dict) -> dict | None:
    """Convert a normal IC datasheet JSON to sch-review format."""
    ext = data.get("extraction", {})
    comp = ext.get("component", {})
    pin_index = data.get("pin_index", {})

    if not comp.get("mpn"):
        return None

    mpn = comp["mpn"]
    category = comp.get("category", "Unknown")

    # --- Pin definitions per package ---
    packages = {}
    for pkg_name, pins in pin_index.get("packages", {}).items():
        pkg_pins = {}
        for pin_num, pin_info in pins.items():
            pkg_pins[str(pin_num)] = {
                "name": pin_info["name"],
                "direction": pin_info["direction"],
                "signal_type": pin_info["signal_type"],
                "description": pin_info.get("description"),
                "unused_treatment": pin_info.get("unused_treatment"),
            }
        packages[pkg_name] = {
            "pin_count": len(pkg_pins),
            "pins": pkg_pins,
        }

    # --- Absolute maximum ratings ---
    abs_max = {}
    for item in ext.get("absolute_maximum_ratings", []):
        sym = item.get("symbol", "")
        if not sym:
            continue
        key = sym
        # Handle duplicates by appending condition
        if key in abs_max and item.get("conditions"):
            key = f"{sym}_{_sanitize(item['conditions'])}"
        abs_max[key] = {
            "parameter": item["parameter"],
            "min": item.get("min"),
            "max": item.get("max"),
            "unit": item.get("unit"),
            "conditions": item.get("conditions"),
        }

    # --- Key electrical parameters ---
    elec_params = {}
    for item in ext.get("electrical_characteristics", []):
        sym = item.get("symbol", "")
        if not sym:
            continue
        key = sym
        cond = item.get("conditions", "")
        if key in elec_params and cond:
            key = f"{sym}_{_sanitize(cond)}"
        elec_params[key] = {
            "parameter": item["parameter"],
            "min": item.get("min"),
            "typ": item.get("typ"),
            "max": item.get("max"),
            "unit": item.get("unit"),
            "conditions": cond or None,
        }

    # --- Extract DRC-critical values ---
    drc_hints = _extract_drc_hints(category, abs_max, elec_params)

    result = {
        "_schema": "sch-review-device/1.0",
        "_type": "normal_ic",
        "mpn": mpn,
        "manufacturer": comp.get("manufacturer"),
        "category": category,
        "description": comp.get("description"),
        "packages": packages,
        "absolute_maximum_ratings": abs_max,
        "electrical_parameters": elec_params,
        "drc_hints": drc_hints,
    }

    return result


def _extract_drc_hints(category: str, abs_max: dict, elec_params: dict) -> dict:
    """Extract DRC-critical values from parameters for quick access."""
    hints = {}

    # Vin max
    for key in ["VIN", "Vin", "VI"]:
        if key in abs_max and abs_max[key].get("max") is not None:
            hints["vin_abs_max"] = {"value": abs_max[key]["max"], "unit": abs_max[key].get("unit", "V")}
            break

    # Vin operating range
    for key in ["VIN", "Vin", "VI"]:
        if key in elec_params:
            p = elec_params[key]
            if p.get("min") is not None or p.get("max") is not None:
                hints["vin_operating"] = {
                    "min": p.get("min"), "max": p.get("max"), "unit": p.get("unit", "V")
                }
                break

    # Vout (for regulators)
    for key in ["VOUT", "Vout", "VO"]:
        if key in elec_params:
            p = elec_params[key]
            hints["vout"] = {
                "min": p.get("min"), "typ": p.get("typ"), "max": p.get("max"),
                "unit": p.get("unit", "V")
            }
            break

    # Vref / VFB (for Buck/Boost with feedback)
    for key in ["VFB", "Vfb", "VREF", "Vref"]:
        if key in elec_params:
            p = elec_params[key]
            hints["vref"] = {
                "min": p.get("min"), "typ": p.get("typ"), "max": p.get("max"),
                "unit": p.get("unit", "V")
            }
            break

    # Iout max
    for key in ["IOUT", "Iout", "IO"]:
        if key in abs_max and abs_max[key].get("max") is not None:
            hints["iout_abs_max"] = {"value": abs_max[key]["max"], "unit": abs_max[key].get("unit", "A")}
            break
    for key in ["IOUT", "Iout", "IO", "ILIM", "Ilim"]:
        if key in elec_params:
            p = elec_params[key]
            if p.get("max") is not None or p.get("typ") is not None:
                hints["iout_operating"] = {
                    "typ": p.get("typ"), "max": p.get("max"), "unit": p.get("unit", "A")
                }
                break

    # Quiescent current
    for key in ["IQ", "Iq", "IGnd", "IGND"]:
        if key in elec_params:
            p = elec_params[key]
            hints["iq"] = {
                "typ": p.get("typ"), "max": p.get("max"), "unit": p.get("unit", "µA")
            }
            break

    # Enable threshold
    for key in ["VEN", "Ven", "VIH_EN", "VIL_EN"]:
        if key in elec_params:
            p = elec_params[key]
            hints["enable_threshold"] = {
                "min": p.get("min"), "typ": p.get("typ"), "max": p.get("max"),
                "unit": p.get("unit", "V")
            }
            break

    return hints


def _sanitize(s: str) -> str:
    """Sanitize a string for use as a dict key."""
    return re.sub(r"[^a-zA-Z0-9]", "_", s)[:30].strip("_")


# ─── FPGA Pin Normalization ─────────────────────────────────────────


def _classify_pin(pin: dict) -> str:
    """Classify a pin into a standard category."""
    if pin.get("category"):
        return pin["category"]
    name = pin.get("name", "")
    func = pin.get("function", "")
    if "VSS" in name or "GND" in name:
        return "GROUND"
    if "VCC" in name or "VDD" in name or "VQPS" in name:
        return "POWER"
    if func in ("IO", "I/O"):
        return "IO"
    if "Q0_" in name or "Q1_" in name:
        if "RX" in name:
            return "SERDES_RX"
        if "TX" in name:
            return "SERDES_TX"
        if "REFCLK" in name:
            return "SERDES_REFCLK"
        return "SERDES"
    if "MIPI" in name or "M0_" in name:
        return "MIPI"
    if "NC" == name:
        return "NC"
    if func in ("CONFIG", "JTAG"):
        return "CONFIG"
    return "OTHER"


def _normalize_pins(pins: list) -> list:
    """Ensure every pin has a 'category' field."""
    for pin in pins:
        if not pin.get("category"):
            pin["category"] = _classify_pin(pin)
        # Normalize function field
        if pin.get("function") == "IO":
            pin["function"] = "I/O"
    return pins


def _normalize_lookup(pinout_data: dict) -> dict:
    """Normalize lookup to standard {by_pin, by_name} format."""
    lookup = pinout_data.get("lookup", {})
    result = {}

    # Handle xlsx format: pin_to_name / name_to_pin
    if "pin_to_name" in lookup:
        result["by_pin"] = dict(lookup["pin_to_name"]) if isinstance(lookup["pin_to_name"], list) else lookup["pin_to_name"]
        result["by_name"] = dict(lookup["name_to_pin"]) if isinstance(lookup["name_to_pin"], list) else lookup["name_to_pin"]
    # Handle PDF format: by_pin / by_name
    elif "by_pin" in lookup:
        result["by_pin"] = lookup["by_pin"]
        result["by_name"] = lookup["by_name"]
    else:
        # Build from pins
        by_pin = {}
        by_name = {}
        for pin in pinout_data.get("pins", []):
            p = pin.get("pin", "")
            n = pin.get("name", "")
            if p and n:
                by_pin[p] = n
                by_name[n] = p
        result["by_pin"] = by_pin
        result["by_name"] = by_name

    return result


# ─── FPGA Export ────────────────────────────────────────────────────


def export_fpga(dc_data: dict, pinout_data: dict, gowin_dc: dict = None) -> dict:
    """Combine FPGA DC datasheet + pinout into sch-review format.

    dc_data: AMD-style extracted datasheet (with extraction.component etc.)
    gowin_dc: Gowin-style DC extraction (from extract_gowin_dc.py)
    """
    ext = dc_data.get("extraction", {})
    comp = ext.get("component", {})

    # --- Supply voltage specs from DC datasheet ---
    supply_specs = {}

    # AMD-style DC data
    for item in ext.get("electrical_characteristics", []):
        sym = item.get("symbol", "")
        param = item.get("parameter", "")
        cond = item.get("conditions", "") or ""

        if not sym:
            continue
        if sym in ("VCCINT", "VCCBRAM", "VCCAUX", "VCCAUX_IO", "VCCO",
                    "VBATT", "VDRINT", "VDRAUX") or "VCCINT_IO" in sym:
            key = sym
            if cond:
                key = f"{sym}_{_sanitize(cond)}"
            supply_specs[key] = {
                "parameter": param,
                "symbol": sym,
                "min": item.get("min"),
                "typ": item.get("typ"),
                "max": item.get("max"),
                "unit": item.get("unit", "V"),
                "conditions": cond or None,
            }

    # Gowin-style DC data
    if gowin_dc:
        device = pinout_data["device"]
        # Find matching recommended operating entries for this device
        for item in gowin_dc.get("recommended_operating", []):
            dev_tag = item.get("device", "")
            # Match: GW5AT-60 matches "GW5AT-60", GW5AT-138 matches "GW5AT-138 / GW5AT-75"
            # For devices without exact match (e.g. GW5AT-15 in old DS981), check if any entry matches
            has_exact_match = any(device in it.get("device", "") for it in gowin_dc.get("recommended_operating", []))
            if device in dev_tag or not dev_tag or not has_exact_match:
                param_name = item["parameter"]
                desc = item.get("description", "")
                section = item.get("section", "")
                key = param_name
                if section:
                    key = f"{param_name}_{_sanitize(section)}"
                if desc and key in supply_specs:
                    key = f"{param_name}_{_sanitize(desc)}"
                supply_specs[key] = {
                    "parameter": f"{param_name} ({desc})" if desc else param_name,
                    "symbol": param_name,
                    "min": item.get("min"),
                    "max": item.get("max"),
                    "unit": item.get("unit", "V"),
                    "conditions": f"Recommended operating, {section}" if section else "Recommended operating",
                    "source": "recommended_operating",
                }

        # Also add absolute maximum ratings
        abs_max_specs = {}
        has_exact_match_abs = any(device in it.get("device", "") for it in gowin_dc.get("absolute_maximum_ratings", []))
        for item in gowin_dc.get("absolute_maximum_ratings", []):
            dev_tag = item.get("device", "")
            if device in dev_tag or not dev_tag or not has_exact_match_abs:
                param_name = item["parameter"]
                desc = item.get("description", "")
                section = item.get("section", "")
                key = f"abs_{param_name}"
                if section:
                    key = f"abs_{param_name}_{_sanitize(section)}"
                abs_max_specs[key] = {
                    "parameter": f"{param_name} ({desc})" if desc else param_name,
                    "symbol": param_name,
                    "min": item.get("min"),
                    "max": item.get("max"),
                    "unit": item.get("unit", "V"),
                    "conditions": f"Absolute maximum, {section}" if section else "Absolute maximum",
                    "source": "absolute_maximum",
                }

    # --- IO standard specs from DC datasheet ---
    io_standard_specs = {}

    # AMD-style
    for item in ext.get("electrical_characteristics", []):
        cond = item.get("conditions", "") or ""
        param = item.get("parameter", "")
        for std in ("LVDS_25", "LVDS", "SSTL12", "SSTL15", "HSTL", "LVCMOS"):
            if std in cond or std in param:
                key = f"{item.get('symbol', '')}_{std}"
                io_standard_specs[key] = {
                    "parameter": param,
                    "symbol": item.get("symbol"),
                    "min": item.get("min"),
                    "typ": item.get("typ"),
                    "max": item.get("max"),
                    "unit": item.get("unit"),
                    "io_standard": std,
                }
                break

    # Gowin-style IO standards
    if gowin_dc:
        for item in gowin_dc.get("io_standards", []):
            std = item.get("standard", "")
            if std:
                key = f"gowin_{std}"
                if "parameter" in item:
                    key = f"gowin_{item['parameter']}_{std}"
                io_standard_specs[key] = {
                    "standard": std,
                    "vcco": item.get("vcco"),
                    "parameter": item.get("parameter"),
                    "value": item.get("value"),
                    "raw": item.get("raw"),
                }

    # --- Merge pinout data ---
    device = pinout_data["device"]
    package = pinout_data["package"]
    vendor = pinout_data.get("_vendor", "AMD")

    if vendor == "Gowin":
        manufacturer = "Gowin"
    else:
        manufacturer = comp.get("manufacturer", "AMD")

    result = {
        "_schema": "sch-review-device/1.0",
        "_type": "fpga",
        "mpn": device,
        "manufacturer": manufacturer,
        "category": "FPGA",
        "description": comp.get("description"),
        "package": package,

        # From DC datasheet
        "supply_specs": supply_specs,
        "io_standard_specs": io_standard_specs,

        # From pinout (L1-L5)
        "power_rails": pinout_data.get("power_rails", {}),
        "banks": pinout_data.get("banks", {}),
        "diff_pairs": pinout_data.get("diff_pairs", []),
        "drc_rules": pinout_data.get("drc_rules", {}),

        # Pin data — full list + normalized lookup
        "pins": _normalize_pins(pinout_data.get("pins", [])),
        "lookup": _normalize_lookup(pinout_data),

        # Summary
        "summary": pinout_data.get("summary", {}),
    }

    # Add absolute maximum ratings if available
    if gowin_dc:
        result["absolute_maximum_ratings"] = abs_max_specs

    return result


# ─── Main ───────────────────────────────────────────────────────────


def main():
    extracted_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXTRACTED_DIR
    fpga_pinout_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_FPGA_PINOUT_DIR
    output_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    exported = 0
    errors = 0

    # --- Export normal ICs ---
    print("=== Normal ICs ===")
    for f in sorted(extracted_dir.glob("*.json")):
        try:
            with open(f) as fp:
                data = json.load(fp)
            result = export_normal_ic(data)
            if result is None:
                continue
            mpn = result["mpn"]
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", mpn)
            out_path = output_dir / f"{safe_name}.json"
            with open(out_path, "w") as fp:
                json.dump(result, fp, indent=2, ensure_ascii=False)
            pkg_count = len(result["packages"])
            pin_total = sum(p["pin_count"] for p in result["packages"].values())
            hints = len(result["drc_hints"])
            print(f"  {mpn:25s} {result['category']:12s} {pkg_count} pkgs, {pin_total} pins, {hints} DRC hints → {out_path.name}")
            exported += 1
        except Exception as e:
            print(f"  ERROR {f.name}: {e}")
            errors += 1

    # --- Export FPGAs ---
    print("\n=== FPGAs ===")
    # Load DC datasheets
    fpga_dc_files = sorted((extracted_dir / "fpga").glob("ds*.json"))
    fpga_pinout_files = sorted(fpga_pinout_dir.glob("*.json"))

    # Load Gowin DC files
    gowin_dc_files = sorted((extracted_dir / "fpga").glob("gowin_*_dc.json"))
    gowin_dc_cache = {}
    for dc_file in gowin_dc_files:
        with open(dc_file) as fp:
            data = json.load(fp)
        dev = data.get("device", "")
        gowin_dc_cache[dc_file.name] = data
        # Index by device prefix: GW5AT, GW5AR, GW5AS, etc.
        prefix = dev.split("-")[0] if "-" in dev else dev
        gowin_dc_cache[prefix] = data

    for pinout_file in fpga_pinout_files:
        try:
            with open(pinout_file) as fp:
                pinout_data = json.load(fp)

            device = pinout_data["device"]
            package = pinout_data["package"]

            # Find matching DC datasheet
            dc_data = None
            gowin_dc = None
            vendor = pinout_data.get("_vendor", "")

            if vendor == "Gowin":
                # Gowin: match by device prefix (GW5AT-60 → GW5AT)
                prefix = device.split("-")[0] if "-" in device else device
                gowin_dc = gowin_dc_cache.get(prefix)
                # Also try Arora V 60K for GW5AT-60
                if gowin_dc is None and "GW5AT-60" in device:
                    gowin_dc = gowin_dc_cache.get("Arora V 60K")
                dc_data = {"extraction": {"component": {}}}
            else:
                # AMD: match by family
                for dc_file in fpga_dc_files:
                    with open(dc_file) as fp:
                        candidate = json.load(fp)
                    if "kintex" in dc_file.name.lower() and "KU" in device:
                        dc_data = candidate
                        break
                    elif "artix" in dc_file.name.lower() and "AU" in device:
                        dc_data = candidate
                        break

            # No fallback — if no matching DC datasheet, use empty
            if dc_data is None:
                dc_data = {"extraction": {"component": {}}}

            result = export_fpga(dc_data, pinout_data, gowin_dc=gowin_dc)
            safe_name = f"{device}_{package}"
            out_path = output_dir / f"{safe_name}.json"
            with open(out_path, "w") as fp:
                json.dump(result, fp, indent=2, ensure_ascii=False)

            n_pins = len(result["pins"])
            n_pairs = len(result["diff_pairs"])
            n_banks = len(result["banks"])
            n_supply = len(result["supply_specs"])
            print(f"  {device:10s} {package:10s} {n_pins} pins, {n_pairs} pairs, {n_banks} banks, {n_supply} supply specs → {out_path.name}")
            exported += 1
        except Exception as e:
            print(f"  ERROR {pinout_file.name}: {e}")
            errors += 1

    print(f"\n{'='*60}")
    print(f"Exported: {exported}, Errors: {errors}")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
