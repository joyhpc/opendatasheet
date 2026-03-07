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

SCHEMA_VERSION = "sch-review-device/1.1"

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
    raw_elec = ext.get("electrical_characteristics", [])
    raw_abs = ext.get("absolute_maximum_ratings", [])
    drc_hints = _extract_drc_hints(category, abs_max, elec_params,
                                    raw_elec=raw_elec, raw_abs=raw_abs)
    thermal = _extract_thermal(raw_elec=raw_elec, raw_abs=raw_abs)

    # --- Determine layers ---
    layers = ["L0_skeleton"]
    if elec_params or abs_max:
        layers.append("L1_electrical")

    result = {
        "_schema": SCHEMA_VERSION,
        "_type": "normal_ic",
        "_layers": layers,
        "mpn": mpn,
        "manufacturer": comp.get("manufacturer"),
        "category": category,
        "description": comp.get("description"),
        "packages": packages,
        "absolute_maximum_ratings": abs_max,
        "electrical_parameters": elec_params,
        "drc_hints": drc_hints,
        "thermal": thermal,
    }

    return result


def _thermal_record(item: dict, source: str) -> dict:
    return {
        "parameter": item.get("parameter"),
        "symbol": item.get("symbol"),
        "min": item.get("min"),
        "typ": item.get("typ"),
        "max": item.get("max"),
        "value": item.get("value"),
        "unit": item.get("unit"),
        "conditions": item.get("conditions"),
        "source": source,
    }


def _classify_thermal_key(item: dict) -> str | None:
    symbol = (item.get("symbol") or "").upper().replace(" ", "")
    parameter = (item.get("parameter") or "").lower()
    conditions = (item.get("conditions") or "").lower()
    haystack = f"{symbol} {parameter} {conditions}"

    if "power dissipation capacitance" in parameter:
        return None
    if "power dissipation" in parameter or re.match(r"^P[Dd]$", symbol):
        return "power_dissipation"
    if re.search(r"(PSI|Ψ)\s*JT", symbol) or "junction-to-top" in parameter or "junction to top" in parameter:
        return "psi_jt"
    if re.search(r"(PSI|Ψ)\s*JB", symbol) or "junction-to-board characterization" in parameter or "junction to board characterization" in parameter:
        return "psi_jb"
    if re.search(r"(R|θ|Θ).*JC", symbol) or "junction-to-case" in parameter or "junction to case" in parameter:
        if "bottom" in haystack or "bot" in symbol:
            return "theta_jc_bottom"
        if "top" in haystack:
            return "theta_jc_top"
        return "theta_jc"
    if re.search(r"(R|θ|Θ).*JB", symbol) or "junction-to-board" in parameter or "junction to board" in parameter:
        return "theta_jb"
    if re.search(r"(R|θ|Θ).*JA", symbol) or "junction-to-ambient" in parameter or "junction to ambient" in parameter or "junction-to-air" in parameter or "junction to air" in parameter:
        return "theta_ja"
    if "thermal resistance" in parameter and not any(token in parameter for token in ("case", "board", "top", "bottom")):
        return "theta_ja"
    return None


def _append_thermal_entry(thermal: dict, key: str, item: dict, source: str) -> None:
    record = _thermal_record(item, source)
    candidate = key
    if candidate in thermal:
        suffix = _sanitize(item.get("conditions") or item.get("parameter") or item.get("symbol") or str(len(thermal)))
        candidate = f"{key}_{suffix}" if suffix else f"{key}_{len(thermal)}"
        while candidate in thermal:
            candidate = f"{candidate}_dup"
    thermal[candidate] = record


def _extract_thermal(raw_elec: list = None, raw_abs: list = None) -> dict:
    thermal = {}
    for source, items in (("electrical_characteristics", raw_elec or []), ("absolute_maximum_ratings", raw_abs or [])):
        for item in items:
            key = _classify_thermal_key(item)
            if key:
                _append_thermal_entry(thermal, key, item, source)
    return thermal


