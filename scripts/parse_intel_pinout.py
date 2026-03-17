#!/usr/bin/env python3
"""Parse Intel/Altera Agilex 5 pinout XLSX files into structured JSON.

The official Agilex 5 pinout workbooks are standard XLSX files. We parse the
OOXML payload directly so the repository does not need an extra Python package.
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

from normalize_fpga_parse import normalize_fpga_parse_result

DEFAULT_XLSX_DIR = Path(__file__).parent.parent / "data/raw/fpga/intel_agilex5"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data/extracted_v2/fpga/pinout"
PINOUT_INDEX_URL = "https://www.altera.com/design/devices/resources/pinouts"

NAMESPACES = {
    "sheet": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}

CONTENT_IDS = {
    "A5EC013B": "819287",
    "A5ED013B": "819288",
    "A5EC052A": "830445",
    "A5ED052A": "830449",
}

CONFIG_PIN_NAMES = {
    "TCK",
    "TMS",
    "TDI",
    "TDO",
    "NCONFIG",
    "NSTATUS",
    "CONF_DONE",
    "OSC_CLK_1",
    "OSC_CLK_2",
}

ORDERING_VARIANTS = {
    "A": {"device_role": "FPGA", "hps": "none", "transceiver": False, "crypto": False},
    "B": {"device_role": "FPGA SoC", "hps": "quad", "transceiver": False, "crypto": True},
    "C": {"device_role": "FPGA", "hps": "none", "transceiver": True, "crypto": False},
    "D": {"device_role": "FPGA SoC", "hps": "quad", "transceiver": True, "crypto": True},
    "E": {"device_role": "FPGA SoC", "hps": "dual", "transceiver": False, "crypto": False},
    "G": {"device_role": "FPGA", "hps": "none", "transceiver": False, "crypto": True},
}


def _col_to_index(column: str) -> int:
    value = 0
    for char in column:
        if char.isalpha():
            value = value * 26 + ord(char.upper()) - 64
    return value - 1


def _parse_shared_strings(zf: ZipFile) -> list[str]:
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("sheet:si", NAMESPACES):
        values.append("".join(text.text or "" for text in item.iterfind(".//sheet:t", NAMESPACES)))
    return values


def _parse_workbook_sheets(zf: ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("pkg:Relationship", NAMESPACES)
    }
    sheets: list[tuple[str, str]] = []
    for sheet in workbook.findall("sheet:sheets/sheet:sheet", NAMESPACES):
        sheet_name = sheet.attrib["name"]
        rel_id = sheet.attrib[f"{{{NAMESPACES['rel']}}}id"]
        sheets.append((sheet_name, f"xl/{rid_to_target[rel_id]}"))
    return sheets


def _parse_sheet_rows(zf: ZipFile, sheet_path: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(zf.read(sheet_path))
    rows: list[list[str]] = []
    for row in root.findall(".//sheet:sheetData/sheet:row", NAMESPACES):
        values: dict[int, str] = {}
        for cell in row.findall("sheet:c", NAMESPACES):
            ref = "".join(ch for ch in cell.attrib.get("r", "") if ch.isalpha())
            col_idx = _col_to_index(ref)
            cell_type = cell.attrib.get("t")
            value_node = cell.find("sheet:v", NAMESPACES)
            if value_node is None:
                value = "".join(text.text or "" for text in cell.iterfind(".//sheet:t", NAMESPACES))
            elif cell_type == "s":
                value = shared_strings[int(value_node.text)]
            else:
                value = value_node.text or ""
            values[col_idx] = value
        rows.append([values.get(i, "") for i in range(max(values.keys(), default=-1) + 1)])
    return rows


def _extract_device_from_title(title: str) -> str:
    match = re.search(r"(A5E[A-Z]\d{3}[AB])", title.upper())
    if not match:
        raise ValueError(f"could not detect device from workbook title: {title!r}")
    return match.group(1)


def _base_device(device: str) -> str | None:
    match = re.match(r"^(A5E)[A-Z](\d{3}[AB])$", device.upper())
    if not match:
        return None
    return f"{match.group(1)}{match.group(2)}"


def _variant_properties(device: str) -> dict:
    match = re.match(r"^A5E([A-Z])\d{3}[AB]$", device.upper())
    if not match:
        return {}
    return {"variant_code": match.group(1), **ORDERING_VARIANTS.get(match.group(1), {})}


def _content_source(device: str) -> dict:
    content_id = CONTENT_IDS.get(device.upper())
    source_url = f"https://cdrdv2.intel.com/v1/dl/getContent/{content_id}" if content_id else None
    return {
        "source_document_id": content_id,
        "source_url": source_url,
        "source_index_url": PINOUT_INDEX_URL,
    }


def _parse_resource_counts(rows: list[list[str]]) -> dict[str, dict[str, dict]]:
    header = rows[1]
    package_columns: dict[int, str] = {}
    for idx, value in enumerate(header):
        if value.endswith(" Package"):
            package_columns[idx] = value.replace(" Package", "").strip()

    resources: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows[2:]:
        if len(row) < 2 or not row[0] or not row[1]:
            continue
        bank_type = row[0].strip()
        bank = row[1].strip()
        for idx, package in package_columns.items():
            if idx >= len(row):
                continue
            raw_count = row[idx].strip()
            if not raw_count or raw_count == "-":
                continue
            resources[package][bank] = {
                "bank_type": bank_type,
                "package_pin_capacity": int(raw_count),
            }
    return dict(resources)


def _parse_revision_history(rows: list[list[str]]) -> dict[str, dict]:
    revisions: dict[str, dict] = {}
    current_package: str | None = None
    for row in rows[1:]:
        if len(row) >= 3 and row[0] == "Date" and "Revision History for" in row[2]:
            current_package = row[2].replace("Revision History for", "").replace("Package", "").strip()
            continue
        if current_package and len(row) >= 3 and row[1]:
            revisions[current_package] = {
                "latest_version": row[1].strip(),
                "latest_revision_note": row[2].strip(),
            }
    return revisions


def _parse_pin_list_metadata(title_row: str, package: str) -> dict:
    version_match = re.search(r"Version:\s*([0-9-]+)", title_row)
    status_match = re.search(rf"{re.escape(package)}\s+Status:\s*([A-Za-z]+)", title_row)
    return {
        "sheet_version": version_match.group(1) if version_match else None,
        "sheet_status": status_match.group(1) if status_match else None,
    }


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _pin_name(raw_name: str, bank: str | None, bank_index: str | None, dedicated_channel: str | None, hps_function: str | None) -> str:
    if raw_name == "IO":
        if dedicated_channel:
            return dedicated_channel
        if bank and bank_index:
            return f"IO_{bank}_{bank_index}"
    if hps_function:
        return hps_function
    return raw_name


def _polarity(name: str) -> str | None:
    upper = name.upper()
    if upper.endswith("P") or upper.endswith("_P"):
        return "P"
    if upper.endswith("N") or upper.endswith("_N"):
        return "N"
    if upper.endswith("M"):
        return "N"
    return None


def _classify_pin(raw_name: str, bank: str, hps_function: str, dedicated_channel: str) -> str:
    upper = raw_name.upper()
    if upper.startswith("GND"):
        return "GROUND"
    if upper in {"NC", "DNU"}:
        return "NC"
    if upper.startswith("VCC") or upper.startswith("VDD"):
        return "POWER"
    if bank == "SDM" or upper.startswith("SDM_") or upper in CONFIG_PIN_NAMES or upper.startswith("NCONFIG") or upper.startswith("NSTATUS"):
        return "CONFIG"
    if bank == "HPS" or upper.startswith("HPS_") or hps_function:
        return "HPS_IO"
    if upper.startswith("REFCLK_GTS"):
        return "SERDES_REFCLK"
    if upper.startswith("GTS") and "_RX_" in upper:
        return "SERDES_RX"
    if upper.startswith("GTS") and "_TX_" in upper:
        return "SERDES_TX"
    if upper.startswith("CDRCLKOUT") or upper.startswith("RCOMP") or upper.startswith("APROBE") or upper.startswith("VSIG"):
        return "SPECIAL"
    if upper == "IO" or dedicated_channel.startswith("DIFF_IO_"):
        return "IO"
    return "SPECIAL"


def _pin_drc(function: str, name: str) -> dict | None:
    if function == "POWER":
        return {"must_connect": True}
    if function == "GROUND":
        return {"must_connect": True, "net": "GND"}
    if function == "CONFIG":
        return {"must_connect": True, "desc": f"Configuration / SDM signal: {name}"}
    return None


def _extract_diff_pairs(pins: list[dict]) -> list[dict]:
    pairs: list[dict] = []
    grouped: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)

    for pin in pins:
        function = pin.get("function")
        name = pin.get("name", "")
        polarity = pin.get("polarity")
        if function not in {"IO", "SERDES_RX", "SERDES_TX", "SERDES_REFCLK"} or not polarity:
            continue
        if function == "IO":
            base = re.sub(r"[PN]$", "", name, flags=re.IGNORECASE)
        else:
            base = re.sub(r"([PN]|_[PN])$", "", name, flags=re.IGNORECASE)
            base = re.sub(r"([pn]|_[pn])$", "", base)
        grouped[(function, base)][polarity] = pin

    for (function, pair_name), entry in sorted(grouped.items()):
        if "P" not in entry or "N" not in entry:
            continue
        kind = {
            "IO": "IO",
            "SERDES_RX": "SERDES_RX",
            "SERDES_TX": "SERDES_TX",
            "SERDES_REFCLK": "SERDES_REFCLK",
        }[function]
        pairs.append({
            "type": kind,
            "pair_name": pair_name,
            "p_pin": entry["P"]["pin"],
            "n_pin": entry["N"]["pin"],
            "p_name": entry["P"]["name"],
            "n_name": entry["N"]["name"],
            "bank": entry["P"].get("bank"),
        })
    return pairs


def _build_banks(resource_counts: dict[str, dict], pins: list[dict]) -> dict:
    actual: dict[str, dict] = defaultdict(lambda: {"total_pins": 0, "io_pins": 0, "hps_io_pins": 0, "config_pins": 0})
    for pin in pins:
        bank = (pin.get("bank") or "").strip()
        if not bank:
            continue
        entry = actual[bank]
        entry["total_pins"] += 1
        if pin.get("function") == "IO":
            entry["io_pins"] += 1
        elif pin.get("function") == "HPS_IO":
            entry["hps_io_pins"] += 1
        elif pin.get("function") == "CONFIG":
            entry["config_pins"] += 1

    bank_ids = sorted(set(resource_counts) | set(actual), key=lambda value: (not bool(re.search(r"\d", value)), value))
    banks: dict[str, dict] = {}
    for bank in bank_ids:
        banks[bank] = {
            "bank": bank,
            "bank_type": resource_counts.get(bank, {}).get("bank_type"),
            "package_pin_capacity": resource_counts.get(bank, {}).get("package_pin_capacity"),
            **actual.get(bank, {"total_pins": 0, "io_pins": 0, "hps_io_pins": 0, "config_pins": 0}),
        }
    return banks


def _build_power_rails(pins: list[dict]) -> dict:
    grouped: dict[str, dict] = {}
    for pin in pins:
        if pin.get("function") != "POWER":
            continue
        name = pin["raw_name"]
        entry = grouped.setdefault(name, {"pin_count": 0, "banks": []})
        entry["pin_count"] += 1
        bank = pin.get("bank")
        if bank and bank not in entry["banks"]:
            entry["banks"].append(bank)
    for entry in grouped.values():
        entry["banks"].sort()
    return dict(sorted(grouped.items()))


def _build_lookup(pins: list[dict]) -> dict:
    pin_to_name = {pin["pin"]: pin["name"] for pin in pins}
    name_counts = Counter(pin["name"] for pin in pins)
    name_to_pin = {pin["name"]: pin["pin"] for pin in pins if name_counts[pin["name"]] == 1}
    return {
        "pin_to_name": pin_to_name,
        "name_to_pin": name_to_pin,
    }


def _summary(functions: Counter[str], diff_pairs: list[dict]) -> dict:
    return {
        "by_function": dict(sorted(functions.items())),
        "diff_pairs": {
            "IO": len([pair for pair in diff_pairs if pair["type"] == "IO"]),
            "SERDES_RX": len([pair for pair in diff_pairs if pair["type"] == "SERDES_RX"]),
            "SERDES_TX": len([pair for pair in diff_pairs if pair["type"] == "SERDES_TX"]),
            "SERDES_REFCLK": len([pair for pair in diff_pairs if pair["type"] == "SERDES_REFCLK"]),
        },
    }


def parse_intel_xlsx(filepath: Path) -> list[dict]:
    with ZipFile(filepath) as zf:
        shared_strings = _parse_shared_strings(zf)
        sheets = dict(_parse_workbook_sheets(zf))
        resource_rows = _parse_sheet_rows(zf, sheets["IO Resource Count"], shared_strings)
        revision_rows = _parse_sheet_rows(zf, sheets["Revision History"], shared_strings)

        workbook_title = resource_rows[0][0]
        device = _extract_device_from_title(workbook_title)
        package_resources = _parse_resource_counts(resource_rows)
        revision_history = _parse_revision_history(revision_rows)
        source = _content_source(device)
        variant = _variant_properties(device)

        results: list[dict] = []
        for sheet_name, sheet_path in sheets.items():
            if not sheet_name.startswith("Pin List "):
                continue
            package = sheet_name.replace("Pin List ", "").strip()
            rows = _parse_sheet_rows(zf, sheet_path, shared_strings)
            metadata = _parse_pin_list_metadata(rows[0][0], package)
            header = rows[1]
            header_index = {value: idx for idx, value in enumerate(header)}

            pins: list[dict] = []
            function_counts: Counter[str] = Counter()
            for row in rows[2:]:
                pin_col = header_index.get(package)
                if pin_col is None or pin_col >= len(row):
                    continue
                pin_location = row[pin_col].strip()
                if not pin_location:
                    continue

                bank = row[header_index["Bank Number"]].strip() if header_index.get("Bank Number") is not None and header_index["Bank Number"] < len(row) else ""
                bank_index = row[header_index["Index within I/O Bank"]].strip() if header_index.get("Index within I/O Bank") is not None and header_index["Index within I/O Bank"] < len(row) else ""
                raw_name = row[header_index["Pin Name/Function"]].strip()
                optional_functions = row[header_index["Optional Function(s)"]].strip() if header_index.get("Optional Function(s)") is not None and header_index["Optional Function(s)"] < len(row) else ""
                configuration_function = row[header_index["Configuration Function"]].strip() if header_index.get("Configuration Function") is not None and header_index["Configuration Function"] < len(row) else ""
                hps_function = row[header_index["HPS Function"]].strip() if header_index.get("HPS Function") is not None and header_index["HPS Function"] < len(row) else ""
                dedicated_channel = row[header_index["Dedicated Tx/Rx Channel SERDES"]].strip() if header_index.get("Dedicated Tx/Rx Channel SERDES") is not None and header_index["Dedicated Tx/Rx Channel SERDES"] < len(row) else ""
                soft_cdr_support = row[header_index["Soft CDR Support"]].strip() if header_index.get("Soft CDR Support") is not None and header_index["Soft CDR Support"] < len(row) else ""
                dqs_x4 = row[header_index["DQS for X4"]].strip() if header_index.get("DQS for X4") is not None and header_index["DQS for X4"] < len(row) else ""
                dqs_x8_x9 = row[header_index["DQS for X8/X9"]].strip() if header_index.get("DQS for X8/X9") is not None and header_index["DQS for X8/X9"] < len(row) else ""
                dqs_x16_x18 = row[header_index["DQS for X16/X18"]].strip() if header_index.get("DQS for X16/X18") is not None and header_index["DQS for X16/X18"] < len(row) else ""

                name = _pin_name(raw_name, bank or None, bank_index or None, dedicated_channel or None, hps_function or None)
                function = _classify_pin(raw_name, bank, hps_function, dedicated_channel)
                pin = {
                    "pin": pin_location,
                    "name": name,
                    "raw_name": raw_name,
                    "function": function,
                    "category": function,
                    "bank": bank or None,
                    "bank_index": int(bank_index) if bank_index.isdigit() else None,
                    "optional_functions": _split_csv(optional_functions),
                    "configuration_function": configuration_function or None,
                    "hps_function": hps_function or None,
                    "dedicated_channel": dedicated_channel or None,
                    "soft_cdr_support": soft_cdr_support == "Yes",
                    "dqs_x4": dqs_x4 or None,
                    "dqs_x8_x9": dqs_x8_x9 or None,
                    "dqs_x16_x18": dqs_x16_x18 or None,
                }
                polarity = _polarity(name)
                if polarity:
                    pin["polarity"] = polarity
                drc = _pin_drc(function, name)
                if drc:
                    pin["drc"] = drc
                pins.append(pin)
                function_counts[function] += 1

            diff_pairs = _extract_diff_pairs(pins)
            result = {
                "_schema_version": "2.0",
                "_purpose": "FPGA pin definition for LLM-driven schematic DRC",
                "_vendor": "Intel/Altera",
                "_family": "Agilex 5",
                "_series": "E-Series",
                "_base_device": _base_device(device),
                "device": device,
                "package": package,
                "source_file": filepath.name,
                **source,
                "source_version": revision_history.get(package, {}).get("latest_version") or metadata["sheet_version"],
                "source_status": metadata["sheet_status"],
                "source_revision_note": revision_history.get(package, {}).get("latest_revision_note"),
                "total_pins": len(pins),
                "ordering_variant": variant,
                "summary": _summary(function_counts, diff_pairs),
                "power_rails": _build_power_rails(pins),
                "banks": _build_banks(package_resources.get(package, {}), pins),
                "diff_pairs": diff_pairs,
                "drc_rules": {
                    "power_integrity": {"severity": "ERROR", "desc": "All power and ground pins must be connected."},
                    "configuration_pins": {"severity": "ERROR", "desc": "Configuration and SDM pins must be wired per the selected boot scheme."},
                    "serdes_refclk": {"severity": "ERROR", "desc": "Refclk pair selection and quad mapping must match the chosen transceiver usage."},
                },
                "pins": pins,
                "lookup": _build_lookup(pins),
            }
            results.append(normalize_fpga_parse_result(result))

    return results


def main() -> None:
    xlsx_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX_DIR
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    xlsx_files = sorted(xlsx_dir.glob("*.xlsx"))
    if not xlsx_files:
        print(f"No Intel/Altera pinout XLSX files found in {xlsx_dir}")
        raise SystemExit(1)

    exported = 0
    for filepath in xlsx_files:
        print(f"Parsing {filepath.name}...")
        for result in parse_intel_xlsx(filepath):
            safe_name = f"intel_agilex5_{result['device']}_{result['package']}".lower()
            out_path = output_dir / f"{safe_name}.json"
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"  {result['device']} {result['package']}: {result['total_pins']} pins -> {out_path.name}")
            exported += 1
    print(f"Exported {exported} Intel/Altera package pinouts")


if __name__ == "__main__":
    main()
