#!/usr/bin/env python3
"""Unified FPGA pinout parser — auto-detects vendor/format and outputs schema v2.0 JSON.

Supported formats:
  - AMD/Xilinx TXT pinout files (from download.amd.com)
  - Gowin XLSX pinout files (from gowin.com)
  - Gowin PDF pinout files (UG1224-style)
  - Lattice CSV pinout files (ECP5, CrossLink-NX)

Usage:
    python parse_pinout.py <input_file> [-o output.json]
    python parse_pinout.py xcku3pffva676pkg.txt
    python parse_pinout.py UG1222-1.1_GW5AT-60器件Pinout手册.xlsx
    python parse_pinout.py UG1224-1.2_GW5AT-15器件Pinout手册.pdf
    python parse_pinout.py ecp5u25_pinout.xlsx -f lattice_csv
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def detect_format(input_path: Path) -> str:
    """Detect input format from file extension and content."""
    suffix = input_path.suffix.lower()
    name = input_path.name.lower()

    if suffix == ".txt":
        # AMD TXT format: first lines contain "Device/Package" or similar
        return "amd_txt"
    elif suffix == ".xlsx":
        # Check if it's a Lattice CSV disguised as .xlsx
        try:
            first_line = input_path.read_text(encoding="utf-8", errors="replace").split("\n")[0]
            if first_line.startswith("#") and ("Pin Out" in first_line or "ECP5" in first_line or "LIFCL" in first_line):
                return "lattice_csv"
        except Exception:
            pass
        return "gowin_xlsx"
    elif suffix == ".csv":
        return "lattice_csv"
    elif suffix == ".pdf":
        return "gowin_pdf"
    else:
        raise ValueError(f"Unknown file format: {suffix} (expected .txt, .xlsx, .csv, or .pdf)")


def parse_amd_txt(input_path: Path) -> dict:
    """Parse AMD/Xilinx TXT pinout file."""
    sys.path.insert(0, str(SCRIPT_DIR))
    from parse_fpga_pinout import parse_pinout_file, build_schema_v2
    raw_pins = parse_pinout_file(str(input_path))
    return build_schema_v2(raw_pins, str(input_path))


def parse_gowin_xlsx(input_path: Path) -> dict:
    """Parse Gowin XLSX pinout file."""
    sys.path.insert(0, str(SCRIPT_DIR))
    from parse_gowin_pinout import parse_gowin_pinout
    return parse_gowin_pinout(str(input_path))


def parse_gowin_pdf(input_path: Path) -> dict:
    """Parse Gowin PDF pinout file."""
    sys.path.insert(0, str(SCRIPT_DIR))
    from parse_gowin_pinout_pdf import parse_gowin_pdf_pinout
    results = parse_gowin_pdf_pinout(str(input_path))
    if not results:
        raise ValueError(f"No pinout data found in {input_path}")
    # PDF parser returns list of (package_name, data) — return first or all
    if len(results) == 1:
        return results[0][1]
    # Multiple packages: return dict keyed by package
    return {pkg: data for pkg, data in results}


def parse_lattice_csv(input_path: Path) -> dict:
    """Parse Lattice CSV pinout file."""
    sys.path.insert(0, str(SCRIPT_DIR))
    from parse_lattice_pinout import parse_lattice_csv as _parse
    results = _parse(input_path)
    if not results:
        raise ValueError(f"No pinout data found in {input_path}")
    if len(results) == 1:
        return results[0]
    # Multiple packages: return dict keyed by package
    return {r["package"]: r for r in results}


def main():
    parser = argparse.ArgumentParser(description="Unified FPGA pinout parser")
    parser.add_argument("input", help="Input pinout file (.txt, .xlsx, .csv, .pdf)")
    parser.add_argument("-o", "--output", help="Output JSON path (default: auto-named)")
    parser.add_argument("-f", "--format", choices=["amd_txt", "gowin_xlsx", "gowin_pdf", "lattice_csv"],
                        help="Force input format (auto-detected if omitted)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    fmt = args.format or detect_format(input_path)
    print(f"Detected format: {fmt}")

    PARSERS = {
        "amd_txt": parse_amd_txt,
        "gowin_xlsx": parse_gowin_xlsx,
        "gowin_pdf": parse_gowin_pdf,
        "lattice_csv": parse_lattice_csv,
    }

    result = PARSERS[fmt](input_path)

    # Determine output path
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = input_path.with_suffix(".json")

    # Handle multi-package PDF results
    if isinstance(result, dict) and "_schema_version" not in result and "pins" not in result:
        # Multiple packages — write each separately
        for pkg_name, pkg_data in result.items():
            pkg_out = out_path.parent / f"{out_path.stem}_{pkg_name}.json"
            with open(pkg_out, "w") as f:
                json.dump(pkg_data, f, indent=2, ensure_ascii=False)
            n_pins = len(pkg_data.get("pins", []))
            print(f"  {pkg_name}: {n_pins} pins → {pkg_out}")
    else:
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        n_pins = len(result.get("pins", []))
        device = result.get("device", "?")
        package = result.get("package", "?")
        print(f"  {device} {package}: {n_pins} pins → {out_path}")


if __name__ == "__main__":
    main()
