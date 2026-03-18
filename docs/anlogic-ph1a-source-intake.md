# Anlogic PH1A Source Intake

> Initial intake notes for the Anlogic `PH1A` family sources provided through the shared Google Drive folder.

## What was imported

Raw sources were added under:

- `data/raw/fpga/anlogic_ph1a/`

Imported document set includes:

- family hardware design guide
- IO user guide
- clock-resource user guide
- SERDES user guide
- SERDES analog parameter note
- PCIe user guide
- DDR3/4 high-speed interface user guide
- MIPI DPHY-RX user guide
- SSO limitation report
- configuration user guide and configuration validation note
- family selection manual
- board usage guides for `APB102`, `AP103`, and `PH1A60GEG324_MINI`

## What we can already do with this set

This source bundle is already useful for:

- hardware architecture review
- board-level power / IO / clock / SERDES / DDR / MIPI review
- family-level capability mapping
- future capability-block and constraint-block extraction planning

It is especially valuable because it contains:

- hardware design guidance
- IO bank and SSO-related material
- clocking and SERDES collateral
- PCIe / DDR / MIPI family IP guidance

## Confirmed device and package tokens seen in the PDFs

The imported documents expose at least these concrete device-package style identifiers:

- `PH1A60GEG324`
- `PH1A90SBG324`
- `PH1A90SBG484`
- `PH1A90SEG324`
- `PH1A90SEG484`
- `PH1A180SFG676`
- `PH1A400SFG676`
- `PH1A400SFG900`

They also expose family-level devices:

- `PH1A60`
- `PH1A90`
- `PH1A180`
- `PH1A400`

## What this set does not yet give us cleanly

It is **not yet sufficient** for package-grade sch-review FPGA export generation.

Current gaps:

- no dedicated package pinout workbook / CSV / TXT source has been imported
- no authoritative per-package pin list with stable physical-pin mapping has been imported
- no clean package guide or pin table source has been isolated for parser development

Without those sources, we should not pretend we can already generate:

- `pins`
- `lookup.pin_to_name`
- `banks`
- `diff_pairs`

at the same quality level we have for AMD / Gowin / Lattice / Intel families.

## Recommended next source targets

Before building an Anlogic package parser, collect one of the following:

1. official package pinout workbook or CSV
2. official package/pin manual with stable tables
3. family datasheet pages that contain machine-usable pinout tables per package

The ideal target is a source that gives:

- physical pin name
- package pin number / ball
- bank
- special function
- differential pair or transceiver role

## Recommended implementation order

1. keep the raw PH1A corpus in `data/raw/fpga/anlogic_ph1a/`
2. use these PDFs for hardware-review docs and capability planning
3. separately acquire package pinout sources
4. only then add an `Anlogic` parser in `scripts/`

## Why this order matters

If we skip straight to parser work using family user guides as if they were pinout truth, we will create exports that look structured but are not package-safe.

For FPGA work in this repo, package truth beats family summary.