def _extract_drc_hints(category: str, abs_max: dict, elec_params: dict,
                       raw_elec: list = None, raw_abs: list = None) -> dict:
    """Extract DRC-critical values using semantic fuzzy matching.

    Uses both dict-keyed params (abs_max, elec_params) and raw list params
    (raw_elec, raw_abs) from extraction for maximum coverage.
    """
    hints = {}
    elec_list = raw_elec or []
    abs_list = raw_abs or []

    def _find(source_list, sym_pats=None, desc_pats=None):
        """Fuzzy match on symbol or parameter description."""
        for p in source_list:
            sym = p.get('symbol') or ''
            desc = p.get('parameter') or ''
            if sym_pats:
                for pat in sym_pats:
                    if re.match(pat, sym, re.IGNORECASE):
                        return p
            if desc_pats:
                for pat in desc_pats:
                    if re.search(pat, desc, re.IGNORECASE):
                        return p
        return None

    def _hint(p, keys=('min', 'typ', 'max', 'unit')):
        return {k: p.get(k) for k in keys if p.get(k) is not None}

    # --- vin_abs_max ---
    p = _find(abs_list,
              sym_pats=[r'^V[_\(]?IN', r'^VCC', r'^VDD'],
              desc_pats=[r'input.*volt', r'supply.*volt', r'voltage\s+at\s+pin.*VIN'])
    if p and p.get('max') is not None:
        hints['vin_abs_max'] = {'value': p['max'], 'unit': p.get('unit', 'V')}

    # --- vin_operating ---
    p = _find(elec_list,
              sym_pats=[r'^V[_\(]?IN', r'^VCC', r'^VDD'],
              desc_pats=[r'input.*volt.*range', r'input.*operat', r'supply.*volt.*range'])
    if p and (p.get('min') is not None or p.get('max') is not None):
        hints['vin_operating'] = _hint(p)

    # --- vref ---
    p = _find(elec_list,
              sym_pats=[r'^V[_\(]?REF', r'^V[_\(]?FB', r'^VFEEDBACK'],
              desc_pats=[r'reference\s+volt', r'feedback.*volt', r'feedback.*regul'])
    if p:
        hints['vref'] = _hint(p)

    # --- vout ---
    p = _find(elec_list,
              sym_pats=[r'^V[_\(]?OUT'],
              desc_pats=[r'^output\s+volt.*range', r'^output\s+volt.*accur'])
    if p:
        hints['vout'] = _hint(p)

    # --- enable_threshold ---
    p = _find(elec_list,
              sym_pats=[r'^V.*EN', r'^VTH.*EN', r'^VIH.*EN', r'^VIL.*EN', r'^VIH$', r'^VIL$'],
              desc_pats=[r'enable.*thresh', r'enable.*volt.*ris', r'enable.*high', r'high.level\s+input\s+volt'])
    if p:
        hints['enable_threshold'] = _hint(p)

    # --- iout_max ---
    p = _find(elec_list,
              sym_pats=[r'^I[_\(]?LIM', r'^I[_\(]?OUT', r'^I[_\(]?LOAD', r'^I[_\(]?OCL'],
              desc_pats=[r'current\s+limit', r'output\s+current', r'load\s+current', r'source\s+current\s+limit'])
    if p:
        hints['iout_max'] = _hint(p)

    # --- iq ---
    p = _find(elec_list,
              sym_pats=[r'^I[_\(]?Q\b', r'^I[_\(]?GND', r'^IVDD\(S0\)'],
              desc_pats=[r'quiescent\s+curr', r'supply\s+curr.*operat', r'VDD\s+supply\s+curr'])
    if p:
        hints['iq'] = _hint(p)

    # --- fsw ---
    p = _find(elec_list,
              sym_pats=[r'^f[_\(]?SW', r'^F[_\(]?OSC', r'^f[_\(]?CLK'],
              desc_pats=[r'switch.*freq', r'oscillat.*freq', r'PWM.*freq'])
    if p:
        hints['fsw'] = _hint(p)

    # --- soft_start ---
    p = _find(elec_list,
              sym_pats=[r'^t[_\(]?SS', r'^I[_\(]?SS'],
              desc_pats=[r'soft.?start\s+time', r'soft.?start\s+charge'])
    if p:
        hints['soft_start'] = _hint(p)

    # --- thermal_shutdown ---
    p = _find(elec_list,
              sym_pats=[r'^T[_\(]?SD', r'^TJ[_\(]?SD', r'^T[_\(]?OTP'],
              desc_pats=[r'thermal\s+shut', r'over.?temp.*protect'])
    if p:
        hints['thermal_shutdown'] = _hint(p)

    # --- thermal_resistance ---
    p = _find(elec_list,
              sym_pats=[r'^[θR].*JA', r'^RθJA'],
              desc_pats=[r'junction.to.ambient', r'thermal\s+resist'])
    if p:
        hints['thermal_resistance'] = _hint(p)

    # --- uvlo ---
    p = _find(elec_list,
              sym_pats=[r'^V.*UVLO', r'^V.*UVP'],
              desc_pats=[r'under.?volt.*lock', r'UVLO.*thresh.*ris'])
    if p:
        hints['uvlo'] = _hint(p)

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
    """Ensure every pin has a 'category' field and normalized function."""
    FUNCTION_MAP = {
        # IO
        "I/O": "IO", "i/o": "IO", "IO": "IO", "DIO": "IO", "MIPI": "IO",
        # Power / Ground
        "POWER": "POWER", "Power": "POWER",
        "GROUND": "GROUND", "Ground": "GROUND", "GND": "GROUND",
        # Config
        "CONFIG": "CONFIG", "JTAG": "CONFIG",
        # GT / SerDes
        "GT": "GT", "GT_RX": "GT", "GT_TX": "GT", "GT_REFCLK": "GT",
        "GT_POWER": "GT_POWER",
        "SERDES": "GT", "SERDES_RX": "GT", "SERDES_TX": "GT",
        "SERDES_REFCLK": "GT",
        # Special
        "RSVDGND": "RSVDGND", "NC": "NC",
        "SPECIAL": "SPECIAL", "OTHER": "SPECIAL",
    }
    for pin in pins:
        if not pin.get("category"):
            pin["category"] = _classify_pin(pin)
        # Normalize function to schema enum
        raw_func = pin.get("function", "")
        name = pin.get("name", "")
        # NC override: if name is exactly "NC", force NC regardless of raw function
        if name == "NC":
            pin["function"] = "NC"
        else:
            pin["function"] = FUNCTION_MAP.get(raw_func, FUNCTION_MAP.get(pin["category"], "SPECIAL"))
        # Normalize drc.must_connect to boolean
        drc = pin.get("drc")
        if drc and "must_connect" in drc:
            mc = drc["must_connect"]
            if isinstance(mc, str):
                # "recommended" → True with priority hint, "mode_dependent" → True with hint
                drc["connect_priority"] = mc  # preserve original semantics
                drc["must_connect"] = mc not in ("false", "no", "optional")
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


