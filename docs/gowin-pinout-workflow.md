# Gowin Pinout Workflow

> How to work with the Gowin XLSX pinout parser.

## Parser

Use:

```bash
python3 scripts/parse_gowin_pinout.py
```

Defaults:
- input dir: `data/raw/fpga/gowin/高云 FPGA`
- output dir: `data/extracted_v2/fpga/pinout`

## Dependency

This parser requires `openpyxl`.

If you see:
- `pip install openpyxl`

Install runtime dependencies or install `openpyxl` directly.

## What it reads

Typical workbook sections:
- `Pin Definitions`
- `Power`
- package-specific `Pin List ...` sheets

## What it derives

- pin classification
- package-specific pin location mapping
- diff pairs
- bank structure
- DRC-oriented lookup helpers

## Good workflow

```bash
python3 scripts/parse_gowin_pinout.py
python3 scripts/export_for_sch_review.py
python3 test_regression.py -k fpga
```

## Gowin-specific review focus

- package sheet header detection
- config-function carryover
- diff pair polarity from workbook fields
- whether SerDes-capable packages really expose the expected pairs

## Why careful review matters here

Gowin sources often carry important package and workbook-structure variation. Small parser mistakes can turn into:
- wrong pair polarity
- wrong package selection
- hidden bank drift
