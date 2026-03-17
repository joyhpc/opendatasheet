# FPGA Pinout Parser Overview

> What each FPGA pinout parser in the repo is responsible for and when to use it.

## Parsers in this repo

- `scripts/parse_fpga_pinout.py`
  AMD/Xilinx UltraScale+ TXT pinout parser
- `scripts/parse_gowin_pinout.py`
  Gowin XLSX pinout parser
- `scripts/parse_lattice_pinout.py`
  Lattice CSV-style pinout parser
- `scripts/parse_intel_pinout.py`
  Intel Agilex 5 OOXML pinout parser

## Shared output target

All of these feed normalized FPGA pinout JSON under:
- `data/extracted_v2/fpga/pinout/`

Those normalized pinouts then feed:
- `scripts/export_for_sch_review.py`

## Common output concepts

Across vendors, the parsers aim to produce:
- physical pin records
- bank structure
- differential pairs
- lookup maps
- DRC-relevant classification

## Why separate parsers exist

Vendor source formats differ materially:
- AMD uses TXT package files
- Gowin uses workbook-style XLSX
- Lattice pinouts are often CSV-like exports
- Intel Agilex 5 workbooks need OOXML parsing

Trying to force one brittle parser across all vendors would make the repo harder to trust.

## Common review expectations

For any parser output, ask:
- are pin counts correct
- are device and package identities correct
- do diff pairs reference valid pins
- do banks exist and look plausible
- are config and power pins classified sensibly

## Downstream dependency

Parser quality directly affects:
- bank-aware DRC
- diff-pair checks
- refclk and high-speed reasoning
- file naming and export discoverability
