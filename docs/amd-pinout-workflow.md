# AMD Pinout Workflow

> How to work with the AMD/Xilinx UltraScale+ TXT pinout parser.

## Parser

Use:

```bash
python3 scripts/parse_fpga_pinout.py
```

Defaults:
- input dir: `data/raw/fpga/pinout`
- output dir: `data/extracted_v2/fpga/pinout`

## Input expectations

The parser expects AMD package TXT files such as:
- `xcku3pffvb676pkg.txt`

## What it derives

The parser classifies:
- IO pins
- GT RX/TX pins
- GT refclk pins
- power rails
- config pins
- special pins such as XADC-related pins

It also auto-builds:
- bank structure
- differential pairs
- lookup maps

## Good workflow

```bash
python3 scripts/parse_fpga_pinout.py
python3 scripts/export_for_sch_review.py
python3 test_regression.py -k fpga
```

## AMD-specific review focus

- `VCCO_*` bank interpretation
- GT lane and refclk extraction
- config pin mandatory connection rules
- reserved or analog-special pins

## Why this parser matters

AMD packages often look family-similar while remaining package-specific in the places that matter for board review:
- bank availability
- transceiver placement
- refclk access
- supply pin layout
