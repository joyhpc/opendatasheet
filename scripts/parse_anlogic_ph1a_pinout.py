#!/usr/bin/env python3
"""Parse official Anlogic PH1A PINLIST workbooks into FPGA pinout JSON.

The PH1A package-capability parser already captures package-level truth from
product tables and user guides. This parser upgrades the source basis with the
official per-package PINLIST workbooks so downstream consumers can use real
pins, banks, differential pairs, and pin-delay metadata.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

from normalize_fpga_parse import normalize_fpga_parse_result

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "fpga" / "anlogic_ph1a" / "pinlist"
MANIFEST_PATH = RAW_DIR / "_download_manifest.json"
PACKAGE_DIR = ROOT / "data" / "extracted_v2" / "fpga" / "anlogic_ph1a"
OUTPUT_DIR = ROOT / "data" / "extracted_v2" / "fpga" / "pinout"

NS = {
    "sheet": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}

CONFIG_PINS = {
    "CCLK_0",
    "DONE_0",
    "INITN_0",
    "M0_0",
    "M1_0",
    "M2_0",
    "PROGRAMN_0",
    "TCK_0",
    "TDI_0",
    "TDO_0",
    "TMS_0",
    "TRSTN_0",
}

CONFIG_ALIASES = {
    "BUSY",
    "CSN",
    "CSON",
    "DIN",
    "DOUT",
    "HOLDN",
    "HSWAPEN",
    "MISO",
    "MOSI",
    "RDWRN",
    "SPICSN",
    "USRCLK",
    "WPN",
}


def _safe_upper(value: str | None) -> str:
    return (value or "").upper()


def _col_to_index(column: str) -> int:
    value = 0
    for char in column:
        if char.isalpha():
            value = value * 26 + ord(char.upper()) - 64
    return value - 1


def _load_shared_strings(zf: ZipFile) -> list[str]:
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in item.iterfind(".//sheet:t", NS))
        for item in root.findall("sheet:si", NS)
    ]


def _load_sheet_targets(zf: ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_id_key = f"{{{NS['rel']}}}id"
    rid_to_target = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("pkg:Relationship", NS)
    }
    return [
        (sheet.attrib["name"], f"xl/{rid_to_target[sheet.attrib[rel_id_key]]}")
        for sheet in workbook.findall("sheet:sheets/sheet:sheet", NS)
    ]


def _sheet_rows(zf: ZipFile, sheet_path: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(zf.read(sheet_path))
    rows: list[list[str]] = []
    for row in root.findall(".//sheet:sheetData/sheet:row", NS):
        values: dict[int, str] = {}
        for cell in row.findall("sheet:c", NS):
            ref = "".join(ch for ch in cell.attrib.get("r", "") if ch.isalpha())
            col_idx = _col_to_index(ref)
            cell_type = cell.attrib.get("t")
            value_node = cell.find("sheet:v", NS)
            if value_node is None:
                value = "".join(text.text or "" for text in cell.iterfind(".//sheet:t", NS))
            elif cell_type == "s":
                value = shared_strings[int(value_node.text)]
            else:
                value = value_node.text or ""
            values[col_idx] = value
        rows.append([values.get(i, "") for i in range(max(values.keys(), default=-1) + 1)])
    return rows


def _manifest_entries() -> dict[str, dict]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {entry["device"]: entry for entry in manifest["entries"]}


def _package_overlays() -> dict[str, dict]:
    overlays = {}
    for path in sorted(PACKAGE_DIR.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("_type") == "fpga_family_package_matrix":
            continue
        overlays[record["device"]] = record
    return overlays


def _split_name(raw_name: str) -> tuple[str, list[str]]:
    parts = [item.strip() for item in re.split(r"\s*,\s*", raw_name.strip()) if item.strip()]
    primary = parts[0] if parts else raw_name.strip()
    aliases = parts[1:] if len(parts) > 1 else []
    return primary, aliases


def _normalize_rail_name(primary_name: str) -> str:
    name = primary_name.replace(" ", "_")
    name = re.sub(r"_(\d+)$", "", name) if name.count("_") >= 2 and name.startswith(("VCCIO_", "PHYVCCT_", "PHYVCCA_", "VCCDPHY_", "VCCAUX_", "VCCINT_")) else name
    name = re.sub(r"\s+\d+$", "", name)
    return name


def _extract_bank(primary_name: str) -> str | None:
    upper = _safe_upper(primary_name)
    for pattern in (
        r"_(\d+)$",
        r"^VCCIO_(\d+)$",
        r"^PHYVCC[AT]_(\d+)$",
        r"^REFCLK[PM]_(\d+)$",
        r"^[RT]X[PM]\d*_(\d+)$",
    ):
        match = re.search(pattern, upper)
        if match:
            return match.group(1)
    return None


def _classify_pin(primary_name: str, aliases: list[str]) -> dict:
    upper = _safe_upper(primary_name)
    alias_upper = [_safe_upper(alias) for alias in aliases]
    bank = _extract_bank(primary_name)

    if upper.startswith("GND"):
        return {"function": "GROUND", "bank": None, "drc": {"must_connect": True, "net": "GND"}}
    if upper.startswith(("VCC", "PHYVCC")):
        return {"function": "POWER", "bank": bank, "drc": {"must_connect": True}}
    if upper == "RESREF":
        return {"function": "GT_POWER", "bank": None, "drc": {"must_connect": True}}
    if upper in CONFIG_PINS:
        return {
            "function": "CONFIG",
            "bank": "0",
            "drc": {"must_connect": True, "desc": f"Dedicated configuration pin: {primary_name}"},
        }
    if upper.startswith("REFCLK"):
        polarity = "P" if "P_" in upper else "N"
        return {"function": "SERDES_REFCLK", "bank": bank, "polarity": polarity}
    if upper.startswith(("RXP", "RXM")):
        polarity = "P" if upper.startswith("RXP") else "N"
        return {"function": "SERDES_RX", "bank": bank, "polarity": polarity}
    if upper.startswith(("TXP", "TXM")):
        polarity = "P" if upper.startswith("TXP") else "N"
        return {"function": "SERDES_TX", "bank": bank, "polarity": polarity}
    if re.match(r"^I_\d+[PN]_DPHY\d+$", upper):
        polarity = "P" if "P_DPHY" in upper else "N"
        attrs = {}
        lane_match = re.match(r"^I_(\d+)[PN]_DPHY(\d+)$", upper)
        if lane_match:
            attrs["dphy_pad_index"] = int(lane_match.group(1))
            attrs["dphy_instance"] = int(lane_match.group(2))
        return {"function": "MIPI", "bank": None, "polarity": polarity, **attrs}
    if upper.startswith("IO_"):
        result = {"function": "IO", "bank": bank}
        clock_aliases = [alias for alias in aliases if _safe_upper(alias).startswith(("GCLK", "GPLL"))]
        config_aliases = [alias for alias in aliases if _safe_upper(alias) in CONFIG_ALIASES]
        if clock_aliases:
            result["clock_capable"] = True
            result["clock_aliases"] = clock_aliases
        if any("DQS" in _safe_upper(alias) for alias in aliases):
            result["dqs_capable"] = True
        if any("VREF" in _safe_upper(alias) for alias in aliases):
            result["vref_capable"] = True
        if config_aliases:
            result["config_function"] = ",".join(config_aliases)
        polarity_match = re.match(r"^IO_[A-Z0-9]+([PN])_\d+$", upper)
        if polarity_match:
            result["polarity"] = polarity_match.group(1)
        return result
    return {"function": "SPECIAL", "bank": bank}


def _parse_delay_sheet(rows: list[list[str]]) -> tuple[dict[str, dict], dict[str, str]]:
    if not rows:
        return {}, {}
    header = rows[0]
    normalized_header = [_safe_upper(item) for item in header]
    metric_columns: list[tuple[int, str, str]] = []
    for idx, column in enumerate(normalized_header):
        if "MIN_TRACE_DELAY" in column:
            metric_columns.append((idx, "min_trace_delay_ps", header[idx]))
        elif "MAX_TRACE_DELAY" in column:
            metric_columns.append((idx, "max_trace_delay_ps", header[idx]))
        elif "PIN_DELAY" in column or "PINDELAY" in column:
            metric_columns.append((idx, "trace_delay_ps", header[idx]))
        elif "NETLENGTH" in column:
            metric_columns.append((idx, "net_length_mil", header[idx]))
    pin_metrics: dict[str, dict] = {}
    pin_name_map: dict[str, str] = {}
    for row in rows[1:]:
        if len(row) < 3 or not row[1]:
            continue
        pin = row[1].strip()
        pin_name = row[2].strip() if len(row) > 2 else ""
        pin_name_map[pin] = pin_name
        for column_idx, metric_key, metric_header in metric_columns:
            raw_metric = row[column_idx].strip() if column_idx < len(row) else ""
            if not raw_metric or raw_metric == "-":
                continue
            try:
                value = float(raw_metric)
            except ValueError:
                continue
            pin_metrics.setdefault(pin, {})[metric_key] = value
            pin_metrics[pin].setdefault("metric_headers", {})[metric_key] = metric_header
    return pin_metrics, pin_name_map


def _parse_schlib_rows(rows: list[list[str]], pin_metrics: dict[str, dict]) -> list[dict]:
    if not rows:
        return []
    pins = []
    for row in rows[1:]:
        if len(row) < 2 or not row[0] or not row[1]:
            continue
        pin = row[0].strip()
        raw_name = row[1].strip()
        pin_type = row[2].strip() if len(row) > 2 else ""
        primary_name, aliases = _split_name(raw_name)
        classification = _classify_pin(primary_name, aliases)
        extra_fields = {
            "raw_name": raw_name,
            "aliases": aliases,
            "symbol_type": pin_type or None,
            "section": row[7].strip() if len(row) > 7 else None,
            "symbol_position": row[6].strip() if len(row) > 6 else None,
        }
        if "clock_capable" in classification:
            extra_fields["clock_capable"] = classification.pop("clock_capable")
            extra_fields["clock_aliases"] = classification.pop("clock_aliases")
        if "dqs_capable" in classification:
            extra_fields["dqs_capable"] = classification.pop("dqs_capable")
        if "vref_capable" in classification:
            extra_fields["vref_capable"] = classification.pop("vref_capable")
        if "dphy_pad_index" in classification:
            extra_fields["dphy_pad_index"] = classification.pop("dphy_pad_index")
            extra_fields["dphy_instance"] = classification.pop("dphy_instance")
        if pin in pin_metrics:
            extra_fields.update(pin_metrics[pin])

        pin_entry = {
            "pin": pin,
            "name": primary_name,
            "function": classification.pop("function"),
            "bank": classification.pop("bank"),
        }
        for key, value in extra_fields.items():
            if value is not None and value != []:
                pin_entry[key] = value
        if classification.get("polarity"):
            pin_entry["polarity"] = classification.pop("polarity")
        if classification.get("config_function"):
            pin_entry["config_function"] = classification.pop("config_function")
        if classification.get("drc"):
            pin_entry["drc"] = classification.pop("drc")
        pins.append(pin_entry)
    return pins


def _pair_name_from_io(name: str) -> str | None:
    match = re.match(r"^(IO_[A-Z0-9]+)([PN])_(\d+)$", _safe_upper(name))
    if not match:
        return None
    return f"{match.group(1)}_{match.group(3)}"


def _pair_name_from_serdes(name: str) -> tuple[str | None, str | None]:
    upper = _safe_upper(name)
    match = re.match(r"^REFCLK([PM])_(\d+)$", upper)
    if match:
        return f"REFCLK_{match.group(2)}", "SERDES_REFCLK"
    match = re.match(r"^RX([PM])(\d+)_(\d+)$", upper)
    if match:
        return f"RX{match.group(2)}_{match.group(3)}", "SERDES_RX"
    match = re.match(r"^TX([PM])(\d+)_(\d+)$", upper)
    if match:
        return f"TX{match.group(2)}_{match.group(3)}", "SERDES_TX"
    return None, None


def _pair_name_from_mipi(pin: dict) -> tuple[str | None, str | None]:
    raw_name = pin.get("raw_name") or pin.get("attrs", {}).get("raw_name", "")
    instance = pin.get("dphy_instance")
    if instance is None:
        instance = pin.get("attrs", {}).get("dphy_instance")
    if instance is None:
        return None, None
    aliases = pin.get("aliases")
    if aliases is None:
        aliases = pin.get("attrs", {}).get("aliases", [])
    for alias in aliases:
        alias_upper = _safe_upper(alias)
        if alias_upper.startswith("CK"):
            return f"DPHY{instance}_CLK", "DPHY"
        data_match = re.match(r"DP(\d+)_\d+$", alias_upper)
        if data_match:
            return f"DPHY{instance}_D{data_match.group(1)}", "DPHY"
    lane_match = re.match(r"^I_(\d+)[PN]_DPHY\d+$", _safe_upper(raw_name))
    if lane_match:
        return f"DPHY{instance}_PAD{lane_match.group(1)}", "DPHY"
    return None, None


def _extract_diff_pairs(pins: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for pin in pins:
        polarity = pin.get("polarity")
        if polarity not in {"P", "N"}:
            continue
        name = pin.get("name", "")
        pair_name = None
        pair_type = None
        if pin.get("function") == "IO":
            pair_name = _pair_name_from_io(name)
            pair_type = "IO"
        elif pin.get("function", "").startswith("SERDES_"):
            pair_name, pair_type = _pair_name_from_serdes(name)
        elif pin.get("function") == "MIPI":
            pair_name, pair_type = _pair_name_from_mipi(pin)
        if not pair_name or not pair_type:
            continue
        groups[(pair_type, pair_name)][polarity] = pin

    pairs = []
    for (pair_type, pair_name), sides in sorted(groups.items()):
        if "P" not in sides or "N" not in sides:
            continue
        pairs.append(
            {
                "type": pair_type,
                "pair_name": pair_name,
                "p_pin": sides["P"]["pin"],
                "n_pin": sides["N"]["pin"],
                "p_name": sides["P"]["name"],
                "n_name": sides["N"]["name"],
                "bank": sides["P"].get("bank") or sides["N"].get("bank"),
            }
        )
    return pairs


def _build_banks(pins: list[dict], overlay: dict) -> dict[str, dict]:
    package_io_banks = overlay.get("package_io_banks", {}) if isinstance(overlay.get("package_io_banks"), dict) else {}
    hr_banks = {str(bank) for bank in (package_io_banks.get("hr_banks") or [])}
    hp_banks = {str(bank) for bank in (package_io_banks.get("hp_banks") or [])}

    banks: dict[str, dict] = {}
    for pin in pins:
        bank = pin.get("bank")
        if bank is None:
            continue
        entry = banks.setdefault(
            str(bank),
            {
                "bank": str(bank),
                "pins": [],
                "total_pins": 0,
                "io_pins": 0,
                "vcco_pin_count": 0,
                "clock_capable_pins": 0,
                "dqs_capable_pins": 0,
                "vref_capable_pins": 0,
            },
        )
        entry["pins"].append(pin["pin"])
        entry["total_pins"] += 1
        if pin.get("function") == "IO":
            entry["io_pins"] += 1
        if pin.get("name", "").startswith("VCCIO_"):
            entry["vcco_pin_count"] += 1
        if pin.get("clock_capable") or pin.get("attrs", {}).get("clock_capable"):
            entry["clock_capable_pins"] += 1
        if pin.get("dqs_capable") or pin.get("attrs", {}).get("dqs_capable"):
            entry["dqs_capable_pins"] += 1
        if pin.get("vref_capable") or pin.get("attrs", {}).get("vref_capable"):
            entry["vref_capable_pins"] += 1

    for bank_id, entry in banks.items():
        if bank_id in hr_banks:
            entry["bank_type"] = "HRIO"
        elif bank_id in hp_banks:
            entry["bank_type"] = "HPIO"
        elif int(bank_id) >= 80:
            entry["bank_type"] = "GT"
    return banks


def _build_power_rails(pins: list[dict]) -> dict[str, dict]:
    rails: dict[str, dict] = {}
    for pin in pins:
        if pin.get("function") not in {"POWER", "GT_POWER"}:
            continue
        rail_name = _normalize_rail_name(pin["name"])
        entry = rails.setdefault(
            rail_name,
            {
                "pins": [],
                "source": "official_pinlist",
            },
        )
        entry["pins"].append(pin["pin"])
        if pin.get("bank") is not None:
            entry.setdefault("banks", [])
            if pin["bank"] not in entry["banks"]:
                entry["banks"].append(pin["bank"])
        metric_headers = pin.get("metric_headers") or pin.get("attrs", {}).get("metric_headers")
        if metric_headers:
            entry["metric_headers"] = metric_headers
    return rails


def _build_lookup(pins: list[dict]) -> dict:
    by_pin = {pin["pin"]: pin["name"] for pin in pins}
    name_counts = Counter(pin["name"] for pin in pins)
    by_name = {
        pin["name"]: pin["pin"]
        for pin in pins
        if name_counts[pin["name"]] == 1
    }
    return {
        "by_pin": by_pin,
        "by_name": by_name,
        "io_pins": [pin["pin"] for pin in pins if pin.get("function") == "IO"],
        "power_pins": [pin["pin"] for pin in pins if pin.get("function") in {"POWER", "GROUND", "GT_POWER"}],
        "config_pins": [pin["pin"] for pin in pins if pin.get("function") == "CONFIG"],
    }


def _summary(pins: list[dict], diff_pairs: list[dict]) -> dict:
    by_function = Counter(pin["function"] for pin in pins)
    by_pair_type = Counter(pair["type"] for pair in diff_pairs)
    return {
        "by_function": dict(sorted(by_function.items())),
        "diff_pairs": dict(sorted(by_pair_type.items())),
    }


def _package_source_conflicts(overlay: dict, manifest_entry: dict | None) -> list[dict]:
    conflicts = list(overlay.get("source_conflicts") or [])
    mismatch = manifest_entry.get("official_listing_mismatch") if manifest_entry else None
    if mismatch:
        conflicts.append(
            {
                "field": "package_pinlist_download_url",
                "expected_device": manifest_entry["device"],
                "listing_name": manifest_entry["listing_name"],
                "download_id": manifest_entry["download_id"],
                "download_api_returned_url": mismatch["download_api_returned_url"],
                "used_download_url": manifest_entry["download_url"],
                "note": mismatch["issue"],
                "source": "anlogic_tools_downloads_page_and_download_api",
            }
        )
    return conflicts


def _package_pin_count_conflict(package: str, total_pins: int) -> dict | None:
    match = re.search(r"(\d+)$", package or "")
    if not match:
        return None
    nominal = int(match.group(1))
    if nominal == total_pins:
        return None
    return {
        "field": "package_pin_count",
        "package": package,
        "package_nominal_pin_count": nominal,
        "pinlist_row_count": total_pins,
        "note": "Official pinlist row count does not match the package suffix pin count; review NC/DNU handling before freezing library symbols.",
        "source": "official_pinlist_workbook",
    }


def _traceability(overlay: dict, manifest_entry: dict, source_file: str) -> dict:
    traceability = dict(overlay.get("source_traceability") or {})
    traceability["package_pinout"] = {
        "source_file": source_file,
        "source_url": manifest_entry["download_url"],
        "source_listing_name": manifest_entry["listing_name"],
        "source_download_id": manifest_entry["download_id"],
        "source_manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "source_page_url": json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["source_page"]["zh_cn_tools_downloads_url"],
    }
    return traceability


def _parse_workbook(path: Path, overlay: dict, manifest_entry: dict) -> dict:
    with ZipFile(path) as zf:
        shared_strings = _load_shared_strings(zf)
        sheets = _load_sheet_targets(zf)
        sheet_rows = {name: _sheet_rows(zf, target, shared_strings) for name, target in sheets}

    schlib_name = next(name for name, _ in sheets if name.upper() not in {"PIN_DELAY", "PINDELAY", "SHEET3"})
    delay_name = next((name for name, _ in sheets if name.upper() in {"PIN_DELAY", "PINDELAY"}), None)
    schlib_rows = sheet_rows[schlib_name]
    delay_rows = sheet_rows.get(delay_name, []) if delay_name else []
    pin_metrics, _ = _parse_delay_sheet(delay_rows)
    pins = _parse_schlib_rows(schlib_rows, pin_metrics)
    diff_pairs = _extract_diff_pairs(pins)
    banks = _build_banks(pins, overlay)

    result = {
        "_schema_version": "2.0",
        "_purpose": "FPGA pin definition for LLM-driven schematic DRC",
        "_vendor": "Anlogic",
        "_family": "SALPHOENIX 1A",
        "_series": "PH1A",
        "_base_device": overlay["device_identity"]["base_device"],
        "device": overlay["device"],
        "package": overlay["package"],
        "source_file": path.name,
        "pins": pins,
        "banks": banks,
        "diff_pairs": diff_pairs,
        "drc_rules": {
            "power_integrity": {"severity": "ERROR", "desc": "All power and ground rails from the official pinlist must be connected."},
            "config_pins": {"severity": "ERROR", "desc": "Dedicated configuration pins must be reviewed and terminated against the selected boot mode."},
            "diff_pair_integrity": {"severity": "ERROR", "desc": "Differential pairs from the official pinlist must be routed as complete P/N pairs."},
        },
        "power_rails": _build_power_rails(pins),
        "lookup": _build_lookup(pins),
        "summary": _summary(pins, diff_pairs),
        "total_pins": len(pins),
        "resources": overlay.get("resources"),
        "package_summary": overlay.get("package_summary"),
        "package_info": overlay.get("package_info"),
        "package_io_banks": overlay.get("package_io_banks"),
        "capability_blocks": overlay.get("capability_blocks"),
        "device_identity": overlay.get("device_identity"),
        "source_conflicts": _package_source_conflicts(overlay, manifest_entry),
        "source_traceability": _traceability(overlay, manifest_entry, path.name),
    }
    pin_count_conflict = _package_pin_count_conflict(overlay["package"], len(pins))
    if pin_count_conflict:
        result["source_conflicts"].append(pin_count_conflict)
    return normalize_fpga_parse_result(result)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_entries = _manifest_entries()
    overlays = _package_overlays()
    written = 0

    for device, manifest_entry in sorted(manifest_entries.items()):
        overlay = overlays[device]
        workbook_path = RAW_DIR / manifest_entry["local_file"]
        result = _parse_workbook(workbook_path, overlay, manifest_entry)
        out_path = OUTPUT_DIR / f"{device.lower()}_pinout.json"
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written += 1

    print(f"wrote {written} Anlogic PH1A pinout parses to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
