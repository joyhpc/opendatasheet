#!/usr/bin/env python3
"""Extract DC electrical characteristics from Gowin FPGA datasheets.

Gowin datasheets are in Chinese with structured tables.
Uses PyMuPDF text extraction (no Vision API needed).

PyMuPDF extracts table cells as separate lines, so we use a
state-machine approach to group (name, description, min, max) tuples.

Output: JSON compatible with sch-review export pipeline.
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

DEFAULT_INPUT_DIR = Path(__file__).parent.parent / "data/raw/fpga/gowin/高云 FPGA"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data/extracted_v2/fpga"


def parse_voltage(s: str) -> float | None:
    """Parse voltage string like '0.87V', '-0.5V', '3.465V'."""
    if not s:
        return None
    m = re.search(r"(-?\d+\.?\d*)\s*V", s)
    return float(m.group(1)) if m else None


def parse_temp(s: str) -> float | None:
    """Parse temperature like '-40℃', '+125℃'."""
    m = re.search(r"(-?\+?\d+)\s*[℃°]", s)
    return float(m.group(1)) if m else None


def is_voltage_line(s: str) -> bool:
    """Check if line is a voltage value like '-0.5V', '1.05V'."""
    return bool(re.match(r"^\s*-?\d+\.?\d*\s*V\s*$", s.strip()))


def is_param_name(s: str) -> bool:
    """Check if line looks like a parameter name (VCC, VCCIO, etc.)."""
    s = s.strip()
    if not s:
        return False
    # Known parameter names
    known = {"VCC", "VCCIO", "VCCX", "VCC_REG", "VIN", "Vddha", "Vdda",
             "Vddd", "Vddt", "Vddx", "VDDA_MIPI", "VDDX_MIPI", "VDDD_MIPI"}
    if s in known:
        return True
    # Pattern: starts with V and has uppercase
    if re.match(r"^V[A-Za-z_]+", s) and len(s) < 20:
        return True
    # Vddd_ln0~4 pattern
    if re.match(r"^V\w+", s) and len(s) < 20:
        return True
    return False


def extract_tables_from_pages(doc, start_page: int, end_page: int) -> str:
    """Extract text from a range of pages."""
    texts = []
    for pg in range(start_page, min(end_page, doc.page_count)):
        texts.append(doc[pg].get_text())
    return "\n".join(texts)


def parse_abs_max_tables(text: str, device_filter: str = None) -> list[dict]:
    """Parse absolute maximum ratings tables from text.

    Text format (each cell on its own line):
        名称
        描述
        最小值
        最大值
        FPGA Logic
        VCC
        核电压
        -0.5V
        1.05V
    """
    results = []
    lines = text.split("\n")
    current_section = ""
    current_device = ""
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Stop at recommended operating section header (not table headers)
        # Section header: "3.1.2 推荐工作范围" — no parentheses
        # Table header: "表3-3 推荐工作范围(GW5AT-138 / GW5AT-75)" — has parentheses
        if "推荐工作范围" in line and "绝对" not in line and "DC" not in line and "表" not in line:
            break

        # Detect device-specific table headers
        if "绝对最大范围" in line:
            # Extract device from parentheses: 绝对最大范围(GW5AT-60)
            m = re.search(r"\(([^)]+)\)", line)
            if m:
                current_device = m.group(1)
            i += 1
            continue

        # Table header row — skip
        if line in ("名称", "描述", "最小值", "最大值"):
            i += 1
            continue

        # Section headers
        if line in ("FPGA Logic", "Gigabit Transceiver", "MIPI", "温度"):
            current_section = line
            i += 1
            continue

        # Skip non-content
        if not line or "DS981" in line or "DS1225" in line or "Preliminary" in line:
            i += 1
            continue
        if re.match(r"^\d+\(\d+\)$", line):  # page numbers like "46(64)"
            i += 1
            continue
        if line.startswith("3 电气特性") or line.startswith("3.1"):
            i += 1
            continue
        if "注！" in line or "建议在推荐" in line or "仅供参考" in line:
            i += 1
            continue

        # Try to parse a parameter entry
        if is_param_name(line):
            name = line
            # Collect description lines until we hit a voltage
            desc_parts = []
            j = i + 1
            while j < len(lines) and not is_voltage_line(lines[j].strip()):
                l = lines[j].strip()
                if not l or is_param_name(l):
                    break
                if "推荐工作范围" in l or "电源上升" in l or "热插拔" in l:
                    break
                desc_parts.append(l)
                j += 1

            # Now expect min voltage
            if j < len(lines) and is_voltage_line(lines[j].strip()):
                vmin = parse_voltage(lines[j].strip())
                j += 1
                # Expect max voltage
                if j < len(lines) and is_voltage_line(lines[j].strip()):
                    vmax = parse_voltage(lines[j].strip())
                    j += 1

                    desc = " ".join(desc_parts)
                    results.append({
                        "parameter": name,
                        "description": desc,
                        "min": vmin,
                        "max": vmax,
                        "unit": "V",
                        "section": current_section,
                        "device": current_device,
                    })
                    i = j
                    continue
            # Didn't match voltage pattern, skip
            i += 1
            continue

        # Temperature entries
        if current_section == "温度" or "Temperature" in line or "温" in line:
            tmin = parse_temp(line)
            if tmin is not None:
                # This is a temperature value, look back for name
                i += 1
                continue
            # Check if this is a temp name line
            if "Temperature" in line or "结温" in line or "储存温度" in line:
                name = line
                desc = ""
                j = i + 1
                # Next line might be Chinese description
                if j < len(lines):
                    l = lines[j].strip()
                    if "温" in l and not re.search(r"[℃°]", l):
                        desc = l
                        j += 1
                # Now expect min temp
                if j < len(lines):
                    tmin = parse_temp(lines[j].strip())
                    j += 1
                    if j < len(lines):
                        tmax = parse_temp(lines[j].strip())
                        j += 1
                        if tmin is not None and tmax is not None:
                            results.append({
                                "parameter": name,
                                "description": desc,
                                "min": tmin,
                                "max": tmax,
                                "unit": "℃",
                                "section": "温度",
                                "device": current_device,
                            })
                            i = j
                            continue

        i += 1

    return results


def parse_recommended_tables(text: str) -> list[dict]:
    """Parse recommended operating conditions tables."""
    results = []
    lines = text.split("\n")
    current_section = ""
    current_device = ""
    active = False  # Only start parsing after seeing "推荐工作范围"
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Detect device-specific table — activate parsing
        if "推荐工作范围" in line and "DC" not in line:
            m = re.search(r"\(([^)]+)\)", line)
            if m:
                current_device = m.group(1)
            active = True
            current_section = ""
            i += 1
            continue

        # Don't parse until we've seen the first 推荐工作范围 header
        if not active:
            i += 1
            continue

        # Table header — skip
        if line in ("名称", "描述", "最小值", "最大值"):
            i += 1
            continue

        # Section headers
        if line in ("FPGA Logic", "Gigabit Transceiver", "MIPI"):
            current_section = line
            i += 1
            continue

        # Stop conditions
        if "电源上升" in line or "热插拔" in line or "ESD" in line:
            break

        # Skip non-content
        if not line or "DS981" in line or "DS1225" in line or "Preliminary" in line:
            i += 1
            continue
        if re.match(r"^\d+\(\d+\)$", line):
            i += 1
            continue
        if line.startswith("3") and ("电气" in line or "工作条件" in line):
            i += 1
            continue
        if "注！" in line or re.match(r"^\[[\d]\]", line):
            i += 1
            continue
        # Skip lines that reference other docs
        if "不同封装" in line or "请参考" in line:
            i += 1
            continue

        # Try to parse parameter
        if is_param_name(line):
            name = line
            # Strip footnote markers like VCC_REG[1]
            name = re.sub(r"\[\d+\]", "", name).strip()
            desc_parts = []
            j = i + 1
            while j < len(lines) and not is_voltage_line(lines[j].strip()):
                l = lines[j].strip()
                if not l or is_param_name(l):
                    break
                if "电源上升" in l or "热插拔" in l or "ESD" in l:
                    break
                if "推荐工作范围" in l:
                    break
                # Skip footnote refs in description
                if re.match(r"^\[\d+\]", l):
                    j += 1
                    continue
                desc_parts.append(l)
                j += 1

            if j < len(lines) and is_voltage_line(lines[j].strip()):
                vmin = parse_voltage(lines[j].strip())
                j += 1
                if j < len(lines) and is_voltage_line(lines[j].strip()):
                    vmax = parse_voltage(lines[j].strip())
                    j += 1
                    desc = " ".join(desc_parts)
                    results.append({
                        "parameter": name,
                        "description": desc,
                        "min": vmin,
                        "max": vmax,
                        "unit": "V",
                        "section": current_section,
                        "device": current_device,
                    })
                    i = j
                    continue

        i += 1

    return results


def parse_dc_characteristics(text: str) -> list[dict]:
    """Parse DC electrical characteristics (supply current, etc.)."""
    results = []
    lines = text.split("\n")
    current_device = ""
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Device-specific table
        if "DC电气特性" in line.replace(" ", "") or "推荐工作范围的DC" in line:
            m = re.search(r"\(([^)]+)\)", line)
            if m:
                current_device = m.group(1)
            i += 1
            continue

        # Look for current values (supply current entries)
        m_current = re.search(r"(-?\d+\.?\d*)\s*(uA|µA|mA|nA|A)\b", line)
        if m_current:
            results.append({
                "raw": line,
                "device": current_device,
            })

        i += 1

    return results


def parse_io_dc_specs(doc, start_page: int, end_page: int) -> list[dict]:
    """Parse single-ended and differential IO DC specs from pages."""
    results = []

    for pg in range(start_page, min(end_page, doc.page_count)):
        text = doc[pg].get_text()
        lines = text.split("\n")
        current_standard = None
        current_device = ""

        for line in lines:
            line = line.strip()

            # Detect device context
            m = re.search(r"\(([^)]+)\)", line)
            if m and "GW5AT" in m.group(1):
                current_device = m.group(1)

            # Detect IO standard
            for std in ["LVCMOS33", "LVCMOS25", "LVCMOS18", "LVCMOS15", "LVCMOS12",
                        "SSTL25", "SSTL18", "SSTL15", "SSTL135",
                        "HSTL18", "HSTL15",
                        "LVDS25", "LVDS", "LVDS_25",
                        "RSDS", "PPDS", "BLVDS", "Mini_LVDS",
                        "PCI33"]:
                if std.lower() in line.lower().replace(" ", ""):
                    current_standard = std
                    break

            # Capture VCCO info
            if current_standard and "VCCIO" in line.upper():
                v = parse_voltage(line)
                if v is not None:
                    results.append({
                        "standard": current_standard,
                        "vcco": v,
                        "raw": line,
                        "device": current_device,
                    })

            # Capture voltage thresholds (VIH, VIL, VOH, VOL)
            for param in ["VIH", "VIL", "VOH", "VOL"]:
                if param in line and current_standard:
                    v = parse_voltage(line)
                    if v is not None:
                        results.append({
                            "standard": current_standard,
                            "parameter": param,
                            "value": v,
                            "raw": line,
                            "device": current_device,
                        })

    return results


def extract_gowin_dc(filepath: Path) -> dict:
    """Extract DC characteristics from a Gowin FPGA datasheet PDF."""
    doc = fitz.open(str(filepath))
    toc = doc.get_toc()

    # Identify device from filename
    fname = filepath.stem
    m = re.search(r"(GW5\w+[-\d]*|Arora[_ ]?V[_ ]?\d*K?)", fname)
    device = m.group(1).replace("_", " ") if m else fname

    # Find relevant page ranges from TOC
    sections = {}
    all_pages = []
    for level, title, page in toc:
        all_pages.append((title, page))
        if "绝对最大" in title:
            sections["abs_max"] = page - 1
        elif "推荐工作范围" in title and "DC" not in title and "I/O" not in title:
            sections["recommended"] = page - 1
        elif "DC" in title.replace(" ", "") and "电气特性" in title:
            if "推荐工作范围" in title:
                sections["dc_recommended"] = page - 1
            elif "I/O推荐" in title or "I/O 推荐" in title:
                sections["io_recommended"] = page - 1
            elif "单端" in title:
                sections["single_ended"] = page - 1
            elif "差分" in title:
                sections["differential"] = page - 1
            else:
                sections["dc_general"] = page - 1
        elif "Transceiver" in title and ("DC" in title or "特性" in title):
            sections["transceiver"] = page - 1
        elif "ESD" in title:
            sections["esd"] = page - 1

    result = {
        "device": device,
        "source_file": filepath.name,
        "absolute_maximum_ratings": [],
        "recommended_operating": [],
        "dc_characteristics": [],
        "io_standards": [],
    }

    # --- Extract Absolute Maximum Ratings ---
    if "abs_max" in sections:
        start = sections["abs_max"]
        # Include the recommended page too — GW5AT-60 abs_max table may be
        # at the top of the page where recommended starts
        end = sections.get("recommended", sections.get("esd", start + 4))
        end = end + 1  # inclusive of the boundary page
        text = extract_tables_from_pages(doc, start, end)
        result["absolute_maximum_ratings"] = parse_abs_max_tables(text)

    # --- Extract Recommended Operating Conditions ---
    if "recommended" in sections:
        start = sections["recommended"]
        end = sections.get("esd", sections.get("dc_general", start + 4))
        text = extract_tables_from_pages(doc, start, end)
        result["recommended_operating"] = parse_recommended_tables(text)

    # --- Extract DC Electrical Characteristics ---
    dc_start = sections.get("dc_general", sections.get("dc_recommended"))
    if dc_start is not None:
        end = sections.get("io_recommended", sections.get("single_ended", dc_start + 3))
        text = extract_tables_from_pages(doc, dc_start, end)
        result["dc_characteristics"] = parse_dc_characteristics(text)

    # --- Extract IO Standards ---
    io_start = sections.get("single_ended", sections.get("io_recommended"))
    if io_start is not None:
        end = sections.get("transceiver", io_start + 6)
        result["io_standards"] = parse_io_dc_specs(doc, io_start, end)

    doc.close()
    return result


def main():
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT_DIR
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    ds_files = sorted([f for f in input_dir.glob("DS*.pdf")])
    if not ds_files:
        print(f"No DS*.pdf files found in {input_dir}")
        sys.exit(1)

    print(f"Found {len(ds_files)} Gowin datasheet PDFs")

    for f in ds_files:
        print(f"\nExtracting {f.name}...")
        result = extract_gowin_dc(f)

        # Clean device name
        dev = result["device"]
        dev = re.sub(r"[系列].*", "", dev).strip()
        if not dev:
            dev = result["device"]
        result["device"] = dev

        safe_name = f"gowin_{dev.replace(' ', '_').replace('-', '-').lower()}"
        safe_name = re.sub(r"[^a-z0-9_-]", "", safe_name)
        out_path = output_dir / f"{safe_name}_dc.json"
        with open(out_path, "w") as fp:
            json.dump(result, fp, indent=2, ensure_ascii=False)

        print(f"  Device: {result['device']}")
        print(f"  Abs max: {len(result['absolute_maximum_ratings'])} entries")
        print(f"  Recommended: {len(result['recommended_operating'])} entries")
        print(f"  DC chars: {len(result['dc_characteristics'])} entries")
        print(f"  IO standards: {len(result['io_standards'])} entries")
        print(f"  → {out_path}")


if __name__ == "__main__":
    main()