def _normalize_banks(banks: dict) -> dict:
    """Ensure every bank entry has a 'bank' key."""
    result = {}
    for bank_id, bank_data in banks.items():
        if isinstance(bank_data, dict):
            if "bank" not in bank_data:
                bank_data = {"bank": str(bank_id), **bank_data}
            # Ensure total_pins and io_pins exist
            if "total_pins" not in bank_data:
                bank_data["total_pins"] = len(bank_data.get("pins", []))
            if "io_pins" not in bank_data:
                bank_data["io_pins"] = bank_data.get("io_count", bank_data["total_pins"])
        result[bank_id] = bank_data
    return result


def _normalize_diff_pairs(pairs: list) -> list:
    """Normalize diff pair field names to p_pin/n_pin standard."""
    result = []
    for dp in pairs:
        normalized = dict(dp)
        # GW5AT-15 PDF format: true_pin/comp_pin → p_pin/n_pin
        if "true_pin" in normalized and "p_pin" not in normalized:
            normalized["p_pin"] = normalized.pop("true_pin")
            normalized["n_pin"] = normalized.pop("comp_pin", "")
            normalized["p_name"] = normalized.pop("true_name", None)
            normalized["n_name"] = normalized.pop("comp_name", None)
        # Ensure required fields
        if "p_pin" not in normalized:
            normalized["p_pin"] = ""
        if "n_pin" not in normalized:
            normalized["n_pin"] = ""
        if "type" not in normalized:
            normalized["type"] = "LVDS"
        result.append(normalized)
    return result


