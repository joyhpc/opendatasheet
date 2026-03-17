# Export File Naming

> Naming rules for generated JSON artifacts and how to predict where a device will land.

## `data/extracted_v2/`

For normal IC datasheets processed from PDFs:
- output name is the PDF stem plus `.json`

Example:
- `0130-01-00043_LM73605QRNPRQ1.pdf`
- `data/extracted_v2/0130-01-00043_LM73605QRNPRQ1.json`

For FPGA pinouts:
- parser-specific normalized names are written under `data/extracted_v2/fpga/pinout/`

## `data/sch_review_export/`

Normal IC exports:
- `{MPN}.json`

Examples:
- `AMS1117.json`
- `LM5060.json`

FPGA exports:
- `{Device}_{Package}.json`

Examples:
- `XCKU3P_FFVB676.json`
- `GW5AT-60_UG225.json`

## Why the split exists

Normal IC consumers normally select by MPN.

FPGA consumers need package-qualified outputs because:
- pin maps are package-specific
- bank topology can differ by package
- diff pairs and lane placement are package-specific

## Related generated files

Manifest and catalog files in `data/sch_review_export/`:
- `_manifest.json`
- `_fpga_catalog.json`

These are repository-level indexes, not per-device exports.

## Practical lookup rule

If you know the device is a normal IC:
- search by MPN

If you know the device is an FPGA:
- search by `device + package`

## Good review habit

When a filename changes unexpectedly, ask:
- did the MPN extraction change
- did the package normalization change
- did a parser start emitting a new device identity

Do not assume a rename is harmless. For consumers, file names are part of discoverability.
