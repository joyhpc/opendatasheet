# Lattice Pinout Workflow

> How to work with the Lattice pinout parser for ECP5 and CrossLink-NX style sources.

## Parser

Use:

```bash
python3 scripts/parse_lattice_pinout.py
```

Defaults:
- input dir: `data/raw/fpga/lattice`
- output dir: `data/extracted_v2/fpga/pinout`

## Source format reality

The parser expects CSV-style content even when vendor downloads may arrive with spreadsheet-like naming.

It supports:
- ECP5 / ECP5-5G style headers
- CrossLink-NX style headers

## What it classifies

- ground and power pins
- config pins
- SerDes pins
- D-PHY-related pins
- IO pins
- special analog or PLL pins

## What it derives

- differential pairs from explicit pair columns
- bank structure
- lookup maps

## Good workflow

```bash
python3 scripts/parse_lattice_pinout.py
python3 scripts/export_for_sch_review.py
python3 test_regression.py -k fpga
```

## Lattice-specific review focus

- format detection between ECP5 and CrossLink-NX
- explicit differential pair complement fields
- SerDes and D-PHY classification
- package pin counts vs expected package identity
