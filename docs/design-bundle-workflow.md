# Design Bundle Workflow

> How to generate human-oriented design helper bundles from checked-in device exports.

## Purpose

`scripts/export_design_bundle.py` transforms machine-oriented sch-review exports into layered design helper bundles for hardware engineers.

Each bundle contains:
- `L0_device.json`
- `L1_design_intent.json`
- `L2_quickstart.md`
- `L3_module_template.json`
- `bundle_manifest.json`

## Default command

```bash
python3 scripts/export_design_bundle.py
```

Useful options:

```bash
python3 scripts/export_design_bundle.py --device TPS62147
python3 scripts/export_design_bundle.py --device XCKU3P_FFVB676
python3 scripts/export_design_bundle.py --limit 5
python3 scripts/export_design_bundle.py --output-dir /tmp/design_bundle
```

## Important dependency

This script imports `fitz`, so `PyMuPDF` must be installed.

If you see:
- `ModuleNotFoundError: No module named 'fitz'`

Install runtime dependencies:

```bash
pip install -r requirements.txt
```

## Inputs

By default the script reads:
- `data/sch_review_export/`
- `data/extracted_v2/`
- `data/raw/datasheet_PDF/`

## Why the bundle exists

The core export contract is optimized for tools.

The bundle adds:
- grouped design intent
- quickstart guidance
- module-starting structure
- easier human navigation

## Good workflow

1. validate exports
2. generate one device bundle
3. inspect `L2_quickstart.md`
4. only then generate broader batches

## Related doc

- `docs/design-extraction-reporting.md`