def _normalize_drc_rules(rules: dict) -> dict:
    """Ensure every DRC rule has a valid severity field."""
    SEVERITY_MAP = {
        "critical": "ERROR", "error": "ERROR", "ERROR": "ERROR",
        "warning": "WARNING", "WARNING": "WARNING",
        "info": "INFO", "INFO": "INFO",
    }
    result = {}
    for key, rule in rules.items():
        if isinstance(rule, dict):
            sev = rule.get("severity", "ERROR")
            rule = dict(rule)
            rule["severity"] = SEVERITY_MAP.get(sev, "ERROR")
        result[key] = rule
    return result


def _normalize_package_token(package: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (package or "").upper())


def _gowin_serdes_package_rate_ceiling(package: str) -> float | None:
    package_token = _normalize_package_token(package)
    if package_token.startswith("PG"):
        return 8.0
    if package_token.startswith("FPG"):
        return 12.5
    if package_token.startswith("MBG"):
        return 10.3125
    return None


def _gowin_protocol_matrix(transceiver_count: int) -> dict:
    lane_widths = [1]
    if transceiver_count >= 2:
        lane_widths.append(2)
    if transceiver_count >= 4:
        lane_widths.append(4)
    if transceiver_count >= 8:
        lane_widths.append(8)
    return {
        "custom": {
            "hardcore": False,
            "lane_widths": lane_widths,
        },
        "PCIe 3.0": {
            "hardcore": transceiver_count >= 4,
            "lane_widths": [width for width in lane_widths if width <= 4],
        },
    }


