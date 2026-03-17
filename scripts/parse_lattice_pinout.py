#!/usr/bin/env python3
"""Parse Lattice FPGA pinout CSV files into structured JSON.

Supports:
  - ECP5/ECP5-5G family (PAD, Pin/Ball Function, Bank, ...)
  - CrossLink-NX family (PADN, Pin/Ball Funcion, CUST_NAME, BANK, ...)

Input:  Lattice pinout CSV files (downloaded as .xlsx but actually CSV)
Output: Per-package JSON files in schema v2.0 format

Usage:
    python parse_lattice_pinout.py [csv_dir] [output_dir]
    python parse_lattice_pinout.py /tmp /path/to/output
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from normalize_fpga_parse import normalize_fpga_parse_result

DEFAULT_CSV_DIR = Path(__file__).parent.parent / "data/raw/fpga/lattice"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data/extracted_v2/fpga/pinout"


# ─── Format Detection ──────────────────────────────────────────────

def detect_format(header: list[str]) -> str:
    """Detect ECP5 vs CrossLink-NX from CSV header."""
    h0 = header[0].strip().upper()
    if h0 == "PADN":
        return "crosslinknx"
    elif h0 == "PAD":
        return "ecp5"
    raise ValueError(f"Unknown Lattice CSV format, first column: {h0}")


def detect_device_from_comments(lines: list[str]) -> str:
    """Extract device name from comment lines at top of CSV."""
    for line in lines[:10]:
        if line.startswith("#"):
            # "# Pin Out For ECP5U-25" or "# Pin Out For LIFCL-40"
            m = re.search(r"Pin Out For\s+(\S+)", line)
            if m:
                return m.group(1).rstrip(",")
    return "UNKNOWN"


# ─── Pin Classification ────────────────────────────────────────────

# ECP5 config pin keywords
CONFIG_KEYWORDS = {
    "CCLK", "TDO", "TDI", "TCK", "TMS", "INITN", "PROGRAMN", "DONE",
    "CFG_0", "CFG_1", "CFG_2", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7",
    "MCLK", "SO", "SI", "SN", "CSSPIN", "WRITEN", "CSN", "CS1N",
    "HOLDN", "DOUT", "BUSY", "CS0N", "JTAG_EN",
}

# ECP5 SerDes pin patterns (ECP5-5G: HDINPx/HDINNx, HDOUTPx/HDOUTNx)
SERDES_RX_RE = re.compile(r"^HDINP|^HDINN", re.I)
SERDES_TX_RE = re.compile(r"^HDOUTP|^HDOUTN", re.I)
SERDES_REFCLK_RE = re.compile(r"^REFCLK[PN]?", re.I)

# CrossLink-NX SerDes patterns (SD0_RXDP, SD0_TXDN, SD0_REFCLKP, etc.)
CLNX_SERDES_RE = re.compile(r"^SD\d?_?(RXD|TXD|REFCLK)", re.I)


def classify_lattice_pin(name: str, bank: str, dual_func: str, fmt: str) -> dict:
    """Classify a Lattice pin into function category."""
    result = {"function": "SPECIAL"}
    name_upper = name.upper().strip()
    dual = (dual_func or "").upper().strip()

    # Ground
    if name_upper in ("GND", "VSS") or name_upper.startswith("VSS"):
        result["function"] = "GROUND"
        result["drc"] = {"must_connect": True, "connect_to": "GND"}
        return result

    # Power
    if name_upper.startswith("VCC") or name_upper.startswith("VDD"):
        result["function"] = "POWER"
        result["drc"] = {"must_connect": True}
        return result

    # NC
    if name_upper == "NC":
        result["function"] = "NC"
        return result

    # RESERVED → treat as ground
    if name_upper == "RESERVED":
        result["function"] = "GROUND"
        result["drc"] = {"must_connect": True, "connect_to": "GND",
                         "desc": "Reserved pin — must connect to GND"}
        return result

    # ECP5 SerDes (ECP5-5G: HDINPx/HDINNx, HDOUTPx/HDOUTNx)
    if SERDES_RX_RE.match(name_upper):
        result["function"] = "GT"
        result["polarity"] = "P" if "HDINP" in name_upper else "N"
        return result
    if SERDES_TX_RE.match(name_upper):
        result["function"] = "GT"
        result["polarity"] = "P" if "HDOUTP" in name_upper else "N"
        return result
    if SERDES_REFCLK_RE.match(name_upper) and "VCC" not in name_upper:
        result["function"] = "GT"
        if "REFCLKP" in name_upper:
            result["polarity"] = "P"
        elif "REFCLKN" in name_upper:
            result["polarity"] = "N"
        return result

    # CrossLink-NX SerDes (SD0_RXDP, SD0_TXDN, SD_REFCLKP, etc.)
    if CLNX_SERDES_RE.match(name_upper):
        result["function"] = "GT"
        if name_upper.endswith("P"):
            result["polarity"] = "P"
        elif name_upper.endswith("N"):
            result["polarity"] = "N"
        return result
    # SD0_REFRET, SD0_REXT — SerDes reference/termination
    if re.match(r"^SD\d?_(REFRET|REXT)", name_upper):
        result["function"] = "SPECIAL"
        return result

    # Dedicated config pins
    if name_upper in CONFIG_KEYWORDS:
        result["function"] = "CONFIG"
        result["drc"] = {"must_connect": True, "desc": f"Dedicated config pin: {name}"}
        return result

    # CrossLink-NX DPHY (MIPI D-PHY) pins
    if "DPHY" in name_upper or "D_PHY" in name_upper:
        result["function"] = "SPECIAL"
        if name_upper.endswith("P") or "CKP" in name_upper or "DP" in name_upper:
            result["polarity"] = "P"
        elif name_upper.endswith("N") or "CKN" in name_upper or "DN" in name_upper:
            result["polarity"] = "N"
        return result

    # ADC pins
    if name_upper.startswith("ADC"):
        result["function"] = "SPECIAL"
        if name_upper.endswith("P") or "DP" in name_upper:
            result["polarity"] = "P"
        elif name_upper.endswith("N") or "DN" in name_upper:
            result["polarity"] = "N"
        return result

    # Comparator pins
    if name_upper.startswith("COMP"):
        result["function"] = "SPECIAL"
        return result

    # PLL pins (not power)
    if "PLL" in name_upper and "VCC" not in name_upper:
        result["function"] = "SPECIAL"
        return result

    # IO pins: PLxxA/B, PTxxA/B, PRxxA/B, PBxxA/B pattern
    if re.match(r"^P[LTRB]\d+[A-D]$", name_upper):
        result["function"] = "IO"
        # Check if it has a config dual function
        if dual and dual != "-":
            for kw in CONFIG_KEYWORDS:
                if kw in dual:
                    result["drc"] = {
                        "must_connect": "recommended",
                        "config_function": dual,
                        "desc": f"Multi-function pin: IO + {dual}",
                    }
                    break
        return result

    # Catch-all for pins with a valid bank number → likely IO
    if bank and bank not in ("-", "", "None"):
        try:
            int(bank)
            result["function"] = "IO"
            return result
        except ValueError:
            pass

    return result


# ─── Diff Pair Extraction ──────────────────────────────────────────

def extract_diff_pairs(pins: list) -> list:
    """Extract differential pairs from Lattice pin data.

    Uses the Differential/LVDS column: True_OF_xxx / Comp_OF_xxx
    """
    pairs = []
    name_to_pin = {p["name"]: p for p in pins}

    seen = set()
    for p in pins:
        diff = p.get("_diff_raw", "")
        if not diff or diff == "-":
            continue

        # True_OF_PL2B → this pin is the P side, complement is PL2B
        m_true = re.match(r"True_OF_(\S+)", diff, re.I)
        if m_true:
            comp_name = m_true.group(1)
            if comp_name in name_to_pin:
                pair_key = tuple(sorted([p["name"], comp_name]))
                if pair_key in seen:
                    continue
                seen.add(pair_key)

                comp_pin = name_to_pin[comp_name]
                base = re.sub(r"[A-D]$", "", p["name"])
                pair_type = "IO"
                if p.get("high_speed"):
                    pair_type = "LVDS"

                pairs.append({
                    "type": pair_type,
                    "pair_name": base,
                    "p_pin": p["pin"],
                    "n_pin": comp_pin["pin"],
                    "p_name": p["name"],
                    "n_name": comp_pin["name"],
                    "bank": p.get("bank"),
                })

    # SerDes diff pairs (ECP5-5G: HDINP/HDINN, HDOUTP/HDOUTN)
    # CrossLink-NX: SD0_RXDP/SD0_RXDN, SD0_TXDP/SD0_TXDN, SD0_REFCLKP/SD0_REFCLKN
    gt_pins = [p for p in pins if p["function"] == "GT"]
    serdes_by_key = defaultdict(dict)
    for p in gt_pins:
        n = p["name"].upper()
        pol = p.get("polarity")
        if not pol:
            continue
        if "HDINP" in n or "HDINN" in n:
            ch = re.sub(r"^HDIN[PN]", "", n)
            key = f"RX_{ch}"
        elif "HDOUTP" in n or "HDOUTN" in n:
            ch = re.sub(r"^HDOUT[PN]", "", n)
            key = f"TX_{ch}"
        elif re.match(r"SD\d?_RXDP|SD\d?_RXDN", n):
            ch = re.sub(r"_RXD[PN]$", "", n)
            key = f"RX_{ch}"
        elif re.match(r"SD\d?_TXDP|SD\d?_TXDN", n):
            ch = re.sub(r"_TXD[PN]$", "", n)
            key = f"TX_{ch}"
        elif "REFCLK" in n:
            ch = re.sub(r"_?REFCLK[PN]?$", "", n)
            if not ch:
                ch = n.replace("REFCLKP", "").replace("REFCLKN", "")
            key = f"REFCLK_{ch}"
        else:
            continue
        serdes_by_key[key][pol] = p

    for key in sorted(serdes_by_key.keys()):
        entry = serdes_by_key[key]
        if "P" in entry and "N" in entry:
            pp = entry["P"]
            np_ = entry["N"]
            ptype = "GT_REFCLK" if "REFCLK" in key else ("GT_RX" if "RX" in key else "GT_TX")
            pairs.append({
                "type": ptype,
                "pair_name": key,
                "p_pin": pp["pin"],
                "n_pin": np_["pin"],
                "p_name": pp["name"],
                "n_name": np_["name"],
                "bank": pp.get("bank"),
            })

    # DPHY diff pairs (CrossLink-NX)
    dphy_pins = [p for p in pins if "DPHY" in p["name"].upper()]
    dphy_by_key = defaultdict(dict)
    for p in dphy_pins:
        pol = p.get("polarity")
        if not pol:
            continue
        n = p["name"].upper()
        # DPHY0_CKP/DPHY0_CKN → key=DPHY0_CK
        # DPHY0_DP0/DPHY0_DN0 → key=DPHY0_D0
        base = re.sub(r"_CK[PN]$", "_CK", n)
        base = re.sub(r"_D[PN](\d+)$", r"_D\1", base)
        dphy_by_key[base][pol] = p

    for key in sorted(dphy_by_key.keys()):
        entry = dphy_by_key[key]
        if "P" in entry and "N" in entry:
            pp = entry["P"]
            np_ = entry["N"]
            pairs.append({
                "type": "DPHY",
                "pair_name": key,
                "p_pin": pp["pin"],
                "n_pin": np_["pin"],
                "p_name": pp["name"],
                "n_name": np_["name"],
                "bank": pp.get("bank"),
            })

    return pairs


# ─── Bank Structure ────────────────────────────────────────────────

def build_banks(pins: list) -> dict:
    """Build bank structure from pin data."""
    banks = defaultdict(lambda: {
        "total_pins": 0, "io_pins": 0,
        "high_speed_count": 0, "dqs_groups": set(),
    })

    for p in pins:
        b = p.get("bank")
        if not b or b in ("-", "None", ""):
            continue
        entry = banks[b]
        entry["total_pins"] += 1
        if p["function"] == "IO":
            entry["io_pins"] += 1
            if p.get("high_speed"):
                entry["high_speed_count"] += 1
            dqs = p.get("dqs")
            if dqs and dqs != "-":
                entry["dqs_groups"].add(dqs)

    result = {}
    for bank_id in sorted(banks.keys(), key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else 999)):
        b = banks[bank_id]
        result[bank_id] = {
            "bank": bank_id,
            "total_pins": b["total_pins"],
            "io_pins": b["io_pins"],
            "high_speed_count": b["high_speed_count"],
            "dqs_groups": sorted(b["dqs_groups"]) if b["dqs_groups"] else None,
        }
    return result


# ─── CSV Parsing ───────────────────────────────────────────────────

def parse_lattice_csv(filepath: Path) -> list[dict]:
    """Parse a Lattice pinout CSV file. Returns list of results (one per package)."""
    raw = filepath.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()

    device = detect_device_from_comments(lines)

    # Find header line (first non-comment, non-empty line with PAD or PADN)
    header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip().strip("\r")
        if stripped.startswith("#") or not stripped:
            continue
        # Parse as CSV to handle quoted fields
        reader = csv.reader([stripped])
        row = next(reader)
        if row and row[0].strip().upper() in ("PAD", "PADN"):
            header_idx = i
            break

    if header_idx is None:
        raise ValueError(f"No header found in {filepath}")

    # Parse CSV from header onwards
    csv_lines = lines[header_idx:]
    reader = csv.reader(csv_lines)
    header = [h.strip() for h in next(reader)]

    fmt = detect_format(header)

    # Map columns
    if fmt == "ecp5":
        # PAD, Pin/Ball Function, Bank, Dual Function, Differential, High Speed, DQS, <packages...>
        col_pad = 0
        col_func = 1
        col_bank = 2
        col_dual = 3
        col_diff = 4
        col_hs = 5
        col_dqs = 6
        pkg_start = 7
    else:
        # PADN, Pin/Ball Funcion, CUST_NAME, BANK, Dual Function, LVDS, HIGHSPEED, DQS, <packages...>
        col_pad = 0
        col_func = 1
        col_cust = 2
        col_bank = 3
        col_dual = 4
        col_diff = 5  # LVDS column
        col_hs = 6
        col_dqs = 7
        pkg_start = 8

    # Package names from header
    pkg_names = [h.strip() for h in header[pkg_start:] if h.strip()]

    # Parse all rows
    all_rows = []
    for row in reader:
        if not row or not row[0].strip():
            continue
        # Skip comment/empty rows
        if row[0].strip().startswith("#"):
            continue
        all_rows.append(row)

    # Build per-package results
    results = []
    for pkg_idx, pkg_name in enumerate(pkg_names):
        col_pin = pkg_start + pkg_idx
        pins = []

        for row in all_rows:
            if col_pin >= len(row):
                continue

            pin_loc = row[col_pin].strip() if col_pin < len(row) else "-"
            if not pin_loc or pin_loc == "-":
                continue

            pad = row[col_pad].strip()
            func_name = row[col_func].strip()
            bank = row[col_bank].strip() if col_bank < len(row) else "-"
            dual = row[col_dual].strip() if col_dual < len(row) else "-"
            diff = row[col_diff].strip() if col_diff < len(row) else "-"
            hs = row[col_hs].strip() if col_hs < len(row) else "-"
            dqs = row[col_dqs].strip() if col_dqs < len(row) else "-"

            if bank == "-":
                bank = None
            if dual == "-":
                dual = None
            if diff == "-":
                diff = None
            if dqs == "-":
                dqs = None

            is_hs = hs.upper() == "TRUE" if hs and hs != "-" else False

            classification = classify_lattice_pin(func_name, bank or "", dual or "", fmt)

            pin_entry = {
                "pin": pin_loc,
                "name": func_name,
                "function": classification["function"],
                "bank": bank,
                "pad": pad if pad and pad != "0" else None,
                "config_function": dual,
                "dqs": dqs,
                "high_speed": is_hs,
                "_diff_raw": diff,  # temporary, used for pair extraction
            }

            # Merge DRC from classification
            if "drc" in classification:
                pin_entry["drc"] = classification["drc"]

            # Polarity from diff column
            if diff:
                if diff.upper().startswith("TRUE_OF_"):
                    pin_entry["polarity"] = "P"
                    pin_entry["diff_complement"] = diff.split("_OF_", 1)[1] if "_OF_" in diff else None
                elif diff.upper().startswith("COMP_OF_"):
                    pin_entry["polarity"] = "N"
                    pin_entry["diff_complement"] = diff.split("_OF_", 1)[1] if "_OF_" in diff else None

            # CrossLink-NX: CUST_NAME
            if fmt == "crosslinknx" and col_cust < len(row):
                cust = row[col_cust].strip()
                if cust and cust != "-":
                    pin_entry["cust_name"] = cust

            pins.append(pin_entry)

        if not pins:
            continue

        # Extract diff pairs
        diff_pairs = extract_diff_pairs(pins)

        # Clean up temporary fields
        for p in pins:
            p.pop("_diff_raw", None)
            p.pop("diff_complement", None)

        # Build bank structure
        bank_structure = build_banks(pins)

        # DRC rules
        drc_rules = {
            "power_integrity": {
                "severity": "ERROR",
                "desc": "All power and ground pins must be connected",
            },
            "config_pins": {
                "severity": "ERROR",
                "desc": "Mandatory config pins (PROGRAMN, INITN, DONE, CCLK) must be connected",
            },
            "vcco_bank_consistency": {
                "severity": "ERROR",
                "desc": "All IO in same bank must use compatible IO standards sharing same VCCIO",
            },
            "diff_pair_integrity": {
                "severity": "ERROR",
                "desc": "Differential pairs must be used together or not at all",
            },
            "unused_io": {
                "severity": "WARNING",
                "desc": "Unused IO pins should not be left floating",
            },
            "jtag_pins": {
                "severity": "WARNING",
                "desc": "JTAG pins (TCK/TMS/TDI/TDO) should be properly connected or have pull resistors",
            },
        }

        # Lookup
        lookup = {
            "pin_to_name": {p["pin"]: p["name"] for p in pins},
            "name_to_pin": {},
            "io_pins": [p["pin"] for p in pins if p["function"] == "IO"],
            "power_pins": [p["pin"] for p in pins if p["function"] in ("POWER", "GROUND")],
            "config_pins": [p["pin"] for p in pins if p["function"] == "CONFIG"],
        }
        name_counts = defaultdict(int)
        for p in pins:
            name_counts[p["name"]] += 1
        for p in pins:
            if name_counts[p["name"]] == 1:
                lookup["name_to_pin"][p["name"]] = p["pin"]

        # Summary
        func_counts = defaultdict(int)
        for p in pins:
            func_counts[p["function"]] += 1

        diff_type_counts = defaultdict(int)
        for dp in diff_pairs:
            diff_type_counts[dp["type"]] += 1

        family = "CrossLink-NX" if fmt == "crosslinknx" else "ECP5"

        result = {
            "_schema_version": "2.0",
            "_purpose": "FPGA pin definition for LLM-driven schematic DRC",
            "_vendor": "Lattice",
            "_family": family,
            "device": device,
            "package": pkg_name,
            "source_file": filepath.name,
            "total_pins": len(pins),
            "summary": {
                "by_function": dict(sorted(func_counts.items())),
                "diff_pairs": dict(sorted(diff_type_counts.items())),
            },
            "power_rails": {},
            "banks": bank_structure,
            "diff_pairs": diff_pairs,
            "drc_rules": drc_rules,
            "pins": pins,
            "lookup": lookup,
        }

        results.append(normalize_fpga_parse_result(result))

    return results


# ─── Main ──────────────────────────────────────────────────────────

def main():
    csv_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV_DIR
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Support both directory and single file
    if csv_dir.is_file():
        csv_files = [csv_dir]
    else:
        csv_files = sorted(csv_dir.glob("*.xlsx")) + sorted(csv_dir.glob("*.csv"))

    if not csv_files:
        print(f"No CSV/XLSX files found in {csv_dir}")
        sys.exit(1)

    print(f"Found {len(csv_files)} Lattice pinout files")

    total = 0
    for f in csv_files:
        print(f"\nParsing {f.name}...")
        try:
            results = parse_lattice_csv(f)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        for result in results:
            safe_name = f"lattice_{result['device']}_{result['package']}".lower()
            safe_name = re.sub(r"[^a-z0-9_-]", "_", safe_name)
            out_path = output_dir / f"{safe_name}.json"
            with open(out_path, "w") as fp:
                json.dump(result, fp, indent=2, ensure_ascii=False)
                fp.write("\n")

            s = result["summary"]
            print(f"  {result['device']} {result['package']}: {result['total_pins']} pins")
            print(f"  Functions: {json.dumps(s['by_function'])}")
            print(f"  Diff pairs: {json.dumps(s['diff_pairs'])}")
            print(f"  Banks: {len(result['banks'])}")
            print(f"  → {out_path}")
            total += 1

    print(f"\nTotal: {total} packages exported")


if __name__ == "__main__":
    main()
