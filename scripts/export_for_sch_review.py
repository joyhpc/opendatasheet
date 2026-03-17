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

from build_fpga_catalog import build_catalog
from design_guide_domain import load_gowin_design_guide_bundle, resolve_gowin_design_guide_source_path

SCHEMA_VERSION = "sch-review-device/1.1"
SCHEMA_VERSION_V2 = "device-knowledge/2.0"

DEFAULT_EXTRACTED_DIR = Path(__file__).parent.parent / "data/extracted_v2"
DEFAULT_FPGA_PINOUT_DIR = Path(__file__).parent.parent / "data/extracted_v2/fpga/pinout"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data/sch_review_export"
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
    return {}  # In flat format, thermal is embedded in extraction


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
    """Get timing data (only available in domains format)."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        return data["domains"].get("timing", {})
    return {}


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


def get_protocol_data(data: dict) -> dict:
    """Get protocol data (only available in domains format)."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        return data["domains"].get("protocol", {})
    return {}


def get_package_data(data: dict) -> dict:
    """Get package data (only available in domains format)."""
    fmt = detect_input_format(data)
    if fmt == "domains":
        return data["domains"].get("package", {})
    return {}


# ─── Normal IC Export ───────────────────────────────────────────────


def export_normal_ic(data: dict) -> dict | None:
    """Convert a normal IC datasheet JSON to sch-review format."""
    ext = get_extraction(data)
    comp = ext.get("component", {})
    pin_index = get_pin_index(data)

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

    # If domains format provided standalone thermal data, merge it in
    thermal_domain = get_thermal_data(data)
    if thermal_domain:
        for key, value in thermal_domain.items():
            if key not in thermal and isinstance(value, dict):
                thermal[key] = value

    # --- Check for register data ---
    register_data = get_register_data(data)

    # --- Check for timing data ---
    timing_data = get_timing_data(data)

    # --- Check for power sequence data ---
    power_seq_data = get_power_sequence_data(data)

    # --- Check for parametric data ---
    parametric_data = get_parametric_data(data)

    # --- Check for protocol data ---
    protocol_data = get_protocol_data(data)

    # --- Check for package data ---
    package_data = get_package_data(data)

    # --- Determine schema version ---
    # Upgrade to 2.0 if any domain data is present
    schema_version = SCHEMA_VERSION_V2 if (register_data or timing_data or power_seq_data or parametric_data or protocol_data or package_data) else SCHEMA_VERSION

    # --- Determine layers ---
    layers = ["L0_skeleton"]
    if elec_params or abs_max:
        layers.append("L1_electrical")

    result = {
        "_schema": schema_version,
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
    capability_blocks = _infer_normal_ic_capability_blocks(
        mpn=mpn,
        manufacturer=comp.get("manufacturer"),
        category=category,
        description=comp.get("description"),
        packages=packages,
    )
    constraint_blocks = _infer_normal_ic_constraint_blocks(capability_blocks)
    if capability_blocks:
        result["capability_blocks"] = capability_blocks
    if constraint_blocks:
        result["constraint_blocks"] = constraint_blocks

    # Include new domains if present
    if register_data or timing_data or power_seq_data or parametric_data or protocol_data or package_data:
        domains_block = {}
        if register_data:
            domains_block["register"] = register_data
        if timing_data:
            domains_block["timing"] = timing_data
        if power_seq_data:
            domains_block["power_sequence"] = power_seq_data
        if parametric_data:
            domains_block["parametric"] = parametric_data
        if protocol_data:
            domains_block["protocol"] = protocol_data
        if package_data:
            domains_block["package"] = package_data
        result["domains"] = domains_block

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


def _safe_upper(value: str | None) -> str:
    return (value or "").upper()


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


def _flatten_package_pins(packages: dict) -> list[dict]:
    records = []
    for package_name, package_data in packages.items():
        pins = package_data.get("pins", {}) if isinstance(package_data, dict) else {}
        for pin_number, pin_info in pins.items():
            records.append({
                "package": package_name,
                "pin": str(pin_number),
                "name": pin_info.get("name"),
                "description": pin_info.get("description"),
                "direction": pin_info.get("direction"),
                "signal_type": pin_info.get("signal_type"),
            })
    return records


def _signal_groups(pin_records: list[dict], matcher) -> list[dict]:
    groups: dict[str, dict] = {}
    for record in pin_records:
        name = record.get("name") or ""
        description = record.get("description") or ""
        if not name:
            continue
        if not matcher(_safe_upper(name), _safe_upper(description)):
            continue
        entry = groups.setdefault(name, {"name": name, "packages": []})
        entry["packages"].append({"package": record["package"], "pin": record["pin"]})
    return sorted(groups.values(), key=lambda item: item["name"])


def _signal_role_names(pin_records: list[dict], role_matchers: dict[str, object]) -> dict:
    roles = {}
    for role, matcher in role_matchers.items():
        names = [item["name"] for item in _signal_groups(pin_records, matcher) if item.get("name")]
        if names:
            roles[role] = names
    return roles


def _merge_signal_names(*signal_sets) -> list[str]:
    names = set()
    for signal_set in signal_sets:
        if isinstance(signal_set, dict):
            iterables = signal_set.values()
            for items in iterables:
                for name in items or []:
                    if name:
                        names.add(name)
            continue
        for item in signal_set or []:
            if isinstance(item, dict):
                name = item.get("name")
            else:
                name = item
            if name:
                names.add(name)
    return sorted(names)


def _role_subset(role_map: dict, *roles: str) -> list[str]:
    return sorted({name for role in roles for name in role_map.get(role, [])})


def _mcu_like_device(mpn: str, manufacturer: str | None, category: str | None, description: str | None) -> bool:
    haystack = " ".join(filter(None, [mpn, manufacturer or "", category or "", description or ""])).upper()
    prefixes = ("STM32", "GD32", "N32", "LPC", "PIC", "ATSAM", "SAMD", "SAME")
    return mpn.upper().startswith(prefixes) or any(token in haystack for token in ("CORTEX-M", "MICROCONTROLLER", "MCU", "SOC"))


def _infer_normal_ic_capability_blocks(mpn: str, manufacturer: str | None, category: str | None, description: str | None, packages: dict) -> dict:
    if not _mcu_like_device(mpn, manufacturer, category, description):
        return {}

    pin_records = _flatten_package_pins(packages)
    debug_signals = _signal_groups(pin_records, lambda name, desc: any(token in name for token in ("SWDIO", "SWCLK", "SWO", "JTMS", "JTCK", "JTDI", "JTDO", "TRACESWO")))
    boot_signals = _signal_groups(pin_records, lambda name, desc: "BOOT" in name)
    hse_signals = _signal_groups(
        pin_records,
        lambda name, desc: any(token in name for token in ("HSE_IN", "HSE_OUT", "OSC_IN", "OSC_OUT"))
        or bool(re.search(r"(^|[^A-Z0-9])PH[01]([^A-Z0-9]|$)", name))
        or "HIGH-SPEED EXTERNAL" in desc,
    )
    lse_signals = _signal_groups(pin_records, lambda name, desc: any(token in name for token in ("LSE_IN", "LSE_OUT", "OSC32", "PC14", "PC15")) or any(token in desc for token in ("LOW SPEED EXTERNAL", "32.768", "LSE")))
    usb_signals = _signal_groups(pin_records, lambda name, desc: any(token in name for token in ("USB", "OTG", "VBUS", "VDDUSB")) or "USB" in desc)
    usb_roles = _signal_role_names(pin_records, {
        "dp": lambda name, desc: any(token in f"{name} {desc}" for token in ("USBDP", "USB_DP", "OTG_FS_DP", "OTG_HS_DP")),
        "dm": lambda name, desc: any(token in f"{name} {desc}" for token in ("USBDM", "USB_DM", "OTG_FS_DM", "OTG_HS_DM")),
        "vbus": lambda name, desc: "VBUS" in f"{name} {desc}",
        "id": lambda name, desc: any(token in f"{name} {desc}" for token in ("USB_ID", "OTG_FS_ID", "OTG_HS_ID")),
        "usb_supply": lambda name, desc: any(token in name for token in ("VDDUSB", "VDD33USB", "VDD50USB")) or "USB POWER SUPPLY" in desc,
    })
    eth_signals = _signal_groups(pin_records, lambda name, desc: any(token in name for token in ("ETH", "RMII", "MII", "RGMII")) or "ETHERNET" in desc)
    eth_roles = _signal_role_names(pin_records, {
        "mdio": lambda name, desc: "MDIO" in f"{name} {desc}",
        "mdc": lambda name, desc: "MDC" in f"{name} {desc}",
        "ref_clk": lambda name, desc: any(token in f"{name} {desc}" for token in ("RMII_REF_CLK", "REF_CLK", "RX_CLK", "TX_CLK", "ETH_CLK")),
        "tx": lambda name, desc: any(token in f"{name} {desc}" for token in ("TXD", "TX_EN", "TX_ER", "TXER")),
        "rx": lambda name, desc: any(token in f"{name} {desc}" for token in ("RXD", "RX_ER", "RXER", "RX_DV", "CRS_DV")),
    })
    can_signals = _signal_groups(pin_records, lambda name, desc: any(token in name for token in ("FDCAN", "CANRX", "CANTX", "CAN_")) or any(token in desc for token in ("CAN_RX", "CAN_TX", "FDCAN")))
    can_roles = _signal_role_names(pin_records, {
        "rx": lambda name, desc: any(token in f"{name} {desc}" for token in ("CAN_RX", "CANRX")) or bool(re.search(r"FDCAN[0-9_]*.*RX", f"{name} {desc}")),
        "tx": lambda name, desc: any(token in f"{name} {desc}" for token in ("CAN_TX", "CANTX")) or bool(re.search(r"FDCAN[0-9_]*.*TX", f"{name} {desc}")),
    })
    qspi_signals = _signal_groups(pin_records, lambda name, desc: any(token in name for token in ("QUADSPI", "QSPI", "OCTOSPI", "OSPI")) or any(token in desc for token in ("QUADSPI", "QSPI", "OCTOSPI", "OSPI")))
    qspi_roles = _signal_role_names(pin_records, {
        "clk": lambda name, desc: any(token in f"{name} {desc}" for token in ("QUADSPI_CLK", "QSPI_CLK", "OCTOSPI_CLK", "OSPI_CLK")),
        "cs": lambda name, desc: any(token in f"{name} {desc}" for token in ("QUADSPI_NCS", "QSPI_NCS", "OCTOSPI_NCS", "OSPI_NCS", "QUADSPI_CS", "QSPI_CS", "OCTOSPI_CS", "OSPI_CS")),
        "dqs": lambda name, desc: any(token in f"{name} {desc}" for token in ("OCTOSPI_DQS", "OSPI_DQS", "QUADSPI_DQS", "QSPI_DQS")),
        **{f"io{idx}": (lambda idx: (lambda name, desc: any(token in f"{name} {desc}" for token in (f"QUADSPI_BK1_IO{idx}", f"QUADSPI_BK2_IO{idx}", f"QUADSPI_IO{idx}", f"QSPI_IO{idx}", f"OCTOSPI_IO{idx}", f"OSPI_IO{idx}", f"BK1_IO{idx}", f"BK2_IO{idx}"))))(idx) for idx in range(8)},
    })
    sdmmc_signals = _signal_groups(pin_records, lambda name, desc: any(token in name for token in ("SDMMC", "SDIO")) or any(token in desc for token in ("SDMMC", "SDIO")))
    sdmmc_roles = _signal_role_names(pin_records, {
        "ck": lambda name, desc: any(token in f"{name} {desc}" for token in ("SDMMC_CK", "SDIO_CK")),
        "cmd": lambda name, desc: any(token in f"{name} {desc}" for token in ("SDMMC_CMD", "SDIO_CMD")),
        **{f"d{idx}": (lambda idx: (lambda name, desc: any(token in f"{name} {desc}" for token in (f"SDMMC_D{idx}", f"SDIO_D{idx}"))))(idx) for idx in range(8)},
    })

    blocks = {}
    if debug_signals:
        interfaces = []
        debug_names = {item["name"].upper() for item in debug_signals}
        if any(token in " ".join(debug_names) for token in ("SWDIO", "SWCLK")):
            interfaces.append("SWD")
        if any(token in " ".join(debug_names) for token in ("JTMS", "JTCK", "JTDI", "JTDO")):
            interfaces.append("JTAG")
        if any(token in " ".join(debug_names) for token in ("SWO", "TRACESWO")):
            interfaces.append("TRACE")
        blocks["debug_access"] = {
            "class": "debug_access",
            "interfaces": interfaces,
            "signal_names": [item["name"] for item in debug_signals],
            "source": "pin_inference",
        }
    if boot_signals:
        blocks["boot_configuration"] = {
            "class": "boot_configuration",
            "signal_names": [item["name"] for item in boot_signals],
            "source": "pin_inference",
        }
    if hse_signals or lse_signals:
        blocks["clocking"] = {
            "class": "clocking",
            "external_sources": {
                "hse": [item["name"] for item in hse_signals],
                "lse": [item["name"] for item in lse_signals],
            },
            "source": "pin_inference",
        }
    if usb_signals or usb_roles:
        blocks["usb_interface"] = {
            "class": "interface",
            "protocols": ["USB 2.0"],
            "signal_names": _merge_signal_names(usb_signals, usb_roles),
            "signal_roles": usb_roles,
            "source": "pin_inference",
        }
    if eth_signals or eth_roles:
        blocks["ethernet_interface"] = {
            "class": "interface",
            "protocols": ["Ethernet MAC"],
            "signal_names": _merge_signal_names(eth_signals, eth_roles),
            "signal_roles": eth_roles,
            "source": "pin_inference",
        }
    if can_signals or can_roles:
        blocks["can_interface"] = {
            "class": "interface",
            "protocols": ["CAN", "FDCAN"],
            "signal_names": _merge_signal_names(can_signals, can_roles),
            "signal_roles": can_roles,
            "source": "pin_inference",
        }
    if qspi_signals or qspi_roles:
        blocks["serial_memory_interface"] = {
            "class": "interface",
            "protocols": ["QSPI", "OctoSPI"],
            "signal_names": _merge_signal_names(qspi_signals, qspi_roles),
            "signal_roles": qspi_roles,
            "source": "pin_inference",
        }
    if sdmmc_signals or sdmmc_roles:
        blocks["storage_interface"] = {
            "class": "interface",
            "protocols": ["SDMMC", "SDIO"],
            "signal_names": _merge_signal_names(sdmmc_signals, sdmmc_roles),
            "signal_roles": sdmmc_roles,
            "source": "pin_inference",
        }
    if description and "DUAL" in description.upper() and "CORTEX-M7" in description.upper() and "CORTEX-M4" in description.upper():
        blocks["compute_topology"] = {
            "class": "compute",
            "topology": "dual_core",
            "cores": ["Cortex-M7", "Cortex-M4"],
            "source": "description_inference",
        }
    return blocks


def _infer_normal_ic_constraint_blocks(capability_blocks: dict) -> dict:
    blocks = {}
    debug = capability_blocks.get("debug_access")
    if debug:
        blocks["debug_access"] = {
            "class": "debug_access",
            "required_signals": debug.get("signal_names", []),
            "recommended_connector": "SWD" if "SWD" in debug.get("interfaces", []) else "JTAG",
            "source": debug.get("source"),
        }
    boot = capability_blocks.get("boot_configuration")
    if boot:
        blocks["boot_configuration"] = {
            "class": "boot_configuration",
            "strap_signals": boot.get("signal_names", []),
            "review_required": True,
            "source": boot.get("source"),
        }
    clocking = capability_blocks.get("clocking")
    if clocking:
        blocks["clocking"] = {
            "class": "clocking",
            "domains": clocking.get("external_sources", {}),
            "review_required": True,
            "source": clocking.get("source"),
        }
    usb = capability_blocks.get("usb_interface")
    if usb:
        usb_roles = usb.get("signal_roles", {}) or {}
        dp_dm_group = _role_subset(usb_roles, "dp", "dm")
        blocks["usb_interface"] = {
            "class": "interface",
            "required_signal_groups": [dp_dm_group] if dp_dm_group else [],
            "vbus_related_signals": _role_subset(usb_roles, "vbus", "usb_supply"),
            "present_signal_roles": sorted(usb_roles),
            "review_required": True,
            "review_items": [
                "Freeze USB role, connector type, and VBUS policy before schematic sign-off.",
                "Verify DP/DM routing, ESD placement, and supply/domain wiring for the selected USB instance.",
            ],
            "source": usb.get("source"),
        }
    ethernet = capability_blocks.get("ethernet_interface")
    if ethernet:
        ethernet_roles = ethernet.get("signal_roles", {}) or {}
        blocks["ethernet_interface"] = {
            "class": "interface",
            "management_signals": _role_subset(ethernet_roles, "mdio", "mdc"),
            "clock_signals": _role_subset(ethernet_roles, "ref_clk"),
            "data_signals": _role_subset(ethernet_roles, "tx", "rx"),
            "present_signal_roles": sorted(ethernet_roles),
            "review_required": True,
            "review_items": [
                "Freeze MAC-to-PHY mode and reference clock source/direction before schematic sign-off.",
                "Review PHY reset, strap pins, and management bus accessibility.",
            ],
            "source": ethernet.get("source"),
        }
    can = capability_blocks.get("can_interface")
    if can:
        can_roles = can.get("signal_roles", {}) or {}
        tx_rx_group = _role_subset(can_roles, "tx", "rx")
        blocks["can_interface"] = {
            "class": "interface",
            "required_signal_groups": [tx_rx_group] if tx_rx_group else [],
            "present_signal_roles": sorted(can_roles),
            "external_component_required": "can_transceiver",
            "review_required": True,
            "review_items": [
                "Freeze MCU-to-transceiver channel assignment before schematic sign-off.",
                "Review CAN termination, standby, and bus protection around the external transceiver.",
            ],
            "source": can.get("source"),
        }
    serial_memory = capability_blocks.get("serial_memory_interface")
    if serial_memory:
        memory_roles = serial_memory.get("signal_roles", {}) or {}
        io_roles = [role for role in sorted(memory_roles) if role.startswith("io")]
        blocks["serial_memory_interface"] = {
            "class": "interface",
            "clock_signals": _role_subset(memory_roles, "clk"),
            "chip_select_signals": _role_subset(memory_roles, "cs"),
            "data_signals": _role_subset(memory_roles, *io_roles),
            "strobe_signals": _role_subset(memory_roles, "dqs"),
            "present_signal_roles": sorted(memory_roles),
            "review_required": True,
            "review_items": [
                "Freeze boot source, flash voltage, and bus width before schematic sign-off.",
                "Review pull states, reset interactions, and unused IO handling for the selected memory mode.",
            ],
            "source": serial_memory.get("source"),
        }
    storage = capability_blocks.get("storage_interface")
    if storage:
        storage_roles = storage.get("signal_roles", {}) or {}
        data_roles = [role for role in sorted(storage_roles) if role.startswith("d")]
        blocks["storage_interface"] = {
            "class": "interface",
            "clock_signals": _role_subset(storage_roles, "ck"),
            "command_signals": _role_subset(storage_roles, "cmd"),
            "data_signals": _role_subset(storage_roles, *data_roles),
            "present_signal_roles": sorted(storage_roles),
            "review_required": True,
            "review_items": [
                "Freeze bus width, IO voltage, and removable-vs-embedded media assumptions before schematic sign-off.",
                "Review pull-ups, card-detect/write-protect policy, and power sequencing for the selected storage interface.",
            ],
            "source": storage.get("source"),
        }
    return {key: value for key, value in blocks.items() if value}


def _config_signal_summary(pins: list[dict]) -> dict:
    names = [pin.get("name") for pin in pins if pin.get("name")]
    upper_names = [_safe_upper(name) for name in names]
    mode_signals = [name for name in names if any(token in _safe_upper(name) for token in ("MODE", "M0_", "M1_", "M2_", "CFGBVS", "PUDC", "BOOT"))]
    status_signals = [name for name in names if any(token in _safe_upper(name) for token in ("DONE", "READY", "INIT", "PROGRAM", "RECONFIG"))]
    jtag_signals = [name for name in names if any(token in _safe_upper(name) for token in ("TCK", "TMS", "TDI", "TDO", "JTAG"))]
    interfaces = []
    if jtag_signals:
        interfaces.append("JTAG")
    if any(token in " ".join(upper_names) for token in ("MSPI", "SSPI", "SPI")):
        interfaces.append("SPI")
    return {
        "mode_signals": sorted(set(mode_signals)),
        "status_signals": sorted(set(status_signals)),
        "jtag_signals": sorted(set(jtag_signals)),
        "interfaces": interfaces,
    }


def _gt_pair_counts(diff_pairs: list[dict]) -> dict:
    counts = {"rx": 0, "tx": 0, "refclk": 0}
    for pair in diff_pairs:
        pair_type = _safe_upper(pair.get("type"))
        if pair_type in ("SERDES_RX", "GT_RX"):
            counts["rx"] += 1
        elif pair_type in ("SERDES_TX", "GT_TX"):
            counts["tx"] += 1
        elif pair_type in ("SERDES_REFCLK", "GT_REFCLK", "REFCLK"):
            counts["refclk"] += 1
    return counts


def _normalize_protocol_refclk_profiles(protocols: list[str] | None) -> dict:
    profiles = {}
    for protocol in protocols or []:
        if protocol in ("PCIe Gen1", "PCIe Gen2", "PCIe 3.0", "PCIe 4.0"):
            profiles[protocol] = {
                "frequencies_mhz": [100.0],
                "source": "protocol_standard",
                "note": "PCI Express reference clocks are typically implemented as 100 MHz differential HCSL or translated equivalents.",
            }
        elif protocol in ("SGMII", "1000BASE-X"):
            profiles[protocol] = {
                "frequencies_mhz": [125.0],
                "source": "protocol_standard",
                "note": "1G serial Ethernet PHY-side links commonly use a 125 MHz differential reference clock.",
            }
        elif protocol in ("XAUI", "10GBASE-R", "10G Ethernet"):
            profiles[protocol] = {
                "frequencies_mhz": [156.25],
                "source": "protocol_standard",
                "note": "10G serial Ethernet families commonly use a 156.25 MHz differential reference clock.",
            }
    return profiles


def _load_gowin_family_design_guide(device: str, package: str, pinout_data: dict, gowin_dc: dict | None = None) -> dict:
    return load_gowin_design_guide_bundle(
        device=device,
        package=package,
        pinout_data=pinout_data,
        guide_path=resolve_gowin_design_guide_source_path(device),
        gowin_dc=gowin_dc,
    )


INTEL_AGILEX5_OVERVIEW_SOURCE = {
    "source": "agilex5_device_overview_762191_2024_09_06",
    "source_url": "https://drive.google.com/file/d/1c1UnPU9rQ8xAidwLzByDD5NbjErAE8Sa/view?usp=drivesdk",
}

INTEL_AGILEX5_PART_DECODER_SOURCE = {
    "source": "agilex5_part_number_decoder_762191_2024_09_06",
    "source_url": "https://drive.google.com/file/d/1c1UnPU9rQ8xAidwLzByDD5NbjErAE8Sa/view?usp=drivesdk",
}

INTEL_AGILEX5_DEVICE_PROFILES = {
    "A5E013B": {
        "device_group": "B",
        "logic_elements": 138060,
        "adaptive_logic_modules": 46800,
        "m20k_count": 358,
        "m20k_mbit": 6.99,
        "mlab_count": 2340,
        "mlab_mbit": 1.43,
        "dsp_count": 376,
        "int8_tops": 4.93,
        "hvio_count": 200,
        "hsio_count": 192,
        "hps_io_count": 48,
        "io_pll_count": 4,
        "fabric_feeding_io_pll_count": 8,
        "lvds_pairs_1v3_1p6gbps": 96,
        "memory_interface_x32_count": 2,
        "mipi_dphy_interface_count": 14,
        "transceiver_channel_count": 4,
        "pcie4_x4_instance_count": 1,
        "gigabit_ethernet_mac_pcs_count": 1,
        "transceiver_max_rate_gbps": 17.16,
        "memory_standards": ["DDR4", "LPDDR4", "LPDDR5"],
        "ethernet_protocols": ["10G Ethernet"],
    },
    "A5E052A": {
        "device_group": "A",
        "logic_elements": 523920,
        "adaptive_logic_modules": 177600,
        "m20k_count": 1288,
        "m20k_mbit": 25.16,
        "mlab_count": 8440,
        "mlab_mbit": 5.15,
        "dsp_count": 1352,
        "int8_tops": 20.78,
        "hvio_count": 120,
        "hsio_count": 384,
        "hps_io_count": 48,
        "io_pll_count": 8,
        "fabric_feeding_io_pll_count": 13,
        "lvds_pairs_1v3_1p6gbps": 192,
        "memory_interface_x32_count": 4,
        "mipi_dphy_interface_count": 28,
        "transceiver_channel_count": 24,
        "pcie4_x4_instance_count": 6,
        "gigabit_ethernet_mac_pcs_count": 4,
        "transceiver_max_rate_gbps": 28.1,
        "memory_standards": ["DDR4", "DDR5", "LPDDR4", "LPDDR5"],
        "ethernet_protocols": ["10G Ethernet", "25G Ethernet"],
    },
}

INTEL_AGILEX5_VARIANTS = {
    "A": {"device_role": "FPGA", "hps": "none", "transceiver": False, "crypto": False},
    "B": {"device_role": "FPGA SoC", "hps": "quad", "transceiver": False, "crypto": True},
    "C": {"device_role": "FPGA", "hps": "none", "transceiver": True, "crypto": False},
    "D": {"device_role": "FPGA SoC", "hps": "quad", "transceiver": True, "crypto": True},
    "E": {"device_role": "FPGA SoC", "hps": "dual", "transceiver": False, "crypto": False},
    "G": {"device_role": "FPGA", "hps": "none", "transceiver": False, "crypto": True},
}


def _intel_agilex5_base_device(device: str) -> str | None:
    match = re.match(r"^(A5E)[A-Z](\d{3}[AB])$", _safe_upper(device))
    if not match:
        return None
    return f"{match.group(1)}{match.group(2)}"


def _intel_agilex5_variant(device: str) -> dict:
    match = re.match(r"^A5E([A-Z])\d{3}[AB]$", _safe_upper(device))
    if not match:
        return {}
    return {"variant_code": match.group(1), **INTEL_AGILEX5_VARIANTS.get(match.group(1), {})}


def _gowin_family_series(device: str) -> tuple[str | None, str | None]:
    device_upper = _safe_upper(device)
    if device_upper.startswith("GW5AR"):
        return "Arora V", "Arora VR"
    if device_upper.startswith("GW5AS"):
        return "Arora V", "Arora VS"
    if device_upper.startswith("GW5AT"):
        return "Arora V", "Arora VT"
    if device_upper.startswith("GW5A"):
        return "Arora V", "Arora V"
    return None, None


def _amd_family_series(device: str, description: str | None) -> tuple[str | None, str | None]:
    device_upper = _safe_upper(device)
    desc_upper = _safe_upper(description)
    if device_upper.startswith("XCKU") or "KINTEX ULTRASCALE+" in desc_upper:
        return "Kintex UltraScale+", "Kintex UltraScale+"
    if device_upper.startswith("XCAU") or "ARTIX ULTRASCALE+" in desc_upper:
        return "Artix UltraScale+", "Artix UltraScale+"
    return None, None


def _lattice_series(family: str | None, device: str) -> str | None:
    family_upper = _safe_upper(family)
    device_upper = _safe_upper(device)
    if family_upper in ("ECP5", "CROSSLINK-NX"):
        return family
    if device_upper.startswith("ECP5"):
        return "ECP5"
    if device_upper.startswith("LIFCL"):
        return "CrossLink-NX"
    return None


def _infer_fpga_device_identity(manufacturer: str, pinout_data: dict, description: str | None = None) -> dict:
    device = pinout_data.get("device")
    package = pinout_data.get("package")
    family = pinout_data.get("_family")
    series = pinout_data.get("_series")
    base_device = pinout_data.get("_base_device") or device

    if manufacturer == "Gowin":
        inferred_family, inferred_series = _gowin_family_series(device or "")
        family = family or inferred_family
        series = series or inferred_series
    elif manufacturer == "AMD":
        inferred_family, inferred_series = _amd_family_series(device or "", description)
        family = family or inferred_family
        series = series or inferred_series
    elif manufacturer == "Lattice":
        if not family:
            if _safe_upper(device).startswith("ECP5"):
                family = "ECP5"
            elif _safe_upper(device).startswith("LIFCL"):
                family = "CrossLink-NX"
        series = series or _lattice_series(family, device or "")
    elif manufacturer == "Intel/Altera":
        family = family or "Agilex 5"
        series = series or "E-Series"
        base_device = pinout_data.get("_base_device") or _intel_agilex5_base_device(device or "") or device

    return {
        "vendor": manufacturer,
        "family": family,
        "series": series,
        "base_device": base_device,
        "device": device,
        "package": package,
    }


def _generic_fpga_source_traceability(pinout_data: dict) -> dict:
    package_pinout = {
        "source_file": pinout_data.get("source_file"),
        "source_document_id": pinout_data.get("source_document_id"),
        "source_url": pinout_data.get("source_url"),
        "source_index_url": pinout_data.get("source_index_url"),
        "source_version": pinout_data.get("source_version"),
        "source_status": pinout_data.get("source_status"),
        "source_revision_note": pinout_data.get("source_revision_note"),
    }
    package_pinout = {key: value for key, value in package_pinout.items() if value is not None}
    if not package_pinout:
        return {}
    return {"package_pinout": package_pinout}


def _fpga_family_high_speed_metadata(vendor: str, device: str, family: str | None, hs_serial: dict) -> dict:
    family_upper = _safe_upper(family)
    device_upper = _safe_upper(device)
    if vendor == "AMD" and device_upper.startswith("XCKU"):
        lane_pairs = min(hs_serial.get("rx_lane_pairs") or 0, hs_serial.get("tx_lane_pairs") or 0)
        return {
            "transceiver_type": "GTY",
            "supported_protocols": ["PCIe 3.0", "PCIe 4.0", "SGMII", "1000BASE-X", "XAUI", "10GBASE-R"],
            "protocol_matrix": {
                "PCIe 3.0": {"lane_widths": [width for width in (1, 2, 4, 8, 16) if width <= lane_pairs], "hardcore": True},
                "PCIe 4.0": {"lane_widths": [width for width in (1, 2, 4, 8) if width <= lane_pairs], "hardcore": True},
                "SGMII": {"lane_widths": [1], "hardcore": False},
                "1000BASE-X": {"lane_widths": [1], "hardcore": False},
                "XAUI": {"lane_widths": [4] if lane_pairs >= 4 else [], "hardcore": False},
                "10GBASE-R": {"lane_widths": [1], "hardcore": False},
            },
            "source": "amd_high_speed_serial_overview",
            "source_url": "https://www.amd.com/en/products/adaptive-socs-and-fpgas/technologies/high-speed-serial.html",
            "review_note": "Exact AMD high-speed IP enablement still depends on device speed grade, selected IP core, and quad placement; freeze the protocol before schematic sign-off.",
        }
    if vendor == "Lattice" and (family_upper == "CROSSLINKNX" or device_upper.startswith("LIFCL")):
        return {
            "supported_protocols": ["SGMII", "1000BASE-X", "PCIe Gen1", "PCIe Gen2"],
            "protocol_matrix": {
                "SGMII": {"lane_widths": [1], "hardcore": False},
                "1000BASE-X": {"lane_widths": [1], "hardcore": False},
                "PCIe Gen1": {"lane_widths": [1], "hardcore": False},
                "PCIe Gen2": {"lane_widths": [1], "hardcore": False},
            },
            "source": "lattice_crosslink_nx_product_page",
            "source_url": "https://www.latticesemi.com/en/Products/FPGAandCPLD/CrossLink-NX",
            "review_note": "CrossLink-NX exports only the single-channel SerDes topology here; protocol selection must still be matched against the chosen Lattice IP/reference design.",
        }
    if vendor == "Intel/Altera" and family_upper == "AGILEX 5":
        base_device = _intel_agilex5_base_device(device)
        profile = INTEL_AGILEX5_DEVICE_PROFILES.get(base_device or "")
        variant = _intel_agilex5_variant(device)
        if profile and variant.get("transceiver"):
            supported_protocols = ["PCIe 4.0", *profile.get("ethernet_protocols", []), "custom"]
            protocol_matrix = {
                "PCIe 4.0": {"lane_widths": [1, 2, 4], "hardcore": True},
                "custom": {"lane_widths": [1, 2, 4], "hardcore": False},
            }
            for protocol in profile.get("ethernet_protocols", []):
                protocol_matrix[protocol] = {"lane_widths": [1], "hardcore": False}
            return {
                "supported_protocols": supported_protocols,
                "protocol_matrix": protocol_matrix,
                "max_rate_gbps": profile["transceiver_max_rate_gbps"],
                "pcie4_x4_instance_count": profile["pcie4_x4_instance_count"],
                "gigabit_ethernet_mac_pcs_count": profile["gigabit_ethernet_mac_pcs_count"],
                **INTEL_AGILEX5_OVERVIEW_SOURCE,
                "review_note": "Agilex 5 transceiver protocol/IP enablement still depends on the selected ordering code, package migration limits, and design-specific quad usage.",
            }
    return {}


def _intel_agilex5_public_device_overlay(pinout_data: dict) -> dict:
    if _safe_upper(pinout_data.get("_family")) != "AGILEX 5":
        return {}

    device = _safe_upper(pinout_data.get("device"))
    base_device = _intel_agilex5_base_device(device)
    profile = INTEL_AGILEX5_DEVICE_PROFILES.get(base_device or "")
    variant = _intel_agilex5_variant(device)
    if not profile or not variant:
        return {}

    overlay = {
        "device_identity": {
            "vendor": "Intel/Altera",
            "family": pinout_data.get("_family"),
            "series": pinout_data.get("_series"),
            "base_device": base_device,
            "device": device,
            "package": pinout_data.get("package"),
        },
        "source_traceability": {
            "package_pinout": {
                "source_file": pinout_data.get("source_file"),
                "source_document_id": pinout_data.get("source_document_id"),
                "source_url": pinout_data.get("source_url"),
                "source_index_url": pinout_data.get("source_index_url"),
                "source_version": pinout_data.get("source_version"),
                "source_status": pinout_data.get("source_status"),
                "source_revision_note": pinout_data.get("source_revision_note"),
            },
            "device_capability": {
                **INTEL_AGILEX5_OVERVIEW_SOURCE,
                "scope": "device-level capability boundary",
            },
            "ordering_variant": {
                **INTEL_AGILEX5_PART_DECODER_SOURCE,
                "scope": "ordering-code role/features",
            },
        },
        "ordering_variant": {
            **variant,
            **INTEL_AGILEX5_PART_DECODER_SOURCE,
        },
        "device_role": variant["device_role"],
        "resources": {
            "logic_elements": profile["logic_elements"],
            "adaptive_logic_modules": profile["adaptive_logic_modules"],
            "m20k_count": profile["m20k_count"],
            "m20k_mbit": profile["m20k_mbit"],
            "mlab_count": profile["mlab_count"],
            "mlab_mbit": profile["mlab_mbit"],
            "dsp_count": profile["dsp_count"],
            "int8_tops": profile["int8_tops"],
        },
        "capability_blocks": {
            "device_role": {
                "class": "device_role",
                "device_role": variant["device_role"],
                **INTEL_AGILEX5_PART_DECODER_SOURCE,
            },
            "fabric_resources": {
                "class": "fpga_fabric",
                "logic_elements": profile["logic_elements"],
                "adaptive_logic_modules": profile["adaptive_logic_modules"],
                "m20k_count": profile["m20k_count"],
                "m20k_mbit": profile["m20k_mbit"],
                "mlab_count": profile["mlab_count"],
                "mlab_mbit": profile["mlab_mbit"],
                "dsp_count": profile["dsp_count"],
                "int8_tops": profile["int8_tops"],
                **INTEL_AGILEX5_OVERVIEW_SOURCE,
            },
            "io_resources": {
                "class": "io_resources",
                "hvio_count": profile["hvio_count"],
                "hsio_count": profile["hsio_count"],
                "hps_io_count": profile["hps_io_count"],
                "io_pll_count": profile["io_pll_count"],
                "fabric_feeding_io_pll_count": profile["fabric_feeding_io_pll_count"],
                "lvds_pairs_1v3_1p6gbps": profile["lvds_pairs_1v3_1p6gbps"],
                "mipi_dphy_interface_count": profile["mipi_dphy_interface_count"],
                **INTEL_AGILEX5_OVERVIEW_SOURCE,
            },
            "memory_interface": {
                "class": "memory_interface",
                "supported_standards": profile["memory_standards"],
                "x32_interface_count": profile["memory_interface_x32_count"],
                **INTEL_AGILEX5_OVERVIEW_SOURCE,
            },
        },
    }

    if variant.get("transceiver"):
        overlay["capability_blocks"]["high_speed_serial"] = {
            "class": "high_speed_serial",
            "transceiver_channel_count": profile["transceiver_channel_count"],
            "max_rate_gbps": profile["transceiver_max_rate_gbps"],
            "pcie4_x4_instance_count": profile["pcie4_x4_instance_count"],
            "gigabit_ethernet_mac_pcs_count": profile["gigabit_ethernet_mac_pcs_count"],
            "supported_protocols": ["PCIe 4.0", *profile.get("ethernet_protocols", []), "custom"],
            **INTEL_AGILEX5_OVERVIEW_SOURCE,
        }

    if variant.get("hps") and variant["hps"] != "none":
        overlay["capability_blocks"]["hard_processor"] = {
            "class": "hard_processor",
            "mode": variant["hps"],
            "cores": ["Arm Cortex-A76", "Arm Cortex-A55"],
            "cache": {
                "l3_mb": 2,
                "cortex_a76_l1_kb": 64,
                "cortex_a76_l2_kb": 256,
                "cortex_a55_l1_kb": 32,
                "cortex_a55_l2_kb": 128,
            },
            **INTEL_AGILEX5_OVERVIEW_SOURCE,
        }
    return overlay


def _infer_refclk_pairs_from_pins(pins: list[dict], existing_pairs: list[dict]) -> list[dict]:
    existing = {(pair.get("p_pin"), pair.get("n_pin")) for pair in existing_pairs}
    normalized_pin_by_name = {}
    for pin in pins:
        name = pin.get("name") or ""
        normalized_name = (name.split("/")[0]).strip()
        if normalized_name:
            normalized_pin_by_name[normalized_name] = pin
    inferred = []
    for pin in pins:
        raw_name = pin.get("name") or ""
        name = (raw_name.split("/")[0]).strip()
        upper = _safe_upper(name)
        comp_name = None
        pair_name = None
        if upper.endswith("REFCLKP"):
            comp_name = re.sub(r"REFCLKP$", "REFCLKN", name, flags=re.IGNORECASE)
            pair_name = re.sub(r"P$", "", name)
        elif re.search(r"REFCLKP_\d+$", upper):
            match = re.search(r"(.*)REFCLKP(_\d+)$", name, flags=re.IGNORECASE)
            if match:
                comp_name = f"{match.group(1)}REFCLKM{match.group(2)}"
                pair_name = f"{match.group(1)}REFCLK{match.group(2)}"
        if not comp_name:
            continue
        comp_pin = normalized_pin_by_name.get(comp_name)
        if not comp_pin:
            continue
        key = (pin.get("pin"), comp_pin.get("pin"))
        rev_key = (comp_pin.get("pin"), pin.get("pin"))
        if key in existing or rev_key in existing:
            continue
        inferred.append({
            "type": "REFCLK",
            "pair_name": pair_name,
            "p_pin": pin.get("pin"),
            "n_pin": comp_pin.get("pin"),
            "p_name": name,
            "n_name": comp_name,
            "bank": pin.get("bank") or comp_pin.get("bank"),
            "source": "pin_name_inference",
        })
    return inferred


def _collect_refclk_pairs(diff_pairs: list[dict], pins: list[dict]) -> list[dict]:
    refclk_pairs = []
    for pair in diff_pairs:
        pair_type = _safe_upper(pair.get("type"))
        if pair_type in ("SERDES_REFCLK", "GT_REFCLK", "REFCLK"):
            refclk_pairs.append({
                "pair_name": pair.get("pair_name"),
                "type": pair.get("type"),
                "p_pin": pair.get("p_pin"),
                "n_pin": pair.get("n_pin"),
                "p_name": pair.get("p_name"),
                "n_name": pair.get("n_name"),
                "bank": pair.get("bank"),
                "source": "diff_pair_export",
            })
    refclk_pairs.extend(_infer_refclk_pairs_from_pins(pins, refclk_pairs))
    return refclk_pairs


def _infer_hs_pair_topology(pair: dict) -> dict:
    pair_type = _safe_upper(pair.get("type"))
    pair_name = pair.get("pair_name") or ""
    p_name = pair.get("p_name") or ""
    upper_pair_name = _safe_upper(pair_name)
    upper_p_name = _safe_upper(p_name)
    bank = pair.get("bank")

    match = re.search(r"(Q\d+)_LN(\d+)_(RX|TX)", upper_p_name)
    if match:
        return {
            "group_id": match.group(1),
            "group_type": "serdes_quad",
            "lane_index": int(match.group(2)),
            "bank": bank or match.group(1),
        }
    match = re.search(r"REFCLK_(Q\d+)_C(\d+)", upper_pair_name)
    if match:
        return {
            "group_id": match.group(1),
            "group_type": "serdes_quad",
            "refclk_index": int(match.group(2)),
            "bank": bank or match.group(1),
        }
    match = re.search(r"(Q\d+)_REFCLK[PM]?_(\d+)", upper_p_name)
    if match:
        return {
            "group_id": match.group(1),
            "group_type": "serdes_quad",
            "refclk_index": int(match.group(2)),
            "bank": bank or match.group(1),
        }

    match = re.search(r"MGT(?:Y|H)?(?:RX|TX)P(\d+)_(\d+)$", upper_p_name)
    if match:
        return {
            "group_id": match.group(2),
            "group_type": "transceiver_quad",
            "lane_index": int(match.group(1)),
            "bank": bank or match.group(2),
        }
    match = re.search(r"MGTREFCLK(\d+)P_(\d+)$", upper_p_name)
    if match:
        return {
            "group_id": match.group(2),
            "group_type": "transceiver_quad",
            "refclk_index": int(match.group(1)),
            "bank": bank or match.group(2),
        }

    match = re.search(r"(SD\d+)_(RX|TX)D[PN]$", upper_p_name)
    if match:
        channel = match.group(1)
        channel_idx = re.search(r"\d+", channel)
        return {
            "group_id": channel,
            "group_type": "serdes_channel",
            "lane_index": int(channel_idx.group(0)) if channel_idx else None,
            "bank": bank,
        }
    if upper_p_name == "SD_REFCLKP" or upper_pair_name == "SD_REFCLK":
        return {
            "group_id": "SD",
            "group_type": "serdes_refclk_domain",
            "bank": bank,
        }

    if pair_type in ("GT_RX", "GT_TX", "SERDES_RX", "SERDES_TX") and bank:
        return {
            "group_id": str(bank),
            "group_type": "lane_bank",
            "bank": bank,
        }
    if pair_type in ("GT_REFCLK", "SERDES_REFCLK", "REFCLK") and bank:
        return {
            "group_id": str(bank),
            "group_type": "refclk_bank",
            "bank": bank,
        }
    return {}


def _candidate_group_ids(refclk_meta: dict, lane_groups: dict) -> list[str]:
    group_id = refclk_meta.get("group_id")
    if not group_id:
        return []
    if group_id in lane_groups:
        return [group_id]
    matches = sorted(group for group in lane_groups if group.startswith(group_id))
    if matches:
        return matches
    bank = refclk_meta.get("bank")
    if bank is not None:
        return sorted(group_id for group_id, group in lane_groups.items() if group.get("bank") == bank)
    return []


def _high_speed_topology(diff_pairs: list[dict], refclk_pairs: list[dict]) -> tuple[list[dict], list[dict]]:
    lane_groups = {}
    for pair in diff_pairs:
        pair_type = _safe_upper(pair.get("type"))
        if pair_type not in ("GT_RX", "GT_TX", "SERDES_RX", "SERDES_TX"):
            continue
        meta = _infer_hs_pair_topology(pair)
        group_id = meta.get("group_id")
        if not group_id:
            continue
        entry = lane_groups.setdefault(group_id, {
            "group_id": group_id,
            "group_type": meta.get("group_type"),
            "bank": meta.get("bank"),
            "rx_pair_names": [],
            "tx_pair_names": [],
            "lane_indices": [],
            "refclk_pair_names": [],
            "refclk_indices": [],
            "source": "pair_name_inference",
        })
        if pair_type in ("GT_RX", "SERDES_RX") and pair.get("pair_name"):
            entry["rx_pair_names"].append(pair.get("pair_name"))
        if pair_type in ("GT_TX", "SERDES_TX") and pair.get("pair_name"):
            entry["tx_pair_names"].append(pair.get("pair_name"))
        lane_index = meta.get("lane_index")
        if lane_index is not None:
            entry["lane_indices"].append(lane_index)

    enriched_refclk_pairs = []
    for pair in refclk_pairs:
        enriched = dict(pair)
        meta = _infer_hs_pair_topology(pair)
        if meta.get("group_id"):
            enriched["group_id"] = meta.get("group_id")
        if meta.get("refclk_index") is not None:
            enriched["refclk_index"] = meta.get("refclk_index")
        candidate_ids = _candidate_group_ids(meta, lane_groups)
        if candidate_ids:
            enriched["mapped_lane_groups"] = candidate_ids
        enriched_refclk_pairs.append(enriched)
        for group_id in candidate_ids:
            entry = lane_groups[group_id]
            if pair.get("pair_name"):
                entry["refclk_pair_names"].append(pair.get("pair_name"))
            refclk_index = meta.get("refclk_index")
            if refclk_index is not None:
                entry["refclk_indices"].append(refclk_index)

    lane_group_mappings = []
    for group_id in sorted(lane_groups):
        entry = dict(lane_groups[group_id])
        entry["rx_pair_names"] = sorted(set(entry["rx_pair_names"]))
        entry["tx_pair_names"] = sorted(set(entry["tx_pair_names"]))
        entry["lane_indices"] = sorted(set(entry["lane_indices"]))
        entry["refclk_pair_names"] = sorted(set(entry["refclk_pair_names"]))
        entry["refclk_indices"] = sorted(set(entry["refclk_indices"]))
        lane_group_mappings.append(entry)
    return enriched_refclk_pairs, lane_group_mappings


def _lane_group_protocol_candidates(lane_group_mappings: list[dict], protocol_matrix: dict | None) -> list[dict]:
    protocol_matrix = protocol_matrix or {}
    enriched = []
    for group in lane_group_mappings:
        entry = dict(group)
        max_lane_pairs = len(entry.get("lane_indices") or []) or min(len(entry.get("rx_pair_names") or []), len(entry.get("tx_pair_names") or [])) or max(len(entry.get("rx_pair_names") or []), len(entry.get("tx_pair_names") or []))
        entry["max_lane_pairs"] = max_lane_pairs
        protocol_lane_widths = {}
        candidate_protocols = []
        for protocol, meta in protocol_matrix.items():
            lane_widths = [width for width in (meta or {}).get("lane_widths", []) if isinstance(width, int) and width <= max_lane_pairs]
            if lane_widths:
                protocol_lane_widths[protocol] = lane_widths
                candidate_protocols.append(protocol)
        entry["candidate_protocols"] = candidate_protocols
        if protocol_lane_widths:
            entry["protocol_lane_widths"] = protocol_lane_widths
        entry["selection_required"] = bool(candidate_protocols)
        if candidate_protocols:
            entry["selection_note"] = "Freeze the protocol/IP assignment for this lane group and bind it to one of the mapped refclk pairs before schematic sign-off."
            entry.update(_protocol_bundle_context(candidate_protocols))
        enriched.append(entry)
    return enriched


def _refclk_pair_protocol_candidates(refclk_pairs: list[dict], lane_group_mappings: list[dict]) -> list[dict]:
    group_map = {entry.get("group_id"): entry for entry in lane_group_mappings}
    enriched = []
    for pair in refclk_pairs:
        entry = dict(pair)
        protocols = []
        protocol_lane_widths = {}
        for group_id in entry.get("mapped_lane_groups", []) or []:
            group = group_map.get(group_id, {})
            for protocol in group.get("candidate_protocols", []) or []:
                if protocol not in protocols:
                    protocols.append(protocol)
                widths = group.get("protocol_lane_widths", {}).get(protocol, [])
                if widths:
                    protocol_lane_widths.setdefault(protocol, [])
                    protocol_lane_widths[protocol] = sorted(set(protocol_lane_widths[protocol]) | set(widths))
        if protocols:
            entry["candidate_protocols"] = protocols
            entry.update(_protocol_bundle_context(protocols))
        if protocol_lane_widths:
            entry["protocol_lane_widths"] = protocol_lane_widths
        enriched.append(entry)
    return enriched


def _protocol_bundle_context(protocols: list[str]) -> dict:
    protocols = [protocol for protocol in protocols or [] if protocol]
    bundle_tags = []
    use_case_tags = []
    scenario_candidates = []

    def add_unique(target: list[str], *values: str) -> None:
        for value in values:
            if value and value not in target:
                target.append(value)

    if protocols:
        add_unique(bundle_tags, "SerDes", "clock")
        add_unique(use_case_tags, "high_speed_link")
        add_unique(scenario_candidates, "high_speed_link_bridge")

    pcie_protocols = [p for p in protocols if p.startswith("PCIe")]
    ethernet_protocols = [p for p in protocols if p in ("SGMII", "1000BASE-X", "XAUI", "10GBASE-R", "10G Ethernet")]
    custom_protocols = [p for p in protocols if p == "custom"]

    if pcie_protocols:
        add_unique(bundle_tags, "PCIe")
        add_unique(use_case_tags, "pcie_link")
    if ethernet_protocols:
        add_unique(bundle_tags, "Ethernet")
        add_unique(use_case_tags, "ethernet_link")
    if custom_protocols:
        add_unique(use_case_tags, "custom_serdes")

    return {
        "bundle_tags": bundle_tags,
        "use_case_tags": use_case_tags,
        "bundle_scenario_candidates": scenario_candidates,
    }


def _package_rate_note(vendor: str, package: str, hs_serial: dict) -> str | None:
    if vendor == "Gowin" and hs_serial.get("package_rate_ceiling_gbps") is not None:
        ceiling = hs_serial.get("package_rate_ceiling_gbps")
        return f"Package-level transceiver ceiling is {ceiling} Gbps per official Gowin product page."
    return None


def _generic_fpga_capability_blocks(pinout_data: dict, vendor: str, device: str, package: str, diff_pairs: list[dict]) -> dict:
    summary = pinout_data.get("summary", {}) if isinstance(pinout_data.get("summary"), dict) else {}
    by_function = summary.get("by_function", {}) if isinstance(summary, dict) else {}
    pins = pinout_data.get("pins", [])
    family = pinout_data.get("_family")
    config_summary = _config_signal_summary(pins)
    gt_counts = _gt_pair_counts(diff_pairs)
    blocks = {}

    if any(config_summary.values()):
        blocks["configuration"] = {
            "class": "boot_configuration",
            "interfaces": config_summary["interfaces"],
            "mode_signals": config_summary["mode_signals"],
            "status_signals": config_summary["status_signals"],
            "jtag_signals": config_summary["jtag_signals"],
            "source": "pinout_inference",
        }

    if any(gt_counts.values()):
        quad_count = gt_counts["rx"] // 4 if gt_counts["rx"] and gt_counts["rx"] % 4 == 0 else None
        blocks["high_speed_serial"] = {
            "class": "high_speed_serial",
            "rx_lane_pairs": gt_counts["rx"],
            "tx_lane_pairs": gt_counts["tx"],
            "refclk_pair_count": gt_counts["refclk"],
            "quad_count": quad_count,
            "source": "pinout_inference",
        }
        blocks["high_speed_serial"].update(_fpga_family_high_speed_metadata(vendor, device, family, blocks["high_speed_serial"]))

    if by_function.get("MIPI", 0) > 0:
        blocks["mipi_phy"] = {
            "class": "mipi_phy",
            "signal_count": by_function.get("MIPI", 0),
            "source": "pinout_inference",
        }

    if vendor == "Gowin":
        gowin_ip = _infer_gowin_ip_blocks(pinout_data)
        if gowin_ip:
            if "mipi" in gowin_ip:
                blocks["mipi_phy"] = {
                    "class": "mipi_phy",
                    **gowin_ip["mipi"],
                }
            if "serdes" in gowin_ip:
                blocks["high_speed_serial"] = {
                    "class": "high_speed_serial",
                    **gowin_ip["serdes"],
                }
            blocks["legacy_ip_blocks"] = gowin_ip

    return blocks


def _generic_fpga_constraint_blocks(pinout_data: dict, capability_blocks: dict, diff_pairs: list[dict]) -> dict:
    blocks = {}
    configuration = capability_blocks.get("configuration")
    if configuration:
        blocks["configuration_boot"] = {
            "class": "boot_configuration",
            "mode_signals": configuration.get("mode_signals", []),
            "status_signals": configuration.get("status_signals", []),
            "jtag_signals": configuration.get("jtag_signals", []),
            "source": configuration.get("source"),
        }

    hs_serial = capability_blocks.get("high_speed_serial")
    refclk_pairs = _collect_refclk_pairs(diff_pairs, pinout_data.get("pins", []))
    if hs_serial and refclk_pairs:
        protocol_profiles = _normalize_protocol_refclk_profiles(hs_serial.get("supported_protocols") or [])
        protocol_candidates = sorted({freq for profile in protocol_profiles.values() for freq in profile.get("frequencies_mhz", [])})
        enriched_refclk_pairs, lane_group_mappings = _high_speed_topology(diff_pairs, refclk_pairs)
        lane_group_mappings = _lane_group_protocol_candidates(lane_group_mappings, hs_serial.get("protocol_matrix"))
        enriched_refclk_pairs = _refclk_pair_protocol_candidates(enriched_refclk_pairs, lane_group_mappings)
        blocks["refclk_requirements"] = {
            "class": "clocking",
            "required": True,
            "selection_required": True,
            "refclk_pair_count": len(enriched_refclk_pairs),
            "refclk_pairs": enriched_refclk_pairs,
            "review_required": True,
            "source": hs_serial.get("source"),
            "source_url": hs_serial.get("source_url"),
            "protocol_refclk_profiles": protocol_profiles,
            "common_review_candidates_mhz": protocol_candidates,
            "selection_note": "Refclk frequency, clock standard, jitter budget, and pair-to-quad mapping must be frozen against the selected protocol before schematic sign-off.",
        }
        if lane_group_mappings:
            blocks["refclk_requirements"]["lane_group_mappings"] = lane_group_mappings
        if hs_serial.get("protocol_matrix"):
            blocks["refclk_requirements"]["protocol_matrix"] = hs_serial.get("protocol_matrix")
        if hs_serial.get("review_note"):
            blocks["refclk_requirements"]["review_note"] = hs_serial.get("review_note")
        if hs_serial.get("package_rate_ceiling_gbps") is not None:
            blocks["refclk_requirements"]["package_rate_ceiling_gbps"] = hs_serial.get("package_rate_ceiling_gbps")
        package_note = _package_rate_note(pinout_data.get("_vendor", ""), pinout_data.get("package", ""), hs_serial)
        if package_note:
            blocks["refclk_requirements"]["package_rate_note"] = package_note

    mipi = capability_blocks.get("mipi_phy")
    if mipi:
        blocks["mipi_phy"] = {
            "class": "clocking",
            "review_required": bool(mipi.get("present", True)),
            "directions": mipi.get("directions", []),
            "source": mipi.get("source"),
        }
    return blocks


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
        "I/O": "IO", "i/o": "IO", "IO": "IO", "DIO": "IO", "MIPI": "IO", "HPS_IO": "IO",
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
            "lane_widths": [width for width in lane_widths if width <= (8 if transceiver_count >= 8 else 4)],
        },
    }