def _infer_gowin_ip_blocks(pinout_data: dict) -> dict | None:
    device = pinout_data.get("device", "")
    package = pinout_data.get("package", "")
    if not device.startswith("GW5AT-"):
        return None

    package_token = _normalize_package_token(package)
    summary = pinout_data.get("summary", {})
    diff_summary = summary.get("diff_pairs", {}) if isinstance(summary, dict) else {}

    profiles = {
        "GW5AT-15": {
            "default": {
                "transceiver_count": 4,
                "mipi": {
                    "present": True,
                    "phy_types": ["D-PHY", "C-PHY"],
                    "directions": ["RX", "TX"],
                    "dphy": {
                        "max_data_lanes": 4,
                        "max_clock_lanes": 1,
                        "max_rate_gbps_per_lane": 2.5,
                    },
                    "cphy": {
                        "max_trios": 3,
                        "max_symbol_rate_gsps": 2.28,
                    },
                },
            },
            "package_overrides": {},
        },
        "GW5AT-60": {
            "default": {
                "transceiver_count": 4,
                "mipi": {
                    "present": False,
                    "phy_types": [],
                    "directions": [],
                },
            },
            "package_overrides": {
                "UG225": {
                    "mipi": {
                        "present": True,
                        "phy_types": ["D-PHY", "C-PHY"],
                        "directions": ["RX", "TX"],
                        "dphy": {
                            "max_data_lanes": 4,
                            "max_clock_lanes": 1,
                            "max_rate_gbps_per_lane": 2.5,
                        },
                        "cphy": {
                            "max_trios": 3,
                            "max_symbol_rate_gsps": 2.28,
                        },
                    },
                },
                "UG225H": {
                    "mipi": {
                        "present": True,
                        "phy_types": ["D-PHY", "C-PHY"],
                        "directions": ["RX", "TX"],
                        "dphy": {
                            "max_data_lanes": 4,
                            "max_clock_lanes": 1,
                            "max_rate_gbps_per_lane": 2.5,
                        },
                        "cphy": {
                            "max_trios": 3,
                            "max_symbol_rate_gsps": 2.28,
                        },
                    },
                },
                "CS234": {
                    "mipi": {
                        "present": True,
                        "phy_types": ["D-PHY", "C-PHY"],
                        "directions": ["RX", "TX"],
                        "dphy": {
                            "max_data_lanes": 4,
                            "max_clock_lanes": 1,
                            "max_rate_gbps_per_lane": 2.5,
                        },
                        "cphy": {
                            "max_trios": 3,
                            "max_symbol_rate_gsps": 2.28,
                        },
                    },
                },
            },
        },
        "GW5AT-75": {
            "default": {
                "transceiver_count": 8,
                "mipi": {
                    "present": False,
                    "phy_types": [],
                    "directions": [],
                },
            },
            "package_overrides": {
                "UG484": {
                    "mipi": {
                        "present": True,
                        "phy_types": ["D-PHY"],
                        "directions": ["RX"],
                        "dphy": {
                            "max_data_lanes": 8,
                            "max_clock_lanes": 2,
                            "max_rate_gbps_per_lane": 2.5,
                        },
                    },
                },
            },
        },
        "GW5AT-138": {
            "default": {
                "transceiver_count": 4,
                "mipi": {
                    "present": False,
                    "phy_types": [],
                    "directions": [],
                },
            },
            "package_overrides": {
                "FPG676A": {
                    "transceiver_count": 8,
                    "mipi": {
                        "present": True,
                        "phy_types": ["D-PHY"],
                        "directions": ["RX"],
                        "dphy": {
                            "max_data_lanes": 8,
                            "max_clock_lanes": 2,
                            "max_rate_gbps_per_lane": 2.5,
                        },
                    },
                },
                "PG676A": {
                    "transceiver_count": 8,
                    "mipi": {
                        "present": True,
                        "phy_types": ["D-PHY"],
                        "directions": ["RX"],
                        "dphy": {
                            "max_data_lanes": 8,
                            "max_clock_lanes": 2,
                            "max_rate_gbps_per_lane": 2.5,
                        },
                    },
                },
                "UG324A": {
                    "transceiver_count": 4,
                    "mipi": {
                        "present": True,
                        "phy_types": ["D-PHY"],
                        "directions": ["RX"],
                        "dphy": {
                            "max_data_lanes": 8,
                            "max_clock_lanes": 2,
                            "max_rate_gbps_per_lane": 2.5,
                        },
                    },
                },
                "PG484": {
                    "transceiver_count": 4,
                    "mipi": {
                        "present": True,
                        "phy_types": ["D-PHY"],
                        "directions": ["RX"],
                        "dphy": {
                            "max_data_lanes": 8,
                            "max_clock_lanes": 2,
                            "max_rate_gbps_per_lane": 2.5,
                        },
                    },
                },
            },
        },
    }

    profile = profiles.get(device)
    if not profile:
        return None

    merged = dict(profile["default"])
    package_override = profile.get("package_overrides", {}).get(package_token, {})
    merged.update({k: v for k, v in package_override.items() if k != "mipi"})
    mipi = dict(profile["default"].get("mipi", {}))
    mipi.update(package_override.get("mipi", {}))

    transceiver_count = merged.get("transceiver_count") or 0
    quad_count = transceiver_count // 4 if transceiver_count else 0
    package_rate_ceiling = _gowin_serdes_package_rate_ceiling(package)
    refclk_pair_count = diff_summary.get("SERDES_REFCLK") if isinstance(diff_summary, dict) else None

    result = {
        "mipi": {
            **mipi,
            "source": "gowin_product_detail_72",
            "source_url": "https://www.gowinsemi.com/en/product/detail/72/",
        },
        "serdes": {
            "transceiver_count": transceiver_count,
            "quad_count": quad_count,
            "lanes_per_quad": 4 if quad_count else 0,
            "rate_range_gbps": [0.27, 12.5],
            "package_rate_ceiling_gbps": package_rate_ceiling,
            "supported_protocols": ["custom", "PCIe 3.0"],
            "protocol_matrix": _gowin_protocol_matrix(transceiver_count),
            "refclk_pair_count": refclk_pair_count,
            "source": "gowin_product_detail_72",
            "source_url": "https://www.gowinsemi.com/en/product/detail/72/",
        },
    }
    return result


