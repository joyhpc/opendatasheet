#!/usr/bin/env python3
"""Extract DC electrical characteristics from Lattice FPGA datasheets.

Supports:
  - ECP5/ECP5-5G Family Data Sheet (FPGA-DS-02012)
  - CrossLink-NX Family Data Sheet (FPGA-DS-02049)

Uses PyMuPDF text extraction with structured table parsing.

Output: JSON compatible with sch-review export pipeline.

Usage:
    python extract_lattice_dc.py [pdf_path_or_dir] [output_dir]
    python extract_lattice_dc.py /tmp/ecp5_ds.pdf
"""

import json
import re
import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    print("pip install PyMuPDF")
    sys.exit(1)

DEFAULT_INPUT_DIR = Path(__file__).parent.parent / "data/raw/fpga/lattice"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data/extracted_v2/fpga"


def parse_number(s: str) -> float | None:
    """Parse a numeric value from text, handling '–0.5', '+125', '—' etc."""
    if not s:
        return None
    s = s.strip().replace("–", "-").replace("—", "").replace("\u2013", "-")
    if not s or s == "-":
        return None
    m = re.search(r"(-?\+?\d+\.?\d*)", s)
    return float(m.group(1)) if m else None


def detect_family(doc) -> str:
    """Detect ECP5 vs CrossLink-NX from PDF content."""
    first_page = doc[0].get_text()
    if "CrossLink-NX" in first_page:
        return "crosslinknx"
    elif "ECP5" in first_page:
        return "ecp5"
    return "unknown"


def find_section_pages(doc) -> dict:
    """Find page ranges for DC sections from TOC."""
    toc = doc.get_toc()
    sections = {}
    for level, title, page in toc:
        pg = page - 1  # 0-indexed
        title_lower = title.lower()
        if "absolute maximum" in title_lower:
            if "abs_max" not in sections:
                sections["abs_max"] = pg
        elif "recommended operating" in title_lower and "sysi/o" not in title_lower:
            if "recommended" not in sections:
                sections["recommended"] = pg
        elif "dc electrical" in title_lower:
            if "dc_elec" not in sections:
                sections["dc_elec"] = pg
        elif "supply current" in title_lower:
            if "supply_current" not in sections:
                sections["supply_current"] = pg
        elif "serdes" in title_lower and "power supply" in title_lower:
            sections["serdes_power"] = pg
        elif "sysi/o recommended" in title_lower:
            if "sysio_rec" not in sections:
                sections["sysio_rec"] = pg
        elif "single-ended" in title_lower and "dc" in title_lower:
            if "single_ended" not in sections:
                sections["single_ended"] = pg
        elif "differential" in title_lower and ("dc" in title_lower or "electrical" in title_lower):
            if "differential" not in sections:
                sections["differential"] = pg
        elif "esd" in title_lower:
            sections["esd"] = pg
        elif "hot socketing" in title_lower and "spec" in title_lower:
            sections["hot_socket"] = pg
    return sections


# ─── Table Parsers ─────────────────────────────────────────────────

def parse_abs_max_table(doc, start_page: int, end_page: int) -> list[dict]:
    """Parse Absolute Maximum Ratings table.

    Lattice format (line by line from PyMuPDF):
        Symbol
        Parameter
        Min
        Max
        Unit
        VCC
        Supply Voltage
        –0.5
        1.32
        V
    """
    results = []
    text = ""
    for pg in range(start_page, min(end_page, doc.page_count)):
        text += doc[pg].get_text() + "\n"

    lines = [l.strip() for l in text.split("\n")]

    # Find table header
    i = 0
    while i < len(lines):
        if lines[i] == "Symbol":
            # Skip header fields
            while i < len(lines) and lines[i] in ("Symbol", "Parameter", "Min", "Max", "Unit", ""):
                i += 1
            break
        i += 1

    # Parse rows: Symbol, Parameter, Min, Max, Unit
    while i < len(lines):
        line = lines[i]

        # Stop conditions
        if not line:
            i += 1
            continue
        if line.startswith("Notes:") or line.startswith("Note:"):
            break
        if re.match(r"^3\.\d+\.", line) and "Absolute" not in line:
            break

        # Skip page headers/footers
        if "Lattice Semiconductor" in line or "Data Sheet" in line or "FPGA-DS-" in line:
            i += 1
            continue
        if re.match(r"^\d+$", line) and int(line) < 200:
            i += 1
            continue

        # Symbol line: starts with letter or "—"
        symbol = line

        # Collect parameter text
        j = i + 1
        param_parts = []
        while j < len(lines):
            l = lines[j]
            if not l:
                j += 1
                continue
            # Is this a numeric value?
            cleaned = l.replace("–", "-").replace("\u2013", "-").replace("+", "")
            if re.match(r"^-?\d+\.?\d*$", cleaned):
                break
            if l == "—":
                break
            if l in ("V", "°C", "mA", "µA"):
                break
            # Stop if it looks like a new section
            if l.startswith("Notes:") or l.startswith("Note:") or re.match(r"^3\.\d+\.", l):
                break
            # Skip page headers
            if "Lattice Semiconductor" in l or "Data Sheet" in l or "FPGA-DS-" in l:
                j += 1
                continue
            if re.match(r"^\d+$", l) and int(l) < 200:
                j += 1
                continue
            param_parts.append(l)
            j += 1

        parameter = " ".join(param_parts)

        # Collect min, max, unit
        min_val = None
        max_val = None
        unit = None

        # Min
        if j < len(lines):
            l = lines[j]
            if l == "—":
                min_val = None
                j += 1
            else:
                min_val = parse_number(l)
                if min_val is not None:
                    j += 1

        # Max
        if j < len(lines):
            l = lines[j]
            if l == "—":
                max_val = None
                j += 1
            else:
                max_val = parse_number(l)
                if max_val is not None:
                    j += 1

        # Unit
        if j < len(lines):
            u = lines[j]
            if u in ("V", "°C", "mA", "µA", "A"):
                unit = u
                j += 1

        if parameter and (min_val is not None or max_val is not None) and unit:
            results.append({
                "symbol": symbol if symbol != "—" else None,
                "parameter": parameter,
                "min": min_val,
                "max": max_val,
                "unit": unit,
            })

        i = j if j > i else i + 1

    return results