def _gowin_package_listing_overlay(device: str, package: str) -> dict:
    package_token = _normalize_package_token(package)
    listings = {
        "GW5AT-15": {
            "source": "gowin_product_detail_72",
            "source_url": "https://www.gowinsemi.com/en/product/detail/72/",
            "current_public_packages": ["CS130F", "MG132"],
        },
        "GW5AT-75": {
            "source": "gowin_product_detail_72",
            "source_url": "https://www.gowinsemi.com/en/product/detail/72/",
            "current_public_packages": ["UG484"],
        },
        "GW5AT-138": {
            "source": "gowin_product_detail_72",
            "source_url": "https://www.gowinsemi.com/en/product/detail/72/",
            "current_public_packages": ["FPG676A", "PG484A", "PG484", "PG676A", "UG324A"],
        },
        "GW5A-25": {
            "source": "gowin_product_detail_77",
            "source_url": "https://www.gowinsemi.com/en/product/detail/77/",
            "current_public_packages": ["UG324"],
        },
        "GW5A-60": {
            "source": "gowin_product_detail_75",
            "source_url": "https://www.gowinsemi.com/en/product/detail/75/",
            "current_public_packages": ["UG324S", "UG324A"],
        },
        "GW5A-138": {
            "source": "gowin_product_detail_76",
            "source_url": "https://www.gowinsemi.com/en/product/detail/76/",
            "current_public_packages": ["UG324A"],
        },
    }
    profile = listings.get(device)
    if not profile:
        return {}
    current_public_packages = profile["current_public_packages"]
    listed = package_token in current_public_packages
    overlay = {
        "package_listing_status": {
            "listed_on_current_product_page": listed,
            "current_public_packages": current_public_packages,
            "source": profile["source"],
            "source_url": profile["source_url"],
        }
    }
    if device == "GW5AT-15" and package_token == "MG132":
        overlay["link_reach_guidance"] = {
            "rate_threshold_gbps": 8.0,
            "recommended_scope_above_threshold": "on_board_only",
            "discouraged_scopes_above_threshold": ["backplane", "long_reach_cable"],
            "note": "For rates above 8 Gbps, official current product page guidance limits MG132 to board-level interconnect.",
            "source": profile["source"],
            "source_url": profile["source_url"],
        }
    return overlay


