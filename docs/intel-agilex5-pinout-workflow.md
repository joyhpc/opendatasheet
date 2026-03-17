# Intel Agilex 5 Pinout Workflow

> How to work with the Intel/Altera Agilex 5 workbook parser.

## Parser

Use:

```bash
python3 scripts/parse_intel_pinout.py
```

Defaults:
- input dir: `data/raw/fpga/intel_agilex5`
- output dir: `data/extracted_v2/fpga/pinout`

## Source format

The parser reads official XLSX workbooks by parsing OOXML directly.

Why that matters:
- avoids adding another heavyweight dependency just for workbook parsing
- keeps parsing logic explicit and reviewable

## What it derives

- package-level pin lists
- package resource counts
- revision history metadata
- ordering-variant properties
- content source metadata
- normalized pin classification

## Device-specific nuance

Agilex 5 ordering variants encode meaning such as:
- FPGA vs FPGA SoC
- HPS presence
- transceiver presence
- crypto presence

That is exactly why package-level and ordering-level review must not be replaced by family-level assumptions.

## Good workflow

```bash
python3 scripts/parse_intel_pinout.py
python3 scripts/export_for_sch_review.py
python3 test_regression.py -k fpga
```

## Intel-specific review focus

- variant-code interpretation
- package resource sheet parsing
- HPS/transceiver assumptions
- workbook title and package metadata coherence