def parse_recommended_table(doc, start_page: int, end_page: int) -> list[dict]:
    """Parse Recommended Operating Conditions table.

    Format: Symbol | Parameter | [Conditions] | Min | [Typ] | Max | Unit
    Some rows have sub-conditions (e.g. ECP5 / ECP5-5G variants).
    """
    results = []
    text = ""
    for pg in range(start_page, min(end_page, doc.page_count)):
        text += doc[pg].get_text() + "\n"

    lines = [l.strip() for l in text.split("\n")]

    # Find table header — must be after "Recommended Operating" section title
    i = 0
    found_section = False
    while i < len(lines):
        if "Recommended Operating" in lines[i] or "Recommended operating" in lines[i]:
            found_section = True
        if found_section and lines[i] == "Symbol":
            while i < len(lines) and lines[i] in ("Symbol", "Parameter", "Min", "Max", "Typ", "Typ.", "Unit", "Conditions", ""):
                i += 1
            break
        i += 1

    # Parse rows
    while i < len(lines):
        line = lines[i]

        if not line:
            i += 1
            continue

        # Stop conditions
        if line.startswith("Notes:") or line.startswith("Note:"):
            break
        if re.match(r"^3\.\d+\.", line) and "Recommended" not in line:
            break

        # Skip page headers
        if "Lattice Semiconductor" in line or "Data Sheet" in line or "FPGA-DS-" in line:
            i += 1
            continue
        if re.match(r"^\d+$", line) and int(line) < 200:
            i += 1
            continue

        # Symbol line
        symbol = line

        # Collect parameter + conditions text
        j = i + 1
        param_parts = []
        while j < len(lines):
            l = lines[j]
            if not l:
                j += 1
                continue
            cleaned = l.replace("–", "-").replace("\u2013", "-").replace("+", "")
            if re.match(r"^-?\d+\.?\d*$", cleaned):
                break
            if l == "—":
                break
            if l in ("V", "°C", "mA", "µA", "V/ms"):
                break
            if l.startswith("Notes:") or l.startswith("Note:") or re.match(r"^3\.\d+\.", l):
                break
            if "Lattice Semiconductor" in l or "Data Sheet" in l or "FPGA-DS-" in l:
                j += 1
                continue
            if re.match(r"^\d+$", l) and int(l) < 200:
                j += 1
                continue
            param_parts.append(l)
            j += 1

        parameter = " ".join(param_parts)

        # Collect numeric values (min, [typ], max)
        values = []
        while j < len(lines) and len(values) < 4:
            l = lines[j]
            if l == "—":
                values.append(None)
                j += 1
                continue
            num = parse_number(l)
            if num is not None and re.match(r"^[–\-+]?\d+\.?\d*$", l.replace("–", "-").replace("\u2013", "-").replace("+", "")):
                values.append(num)
                j += 1
                continue
            break

        # Unit
        unit = None
        if j < len(lines):
            u = lines[j]
            if u in ("V", "°C", "mA", "µA", "V/ms"):
                unit = u
                j += 1

        if parameter and values and unit:
            min_v = max_v = typ_v = None
            if len(values) == 2:
                min_v, max_v = values
            elif len(values) == 3:
                min_v, typ_v, max_v = values
            elif len(values) == 1:
                max_v = values[0]

            # Clean symbol
            sym = re.sub(r"[\d,\s]+$", "", symbol).strip()

            results.append({
                "symbol": sym if sym and sym != "—" else None,
                "parameter": parameter,
                "min": min_v,
                "typ": typ_v,
                "max": max_v,
                "unit": unit,
            })

        i = j if j > i else i + 1

    return results