def export_fpga(dc_data: dict, pinout_data: dict, gowin_dc: dict = None, lattice_dc: dict = None) -> dict:
    """Combine FPGA DC datasheet + pinout into sch-review format.

    dc_data: AMD-style extracted datasheet (with extraction.component etc.)
    gowin_dc: Gowin-style DC extraction (from extract_gowin_dc.py)
    lattice_dc: Lattice-style DC extraction (from extract_lattice_dc.py)
    """
    ext = dc_data.get("extraction", {})
    comp = ext.get("component", {})

    # --- Supply voltage specs from DC datasheet ---
    supply_specs = {}
    io_standard_specs = {}
    abs_max_specs = {}

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
        # abs_max_specs already initialized
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

    # Lattice-style DC data
    if lattice_dc:
        # Recommended operating conditions
        for item in lattice_dc.get("recommended_operating", []):
            sym = item.get("symbol") or item.get("parameter", "")
            if not sym:
                continue
            param = item.get("parameter", sym)
            key = sym
            if key in supply_specs:
                key = f"{sym}_lattice"
            supply_specs[key] = {
                "parameter": param,
                "symbol": sym,
                "min": item.get("min"),
                "typ": item.get("typ"),
                "max": item.get("max"),
                "unit": item.get("unit", "V"),
                "conditions": "Recommended operating",
                "source": "recommended_operating",
            }

        # Absolute maximum ratings
        # abs_max_specs already initialized
        for item in lattice_dc.get("absolute_maximum_ratings", []):
            sym = item.get("symbol") or item.get("parameter", "")
            if not sym:
                continue
            param = item.get("parameter", sym)
            key = f"abs_{sym}"
            abs_max_specs[key] = {
                "parameter": param,
                "symbol": sym,
                "min": item.get("min"),
                "max": item.get("max"),
                "unit": item.get("unit", "V"),
                "conditions": "Absolute maximum",
                "source": "absolute_maximum",
            }

        # IO standards
        for item in lattice_dc.get("io_standards", []):
            std = item.get("standard", "")
            if std:
                param = item.get("parameter", "")
                key = f"lattice_{std}"
                if param:
                    key = f"lattice_{param}_{std}"
                io_standard_specs[key] = {
                    "standard": std,
                    "parameter": param,
                    "value": item.get("value"),
                    "raw": item.get("raw"),
                }

    # --- IO standard specs from DC datasheet ---
    # io_standard_specs already initialized

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
    elif vendor == "Lattice":
        manufacturer = "Lattice"
    else:
        manufacturer = comp.get("manufacturer", "AMD")

    raw_elec = ext.get("electrical_characteristics", [])
    raw_abs = ext.get("absolute_maximum_ratings", [])
    if gowin_dc:
        raw_abs = raw_abs + list(gowin_dc.get("absolute_maximum_ratings", []))
    if lattice_dc:
        raw_abs = raw_abs + list(lattice_dc.get("absolute_maximum_ratings", []))
    thermal = _extract_thermal(raw_elec=raw_elec, raw_abs=raw_abs)

    result = {
        "_schema": SCHEMA_VERSION,
        "_type": "fpga",
        "mpn": device,
        "manufacturer": manufacturer,
        "category": "FPGA",
        "description": comp.get("description"),
        "package": package,

        # From DC datasheet
        "supply_specs": supply_specs,
        "io_standard_specs": io_standard_specs,
        "thermal": thermal,

        # From pinout (L1-L5)
        "power_rails": pinout_data.get("power_rails", {}),
        "banks": _normalize_banks(pinout_data.get("banks", {})),
        "diff_pairs": _normalize_diff_pairs(pinout_data.get("diff_pairs", [])),
        "drc_rules": _normalize_drc_rules(pinout_data.get("drc_rules", {})),

        # Pin data — full list + normalized lookup
        "pins": _normalize_pins(pinout_data.get("pins", [])),
        "lookup": _normalize_lookup(pinout_data),

        # Summary
        "summary": pinout_data.get("summary", {}),
    }
    ip_blocks = _infer_gowin_ip_blocks(pinout_data)
    if ip_blocks:
        result["ip_blocks"] = ip_blocks

    # Add absolute maximum ratings if available
    if gowin_dc or lattice_dc:
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

    # Load Lattice DC files
    lattice_dc_files = sorted((extracted_dir / "fpga").glob("lattice_*_dc.json"))
    lattice_dc_cache = {}
    for dc_file in lattice_dc_files:
        with open(dc_file) as fp:
            data = json.load(fp)
        family = data.get("family", "")
        device = data.get("device", "")
        lattice_dc_cache[dc_file.name] = data
        # Index by family: ecp5, crosslinknx
        if family:
            lattice_dc_cache[family] = data
        # Also index by device name
        if device:
            lattice_dc_cache[device.lower().replace("-", "_").replace(" ", "_")] = data

    for pinout_file in fpga_pinout_files:
        try:
            with open(pinout_file) as fp:
                pinout_data = json.load(fp)

            device = pinout_data["device"]
            package = pinout_data["package"]

            # Find matching DC datasheet
            dc_data = None
            gowin_dc = None
            lattice_dc = None
            vendor = pinout_data.get("_vendor", "")

            if vendor == "Gowin":
                # Gowin: match by device prefix (GW5AT-60 → GW5AT)
                prefix = device.split("-")[0] if "-" in device else device
                gowin_dc = gowin_dc_cache.get(prefix)
                # Also try Arora V 60K for GW5AT-60
                if gowin_dc is None and "GW5AT-60" in device:
                    gowin_dc = gowin_dc_cache.get("Arora V 60K")
                dc_data = {"extraction": {"component": {}}}
            elif vendor == "Lattice":
                # Lattice: match by family
                family = pinout_data.get("_family", "")
                if "ECP5" in device.upper():
                    lattice_dc = lattice_dc_cache.get("ecp5")
                elif "LIFCL" in device.upper() or "CrossLink" in family:
                    lattice_dc = lattice_dc_cache.get("crosslinknx")
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

            result = export_fpga(dc_data, pinout_data, gowin_dc=gowin_dc, lattice_dc=lattice_dc)
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

    # Generate manifest
    manifest = {"devices": []}
    for f in sorted(output_dir.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            data = json.load(fp)
        manifest["devices"].append({
            "file": f.name,
            "mpn": data.get("mpn", ""),
            "type": data.get("_type", ""),
            "manufacturer": data.get("manufacturer", ""),
        })
    manifest_path = output_dir / "_manifest.json"
    with open(manifest_path, "w") as fp:
        json.dump(manifest, fp, indent=2)
    print(f"Manifest: {manifest_path} ({len(manifest['devices'])} devices)")


if __name__ == "__main__":
    main()