def _gowin_public_device_overlay(pinout_data: dict) -> dict:
    device = pinout_data.get("device", "")
    package = pinout_data.get("package", "")
    package_token = _normalize_package_token(package)

    profiles = {
        "GW5AR-25": {
            "source": "gowin_product_detail_79",
            "source_url": "https://www.gowinsemi.com/en/product/detail/79/",
            "device_role": "FPGA",
            "resources": {
                "lut4": 23040,
                "bsram_kbit": 1008,
                "dsp": 28,
                "pll": 6,
                "adc": 1,
                "user_io": 178,
            },
            "embedded_memories": {
                "embedded_psram_mbit": 64,
            },
            "ip_blocks": {
                "mipi": {
                    "present": True,
                    "phy_types": ["D-PHY"],
                    "directions": ["RX", "TX"],
                    "dphy": {
                        "max_data_lanes": 4,
                        "max_clock_lanes": 1,
                    },
                }
            },
        },
        "GW5AS-25": {
            "source": "gowin_product_detail_78",
            "source_url": "https://www.gowinsemi.com/en/product/detail/78/",
            "device_role": "FPGA SoC",
            "resources": {
                "lut4": 41472,
                "bsram_kbit": 1512,
                "dsp": 178,
                "pll": 12,
                "adc": {
                    "fpga": 1,
                    "cortex_m4": 3,
                    "total": 4,
                },
            },
            "embedded_memories": {
                "embedded_psram_mbit": 64,
            },
            "hard_processor": {
                "core": "Cortex-M4",
            },
            "ip_blocks": {
                "mipi": {
                    "present": True,
                    "phy_types": ["D-PHY"],
                    "directions": ["RX", "TX"],
                    "dphy": {
                        "max_data_lanes": 4,
                        "max_clock_lanes": 1,
                    },
                }
            },
        },
        "GW5A-25": {
            "source": "gowin_product_detail_77",
            "source_url": "https://www.gowinsemi.com/en/product/detail/77/",
            "device_role": "FPGA",
            "resources": {
                "lut4": 23040,
                "bsram_kbit": 1008,
                "dsp": 28,
                "pll": 6,
                "adc": 1,
            },
            "memory_interface": {
                "ddr3_mbps": 800,
            },
            "ip_blocks": {
                "mipi": {
                    "present": True,
                    "phy_types": ["D-PHY"],
                    "directions": ["RX", "TX"],
                    "dphy": {
                        "max_data_lanes": 4,
                        "max_clock_lanes": 1,
                        "max_rate_gbps_per_lane": 2.5,
                    },
                }
            },
            "package_profiles": {
                "UG324": {"user_io": 206, "true_lvds_pairs": 100},
            },
        },
        "GW5A-60": {
            "source": "gowin_product_detail_75",
            "source_url": "https://www.gowinsemi.com/en/product/detail/75/",
            "device_role": "FPGA",
            "resources": {
                "lut4": 59904,
                "bsram_kbit": 2124,
                "dsp": 118,
                "pll": 8,
                "adc": 2,
                "gpio_bank_count": 11,
                "max_gpio": 320,
            },
            "memory_interface": {
                "ddr3_mbps": 1100,
            },
            "ip_blocks": {
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
                        "max_symbol_rate_gsps": 2.5,
                    },
                }
            },
            "package_profiles": {
                "UG324S": {"user_io": 226, "true_lvds_pairs": 110},
                "UG324A": {"user_io": 222, "true_lvds_pairs": 106},
            },
        },
        "GW5A-138": {
            "source": "gowin_product_detail_76",
            "source_url": "https://www.gowinsemi.com/en/product/detail/76/",
            "device_role": "FPGA SoC",
            "resources": {
                "lut4": 138240,
                "bsram_kbit": 6012,
                "dsp": 298,
                "pll": 20,
                "adc": 3,
                "max_gpio": 398,
            },
            "memory_interface": {
                "ddr3_mbps": 1600,
            },
            "hard_processor": {
                "core": "RiscV AE350_SOC",
            },
            "ip_blocks": {
                "mipi": {
                    "present": True,
                    "phy_types": ["D-PHY"],
                    "directions": ["RX"],
                    "dphy": {
                        "max_data_lanes": 8,
                        "max_clock_lanes": 2,
                        "max_rate_gbps_per_lane": 2.5,
                    },
                }
            },
            "package_profiles": {
                "UG324A": {"user_io": 222, "true_lvds_pairs": 106},
            },
        },
    }

    profile = profiles.get(device)
    if not profile:
        return {}

    source = profile["source"]
    source_url = profile["source_url"]
    resources = dict(profile.get("resources", {}))
    package_profile = profile.get("package_profiles", {}).get(package_token)
    if package_profile:
        resources.update(package_profile)

    overlay = {
        "device_role": profile["device_role"],
        "resources": resources,
        "capability_blocks": {
            "device_role": {
                "class": "device_role",
                "device_role": profile["device_role"],
                "source": source,
                "source_url": source_url,
            },
            "fabric_resources": {
                "class": "fpga_fabric",
                **resources,
                "source": source,
                "source_url": source_url,
            },
        },
    }

    if profile.get("embedded_memories"):
        overlay["embedded_memories"] = profile["embedded_memories"]
        overlay["capability_blocks"]["embedded_memory"] = {
            "class": "embedded_memory",
            **profile["embedded_memories"],
            "source": source,
            "source_url": source_url,
        }

    if profile.get("memory_interface"):
        overlay["capability_blocks"]["memory_interface"] = {
            "class": "memory_interface",
            **profile["memory_interface"],
            "source": source,
            "source_url": source_url,
        }

    if profile.get("hard_processor"):
        overlay["capability_blocks"]["hard_processor"] = {
            "class": "hard_processor",
            **profile["hard_processor"],
            "source": source,
            "source_url": source_url,
        }

    if profile.get("ip_blocks"):
        overlay["ip_blocks"] = profile["ip_blocks"]
        if "mipi" in profile["ip_blocks"]:
            overlay["capability_blocks"]["mipi_phy"] = {
                "class": "mipi_phy",
                **profile["ip_blocks"]["mipi"],
                "source": source,
                "source_url": source_url,
            }

    return overlay


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
                "PG484F": {
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
    package_overlay = _gowin_package_listing_overlay(device, package)
    if package_overlay:
        result["serdes"] = _deep_merge_dict(result["serdes"], package_overlay)
    return result


def export_fpga(dc_data: dict, pinout_data: dict, gowin_dc: dict = None, lattice_dc: dict = None) -> dict:
    """Combine FPGA DC datasheet + pinout into sch-review format.

    dc_data: AMD-style extracted datasheet (with extraction.component etc.)
    gowin_dc: Gowin-style DC extraction (from extract_gowin_dc.py)
    lattice_dc: Lattice-style DC extraction (from extract_lattice_dc.py)
    """
    ext = get_extraction(dc_data)
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
    elif vendor in ("Intel/Altera", "Intel", "Altera"):
        manufacturer = "Intel/Altera"
    else:
        manufacturer = comp.get("manufacturer", "AMD")

    raw_elec = ext.get("electrical_characteristics", [])
    raw_abs = ext.get("absolute_maximum_ratings", [])
    if gowin_dc:
        raw_abs = raw_abs + list(gowin_dc.get("absolute_maximum_ratings", []))
    if lattice_dc:
        raw_abs = raw_abs + list(lattice_dc.get("absolute_maximum_ratings", []))
    thermal = _extract_thermal(raw_elec=raw_elec, raw_abs=raw_abs)

    normalized_diff_pairs = _normalize_diff_pairs(pinout_data.get("diff_pairs", []))
    normalized_pins = _normalize_pins(pinout_data.get("pins", []))
    device_identity = _infer_fpga_device_identity(manufacturer, pinout_data, comp.get("description"))
    source_traceability = _generic_fpga_source_traceability(pinout_data)
    result = {
        "_schema": SCHEMA_VERSION,
        "_type": "fpga",
        "mpn": device,
        "manufacturer": manufacturer,
        "category": "FPGA",
        "description": comp.get("description"),
        "package": package,
        "device_identity": device_identity,

        # From DC datasheet
        "supply_specs": supply_specs,
        "io_standard_specs": io_standard_specs,
        "thermal": thermal,

        # From pinout (L1-L5)
        "power_rails": pinout_data.get("power_rails", {}),
        "banks": _normalize_banks(pinout_data.get("banks", {})),
        "diff_pairs": normalized_diff_pairs,
        "drc_rules": _normalize_drc_rules(pinout_data.get("drc_rules", {})),

        # Pin data — full list + normalized lookup
        "pins": normalized_pins,
        "lookup": _normalize_lookup(pinout_data),

        # Summary
        "summary": pinout_data.get("summary", {}),
    }
    if source_traceability:
        result["source_traceability"] = source_traceability
    capability_blocks = _generic_fpga_capability_blocks(pinout_data, vendor, device, package, normalized_diff_pairs)
    constraint_blocks = _generic_fpga_constraint_blocks(pinout_data, capability_blocks, normalized_diff_pairs)
    guide_data = _load_gowin_family_design_guide(device, package, pinout_data, gowin_dc=gowin_dc) if vendor == "Gowin" else {}
    if guide_data.get("constraint_overlays"):
        constraint_blocks = _deep_merge_dict(constraint_blocks, guide_data["constraint_overlays"])
    if capability_blocks:
        result["capability_blocks"] = capability_blocks
    if constraint_blocks:
        result["constraint_blocks"] = constraint_blocks
    legacy_ip_blocks = capability_blocks.get("legacy_ip_blocks") if capability_blocks else None
    if legacy_ip_blocks:
        result["ip_blocks"] = legacy_ip_blocks
    if guide_data.get("domains"):
        result["domains"] = guide_data["domains"]

    # Add absolute maximum ratings if available
    if gowin_dc or lattice_dc:
        result["absolute_maximum_ratings"] = abs_max_specs

    if vendor == "Gowin":
        public_overlay = _gowin_public_device_overlay(pinout_data)
        if public_overlay:
            result = _deep_merge_dict(result, public_overlay)
    elif vendor in ("Intel/Altera", "Intel", "Altera"):
        public_overlay = _intel_agilex5_public_device_overlay(pinout_data)
        if public_overlay:
            result = _deep_merge_dict(result, public_overlay)

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
                fp.write("\n")
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
                fp.write("\n")

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
        if f.name in {"_manifest.json", "_fpga_catalog.json"}:
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
        fp.write("\n")
    print(f"Manifest: {manifest_path} ({len(manifest['devices'])} devices)")

    fpga_catalog = build_catalog(output_dir)
    fpga_catalog_path = output_dir / "_fpga_catalog.json"
    fpga_catalog_path.write_text(json.dumps(fpga_catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"FPGA catalog: {fpga_catalog_path} ({fpga_catalog['summary']['device_count']} devices, {fpga_catalog['summary']['package_count']} packages)")


if __name__ == "__main__":
    main()