def parse_sysio_table(doc, start_page: int, end_page: int) -> list[dict]:
    """Parse sysI/O Recommended Operating Conditions and DC characteristics.

    Extracts IO standard voltage levels (VCCO, VIH, VIL, VOH, VOL).
    """
    results = []
    for pg in range(start_page, min(end_page, doc.page_count)):
        text = doc[pg].get_text()
        lines = text.split("\n")

        current_standard = None
        for line in lines:
            line = line.strip()

            # Detect IO standard names
            for std in ["LVCMOS33", "LVCMOS25", "LVCMOS18", "LVCMOS15", "LVCMOS12",
                        "LVCMOS10", "LVTTL33",
                        "SSTL25", "SSTL18", "SSTL15", "SSTL135",
                        "HSTL18", "HSTL15", "HSUL12",
                        "LVDS25", "LVDS", "LVDS_25",
                        "BLVDS25", "LVPECL33", "MLVDS25", "SLVS",
                        "LVCMOS33D", "LVCMOS25D", "LVTTL33D",
                        "PCI33", "SubLVDS"]:
                if std.upper() in line.upper().replace(" ", ""):
                    current_standard = std
                    break

            # Capture VCCO values
            if current_standard and "VCCIO" in line.upper():
                v = parse_number(line)
                if v is not None:
                    results.append({
                        "standard": current_standard,
                        "parameter": "VCCO",
                        "value": v,
                        "raw": line,
                    })

            # Capture VIH, VIL, VOH, VOL
            for param in ["VIH", "VIL", "VOH", "VOL"]:
                if param in line and current_standard:
                    v = parse_number(line)
                    if v is not None:
                        results.append({
                            "standard": current_standard,
                            "parameter": param,
                            "value": v,
                            "raw": line,
                        })

    return results


# ─── Main Extractor ────────────────────────────────────────────────

def extract_lattice_dc(filepath: Path) -> dict:
    """Extract DC characteristics from a Lattice FPGA datasheet PDF."""
    doc = fitz.open(str(filepath))
    family = detect_family(doc)
    sections = find_section_pages(doc)

    # Determine device/family name
    if family == "ecp5":
        device = "ECP5"
    elif family == "crosslinknx":
        device = "CrossLink-NX"
    else:
        device = filepath.stem

    result = {
        "device": device,
        "family": family,
        "source_file": filepath.name,
        "absolute_maximum_ratings": [],
        "recommended_operating": [],
        "io_standards": [],
    }

    # --- Absolute Maximum Ratings ---
    if "abs_max" in sections:
        start = sections["abs_max"]
        end = sections.get("recommended", sections.get("esd", start + 2))
        # Ensure at least 1 page is read
        if end <= start:
            end = start + 1
        result["absolute_maximum_ratings"] = parse_abs_max_table(doc, start, end)

    # --- Recommended Operating Conditions ---
    if "recommended" in sections:
        start = sections["recommended"]
        end = sections.get("hot_socket", sections.get("esd", sections.get("dc_elec", start + 3)))
        if end <= start:
            end = start + 2
        result["recommended_operating"] = parse_recommended_table(doc, start, end)

    # --- sysI/O specs ---
    io_start = sections.get("sysio_rec", sections.get("single_ended"))
    if io_start is not None:
        end = sections.get("differential", io_start + 4)
        result["io_standards"] = parse_sysio_table(doc, io_start, end)

    # Also grab differential IO specs
    if "differential" in sections:
        diff_start = sections["differential"]
        diff_end = diff_start + 8
        diff_io = parse_sysio_table(doc, diff_start, diff_end)
        result["io_standards"].extend(diff_io)

    doc.close()
    return result


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT_DIR
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    if input_path.is_file():
        pdf_files = [input_path]
    else:
        pdf_files = sorted(input_path.glob("*_ds.pdf")) + sorted(input_path.glob("*_ds*.pdf"))

    if not pdf_files:
        print(f"No datasheet PDFs found in {input_path}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} Lattice datasheet PDFs")

    for f in pdf_files:
        print(f"\nExtracting {f.name}...")
        result = extract_lattice_dc(f)

        dev = result["device"].lower().replace(" ", "_").replace("-", "_")
        safe_name = f"lattice_{dev}_dc"
        safe_name = re.sub(r"[^a-z0-9_-]", "", safe_name)
        out_path = output_dir / f"{safe_name}.json"
        with open(out_path, "w") as fp:
            json.dump(result, fp, indent=2, ensure_ascii=False)

        print(f"  Device: {result['device']}")
        print(f"  Abs max: {len(result['absolute_maximum_ratings'])} entries")
        print(f"  Recommended: {len(result['recommended_operating'])} entries")
        print(f"  IO standards: {len(result['io_standards'])} entries")
        print(f"  → {out_path}")


if __name__ == "__main__":
    main()
