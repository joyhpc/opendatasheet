#!/usr/bin/env python3
"""Parse Xilinx/AMD UltraScale+ package pinout TXT files into structured JSON.

Input:  AMD pinout .txt files (e.g. xcku3pffvb676pkg.txt)
Output: Multi-layer FPGA pin definition JSON for schematic DRC

Layers:
  L1 - Physical Pin Map (pin_number ↔ pin_name, bank, io_type)
  L2 - Pin Classification & Mandatory Connection Rules
  L3 - Bank Structure (IO type, VCCO grouping)
  L4 - Differential Pair Map (auto-derived from P/N naming)
  L5 - DRC Rule Templates

Usage:
    python parse_fpga_pinout.py <pinout_dir> <output_dir>
    python parse_fpga_pinout.py  # uses default paths
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from normalize_fpga_parse import normalize_fpga_parse_result

DEFAULT_PINOUT_DIR = Path(__file__).parent.parent / "data/raw/fpga/pinout"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data/extracted_v2/fpga/pinout"

# UltraScale+ known power rail voltages
POWER_RAILS = {
    "VCCINT": {"voltage": 0.85, "tolerance": "±3%", "desc": "Internal core supply"},
    "VCCBRAM": {"voltage": 0.85, "tolerance": "±3%", "desc": "Block RAM supply"},
    "VCCAUX": {"voltage": 1.8, "tolerance": "±5%", "desc": "Auxiliary supply"},
    "VCCAUX_IO": {"voltage": 1.8, "tolerance": "±5%", "desc": "Auxiliary IO supply (can be 2.0V for HP banks)"},
    "MGTAVCC": {"voltage": 0.9, "tolerance": "±3%", "desc": "GT analog core supply"},
    "MGTAVTT": {"voltage": 1.2, "tolerance": "±5%", "desc": "GT TX/RX termination supply"},
    "MGTVCCAUX": {"voltage": 1.8, "tolerance": "±5%", "desc": "GT auxiliary supply"},
    "VCCADC": {"voltage": 1.8, "tolerance": "±5%", "desc": "XADC supply"},
    "VBATT": {"voltage": 1.5, "tolerance": "1.4V~1.6V", "desc": "Battery backup for encryption key"},
}

# Config pin mandatory connection rules
CONFIG_PIN_RULES = {
    "PROGRAM_B": {"must_connect": True, "pull": "4.7k to VCCO_0", "desc": "Active-low program. Directly or via button to GND."},
    "INIT_B": {"must_connect": True, "pull": "4.7k to VCCO_0", "desc": "Active-low init status / config error indicator."},
    "DONE": {"must_connect": True, "pull": "330R to VCCO_0", "desc": "Config done indicator. Can drive LED."},
    "CCLK": {"must_connect": True, "pull": None, "desc": "Config clock. Master mode: output. Slave mode: input."},
    "M0": {"must_connect": True, "pull": None, "desc": "Mode select bit 0. Tie to VCCO_0 or GND per config mode."},
    "M1": {"must_connect": True, "pull": None, "desc": "Mode select bit 1. Tie to VCCO_0 or GND per config mode."},
    "M2": {"must_connect": True, "pull": None, "desc": "Mode select bit 2. Tie to VCCO_0 or GND per config mode."},
    "D00_MOSI": {"must_connect": True, "pull": None, "desc": "Config data / SPI MOSI."},
    "D01_DIN": {"must_connect": True, "pull": None, "desc": "Config data / serial DIN."},
    "D02": {"must_connect": "mode_dependent", "pull": None, "desc": "Config data bit 2. Required for x4/x8/x16 config modes."},
    "D03": {"must_connect": "mode_dependent", "pull": None, "desc": "Config data bit 3. Required for x4/x8/x16 config modes."},
    "RDWR_FCS_B": {"must_connect": True, "pull": "4.7k to VCCO_0", "desc": "Read/Write select / SPI flash CS."},
    "PUDC_B": {"must_connect": True, "pull": None, "desc": "Pull-up during config. Tie to GND=pull-up, VCCO_0=no pull-up."},
    "TCK": {"must_connect": "recommended", "pull": "4.7k to GND", "desc": "JTAG clock."},
    "TDI": {"must_connect": "recommended", "pull": "4.7k to VCCO_0", "desc": "JTAG data in."},
    "TDO": {"must_connect": "recommended", "pull": None, "desc": "JTAG data out."},
    "TMS": {"must_connect": "recommended", "pull": "4.7k to VCCO_0", "desc": "JTAG mode select."},
    "POR_OVERRIDE": {"must_connect": False, "pull": "NC or GND", "desc": "Power-on reset override. Leave NC or tie GND."},
    "VBATT": {"must_connect": True, "pull": None, "desc": "Battery backup. Tie to 1.5V or VCCAUX if not using encryption."},
}

# Special pin handling rules
SPECIAL_PIN_RULES = {
    "DXP": {"must_connect": False, "desc": "XADC dedicated analog input P. Leave NC if unused."},
    "DXN": {"must_connect": False, "desc": "XADC dedicated analog input N. Leave NC if unused."},
    "GNDADC": {"must_connect": True, "desc": "XADC ground. Must connect to GND."},
    "VCCADC": {"must_connect": True, "desc": "XADC power. Must connect to 1.8V."},
    "VP": {"must_connect": False, "desc": "XADC VP input. Leave NC if unused."},
    "VN": {"must_connect": False, "desc": "XADC VN input. Leave NC if unused."},
    "VREFP": {"must_connect": False, "desc": "XADC VREFP. Leave NC if unused (internal ref)."},
    "VREFN": {"must_connect": False, "desc": "XADC VREFN. Leave NC if unused (internal ref)."},
    "RSVDGND": {"must_connect": True, "desc": "Reserved. MUST connect to GND."},
}


def classify_pin(pin_name: str, io_type: str) -> dict:
    """Classify a pin and return function + DRC metadata."""
    result = {"function": "OTHER", "drc": {}}

    if pin_name.startswith("IO_"):
        result["function"] = "IO"
        # Extract differential info from name
        if "_N_" in pin_name or pin_name.endswith("N"):
            result["polarity"] = "N"
        elif "_P_" in pin_name or pin_name.endswith("P"):
            result["polarity"] = "P"
        else:
            result["polarity"] = None
        # Extract special functions embedded in IO name
        special = []
        if "DBC_" in pin_name:
            special.append("DBC")  # Byte clock capable
        if "AD0" in pin_name:
            special.append("VREF")  # Can be VREF pin
        if "GC_" in pin_name or "QBC_" in pin_name:
            special.append("CLOCK")  # Clock capable
        if "SRCC_" in pin_name:
            special.append("SRCC")  # Single-region clock capable
        if "MRCC_" in pin_name:
            special.append("MRCC")  # Multi-region clock capable
        result["special_functions"] = special if special else None

    elif pin_name.startswith("MGTY") or pin_name.startswith("MGTH"):
        gt_type = "GTY" if pin_name.startswith("MGTY") else "GTH"
        if "RXN" in pin_name or "RXP" in pin_name:
            result["function"] = "GT_RX"
            result["polarity"] = "N" if "RXN" in pin_name else "P"
        elif "TXN" in pin_name or "TXP" in pin_name:
            result["function"] = "GT_TX"
            result["polarity"] = "N" if "TXN" in pin_name else "P"
        else:
            result["function"] = "GT"
        result["gt_type"] = gt_type
        # Extract lane number
        m = re.search(r"[RT]X[NP](\d+)_(\d+)", pin_name)
        if m:
            result["lane"] = int(m.group(1))
            result["gt_bank"] = int(m.group(2))

    elif pin_name.startswith("MGTREFCLK"):
        result["function"] = "GT_REFCLK"
        result["polarity"] = "N" if pin_name.endswith("N") or "CLK0N" in pin_name or "CLK1N" in pin_name else "P"
        m = re.search(r"MGTREFCLK(\d+)[NP]_(\d+)", pin_name)
        if m:
            result["refclk_index"] = int(m.group(1))
            result["gt_bank"] = int(m.group(2))

    elif pin_name.startswith("MGTAVCC"):
        result["function"] = "GT_POWER"
        result["rail"] = "MGTAVCC"
        result["drc"] = {"must_connect": True, "net": "MGTAVCC_0V9"}
    elif pin_name.startswith("MGTAVTT"):
        result["function"] = "GT_POWER"
        result["rail"] = "MGTAVTT"
        result["drc"] = {"must_connect": True, "net": "MGTAVTT_1V2"}
    elif pin_name.startswith("MGTVCCAUX"):
        result["function"] = "GT_POWER"
        result["rail"] = "MGTVCCAUX"
        result["drc"] = {"must_connect": True, "net": "MGTVCCAUX_1V8"}

    elif pin_name.startswith("VCCO_"):
        result["function"] = "POWER"
        result["rail"] = "VCCO"
        m = re.search(r"VCCO_(\d+)", pin_name)
        if m:
            result["power_bank"] = int(m.group(1))
        result["drc"] = {"must_connect": True, "note": "Voltage depends on IO standard used in this bank"}
    elif pin_name.startswith("VCCINT"):
        result["function"] = "POWER"
        result["rail"] = "VCCINT"
        result["drc"] = {"must_connect": True, "net": "VCCINT_0V85"}
    elif pin_name.startswith("VCCBRAM"):
        result["function"] = "POWER"
        result["rail"] = "VCCBRAM"
        result["drc"] = {"must_connect": True, "net": "VCCBRAM_0V85"}
    elif pin_name.startswith("VCCAUX_IO"):
        result["function"] = "POWER"
        result["rail"] = "VCCAUX_IO"
        result["drc"] = {"must_connect": True, "net": "VCCAUX_IO_1V8"}
    elif pin_name.startswith("VCCAUX"):
        result["function"] = "POWER"
        result["rail"] = "VCCAUX"
        result["drc"] = {"must_connect": True, "net": "VCCAUX_1V8"}
    elif "VCC" in pin_name:
        result["function"] = "POWER"
        result["rail"] = pin_name.split("_")[0] if "_" in pin_name else pin_name
        result["drc"] = {"must_connect": True}

    elif pin_name == "GND" or pin_name.startswith("GND"):
        result["function"] = "GROUND"
        result["drc"] = {"must_connect": True, "net": "GND"}
    elif pin_name == "RSVDGND":
        result["function"] = "GROUND"
        result["drc"] = {"must_connect": True, "net": "GND", "critical": True,
                         "note": "Reserved GND - MUST connect to ground"}

    elif io_type == "CONFIG":
        result["function"] = "CONFIG"
        # Match config pin rules
        for key, rule in CONFIG_PIN_RULES.items():
            if key in pin_name:
                result["drc"] = rule
                break

    else:
        # Check special pins
        for key, rule in SPECIAL_PIN_RULES.items():
            if pin_name.startswith(key) or pin_name == key:
                result["function"] = "SPECIAL"
                result["drc"] = rule
                break

    return result


def extract_diff_pairs(pins: list) -> list:
    """Extract differential pairs from pin list."""
    pairs = []

    # IO differential pairs: match P/N by normalizing the full name
    # e.g. IO_L10P_AD10P_87 ↔ IO_L10N_AD10N_87
    # Strategy: replace all P→X and N→X after IO_Lxx to get a canonical base
    io_pins = [p for p in pins if p["function"] == "IO"]
    n_pins = {}
    p_pins = {}

    def io_pair_key(name: str) -> tuple[str, str] | None:
        """Extract (pair_key, polarity) from IO pin name.
        
        Pair matching uses IO_Lxx + bank_suffix only.
        e.g. IO_L10P_T1U_N6_QBC_AD4P_64 → key=("L10", "64"), pol="P"
             IO_L10N_T1U_N7_QBC_AD4N_64 → key=("L10", "64"), pol="N"
        """
        m = re.match(r"IO_(L\d+)([NP])_.*?(\d+)$", name)
        if not m:
            return None
        lane, pol, bank = m.group(1), m.group(2), m.group(3)
        return (f"{lane}_{bank}", pol)

    for pin in io_pins:
        result = io_pair_key(pin["name"])
        if result is None:
            continue
        key, pol = result
        if pol == "N":
            n_pins[key] = pin
        else:
            p_pins[key] = pin

    for base in sorted(set(n_pins.keys()) & set(p_pins.keys())):
        pp = p_pins[base]
        np = n_pins[base]
        pairs.append({
            "type": "IO",
            "pair_name": f"IO_{base}",
            "p_pin": pp["pin"],
            "n_pin": np["pin"],
            "p_name": pp["name"],
            "n_name": np["name"],
            "bank": pp["bank"],
            "io_type": pp["io_type"],
        })

    # GT differential pairs
    gt_rx = [p for p in pins if p["function"] == "GT_RX"]
    gt_tx = [p for p in pins if p["function"] == "GT_TX"]

    for gt_list, direction in [(gt_rx, "RX"), (gt_tx, "TX")]:
        by_lane = {}
        for pin in gt_list:
            m = re.search(r"[RT]X([NP])(\d+)_(\d+)", pin["name"])
            if m:
                pol, lane, bank = m.group(1), m.group(2), m.group(3)
                key = f"{direction}_{lane}_{bank}"
                by_lane.setdefault(key, {})[pol] = pin

        for key in sorted(by_lane.keys()):
            if "P" in by_lane[key] and "N" in by_lane[key]:
                pp = by_lane[key]["P"]
                np = by_lane[key]["N"]
                pairs.append({
                    "type": f"GT_{direction}",
                    "pair_name": key,
                    "p_pin": pp["pin"],
                    "n_pin": np["pin"],
                    "p_name": pp["name"],
                    "n_name": np["name"],
                    "bank": pp["bank"],
                    "io_type": pp["io_type"],
                })

    # GT REFCLK pairs
    refclk_pins = [p for p in pins if p["function"] == "GT_REFCLK"]
    refclk_by_key = {}
    for pin in refclk_pins:
        m = re.search(r"MGTREFCLK(\d+)([NP])_(\d+)", pin["name"])
        if m:
            idx, pol, bank = m.group(1), m.group(2), m.group(3)
            key = f"REFCLK{idx}_{bank}"
            refclk_by_key.setdefault(key, {})[pol] = pin

    for key in sorted(refclk_by_key.keys()):
        if "P" in refclk_by_key[key] and "N" in refclk_by_key[key]:
            pp = refclk_by_key[key]["P"]
            np = refclk_by_key[key]["N"]
            pairs.append({
                "type": "GT_REFCLK",
                "pair_name": key,
                "p_pin": pp["pin"],
                "n_pin": np["pin"],
                "p_name": pp["name"],
                "n_name": np["name"],
                "bank": pp["bank"],
                "io_type": pp["io_type"],
            })

    return pairs


def build_bank_structure(pins: list) -> dict:
    """Build bank-level structure for DRC."""
    banks = defaultdict(lambda: {
        "io_type": None, "pin_count": 0, "io_count": 0,
        "vcco_pins": [], "vref_capable": [], "clock_capable": [],
        "pins": []
    })

    for p in pins:
        if not p.get("bank"):
            continue
        b = banks[p["bank"]]
        b["pin_count"] += 1
        b["pins"].append(p["pin"])

        if p["io_type"] and b["io_type"] is None:
            b["io_type"] = p["io_type"]

        if p["function"] == "IO":
            b["io_count"] += 1
            sf = p.get("special_functions") or []
            if "VREF" in sf:
                b["vref_capable"].append(p["pin"])
            if any(x in sf for x in ("CLOCK", "SRCC", "MRCC")):
                b["clock_capable"].append(p["pin"])

        if p.get("rail") == "VCCO":
            b["vcco_pins"].append(p["pin"])

    # Convert to regular dict and sort
    result = {}
    for bank_id in sorted(banks.keys(), key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else 999)):
        b = banks[bank_id]
        entry = {
            "bank": bank_id,
            "io_type": b["io_type"],
            "total_pins": b["pin_count"],
            "io_pins": b["io_count"],
            "vcco_pin_count": len(b["vcco_pins"]),
            "vref_capable_pins": b["vref_capable"] if b["vref_capable"] else None,
            "clock_capable_pins": b["clock_capable"] if b["clock_capable"] else None,
        }
        # Add bank-type specific DRC rules
        if b["io_type"] == "HP":
            entry["supported_vcco"] = [1.0, 1.2, 1.35, 1.5, 1.8]
            entry["drc_note"] = "HP bank: all IOs in same bank must use compatible IO standards sharing same VCCO"
        elif b["io_type"] == "HD":
            entry["supported_vcco"] = [1.2, 1.5, 1.8, 2.5, 3.3]
            entry["drc_note"] = "HD bank: supports wider voltage range but lower speed"
        elif b["io_type"] == "GTY":
            entry["drc_note"] = "GT bank: dedicated transceiver pins, powered by MGTAVCC/MGTAVTT/MGTVCCAUX"
        result[bank_id] = entry

    return result


def parse_pinout_file(filepath: Path) -> dict:
    """Parse a single AMD pinout TXT file into multi-layer pin definition."""
    lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()

    # Extract metadata from filename
    fname = filepath.stem
    match = re.match(r"(xc\w+?)(ff|fb|sf|fl|fc|cm|cn|ub|vs|sb|sr|fh|fi|fs|fg)(\w+)pkg", fname, re.I)
    if match:
        device = match.group(1).upper()
        package = (match.group(2) + match.group(3)).upper()
    else:
        device = fname
        package = "UNKNOWN"

    pins = []
    header_found = False

    for line in lines:
        line = line.strip().rstrip("\r")
        if line.startswith("--") or not line:
            continue
        if "Pin" in line and "Pin Name" in line and "Bank" in line:
            header_found = True
            continue
        if not header_found:
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        pin_number = parts[0]
        if not re.match(r"^[A-Z]{1,2}\d{1,2}$", pin_number):
            continue

        pin_name = parts[1]
        remaining = line[len(pin_number):].strip()
        remaining = remaining[len(pin_name):].strip()
        fields = re.split(r"\s{2,}", remaining)

        memory_byte_group = fields[0] if len(fields) > 0 else "NA"
        bank = fields[1] if len(fields) > 1 else "NA"
        io_type = fields[2] if len(fields) > 2 else "NA"
        slr = fields[3] if len(fields) > 3 else "NA"

        # Classify with full DRC metadata
        classification = classify_pin(pin_name, io_type)

        pin_entry = {
            "pin": pin_number,
            "name": pin_name,
            "bank": bank if bank != "NA" else None,
            "io_type": io_type if io_type != "NA" else None,
            "memory_byte_group": memory_byte_group if memory_byte_group != "NA" else None,
            "slr": slr if slr != "NA" else None,
        }
        # Merge classification fields
        pin_entry.update(classification)
        # Remove empty drc
        if not pin_entry.get("drc"):
            pin_entry.pop("drc", None)

        pins.append(pin_entry)

    # === Build all layers ===

    # L1: Summary
    func_counts = defaultdict(int)
    for p in pins:
        func_counts[p["function"]] += 1

    # L3: Bank structure
    bank_structure = build_bank_structure(pins)

    # L4: Differential pairs
    diff_pairs = extract_diff_pairs(pins)

    # L5: DRC rule templates
    drc_rules = {
        "power_integrity": {
            "desc": "All power and ground pins must be connected",
            "check": "Every pin with function POWER/GROUND/GT_POWER must have a net assignment",
            "severity": "ERROR",
        },
        "rsvdgnd": {
            "desc": "RSVDGND pins must connect to GND",
            "check": "Pin named RSVDGND must connect to GND net",
            "severity": "ERROR",
        },
        "config_pins": {
            "desc": "Mandatory config pins must be connected",
            "check": "CONFIG pins with must_connect=True must have net assignment",
            "severity": "ERROR",
        },
        "vcco_bank_consistency": {
            "desc": "All IO in same bank must use IO standards compatible with the bank VCCO voltage",
            "check": "For each bank, verify all assigned IO standards require the same VCCO",
            "severity": "ERROR",
        },
        "diff_pair_integrity": {
            "desc": "Differential pairs must be used together or not at all",
            "check": "If one pin of a diff pair is used, the other must also be connected",
            "severity": "ERROR",
        },
        "unused_io": {
            "desc": "Unused IO pins should not be left floating",
            "check": "Unconnected IO pins should have internal pull-up/down configured in bitstream, or be noted",
            "severity": "WARNING",
        },
        "gt_power": {
            "desc": "GT power rails must be connected even if GT not used",
            "check": "MGTAVCC, MGTAVTT, MGTVCCAUX pins must be powered per UG575 recommendations",
            "severity": "ERROR",
        },
        "config_mode_consistency": {
            "desc": "M[2:0] pin levels must match intended configuration mode",
            "check": "M0/M1/M2 net assignments must be consistent with config mode (e.g. SPI: M[2:0]=001)",
            "severity": "ERROR",
        },
    }

    # Build lookup tables
    lookup = {
        "pin_to_name": {p["pin"]: p["name"] for p in pins},
        "name_to_pin": {p["name"]: p["pin"] for p in pins},
        "io_pins": [p["pin"] for p in pins if p["function"] == "IO"],
        "power_pins": [p["pin"] for p in pins if p["function"] in ("POWER", "GROUND", "GT_POWER")],
        "config_pins": [p["pin"] for p in pins if p["function"] == "CONFIG"],
        "gt_pins": [p["pin"] for p in pins if p["function"].startswith("GT")],
    }

    result = {
        "_schema_version": "2.0",
        "_purpose": "FPGA pin definition for LLM-driven schematic DRC",
        "device": device,
        "package": package,
        "source_file": filepath.name,
        "total_pins": len(pins),
        "summary": {
            "by_function": dict(sorted(func_counts.items())),
            "diff_pairs": {
                "IO": len([p for p in diff_pairs if p["type"] == "IO"]),
                "GT_RX": len([p for p in diff_pairs if p["type"] == "GT_RX"]),
                "GT_TX": len([p for p in diff_pairs if p["type"] == "GT_TX"]),
                "GT_REFCLK": len([p for p in diff_pairs if p["type"] == "GT_REFCLK"]),
            },
        },
        "power_rails": POWER_RAILS,
        "banks": bank_structure,
        "diff_pairs": diff_pairs,
        "drc_rules": drc_rules,
        "pins": pins,
        "lookup": lookup,
    }

    return normalize_fpga_parse_result(result)


def main():
    pinout_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PINOUT_DIR
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(pinout_dir.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {pinout_dir}")
        sys.exit(1)

    print(f"Found {len(txt_files)} pinout files in {pinout_dir}")

    for f in txt_files:
        print(f"\nParsing {f.name}...")
        result = parse_pinout_file(f)
        out_path = output_dir / f"{f.stem}.json"
        with open(out_path, "w") as fp:
            json.dump(result, fp, indent=2, ensure_ascii=False)
            fp.write("\n")

        s = result["summary"]
        dp = s["diff_pairs"]
        print(f"  {result['device']} {result['package']}: {result['total_pins']} pins")
        print(f"  Functions: {json.dumps(s['by_function'])}")
        print(f"  Diff pairs: IO={dp['IO']} GT_RX={dp['GT_RX']} GT_TX={dp['GT_TX']} REFCLK={dp['GT_REFCLK']}")
        print(f"  Banks: {len(result['banks'])}")
        print(f"  → {out_path}")


if __name__ == "__main__":
    main()
