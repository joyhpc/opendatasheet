# Release And Regeneration Matrix

> Decision table for whether a change needs data regeneration, validation only, or just documentation updates.

## Rule of thumb

Regenerate outputs when the change affects output semantics. Do not regenerate just because files nearby changed.

## Change matrix

### Documentation-only change

Examples:
- `docs/*.md`
- `README.md`
- `GUIDE.md`

Expected action:
- run markdown link checks if relevant
- no export regeneration

### Raw library add/move/remove

Examples:
- `data/raw/**`

Expected action:

```bash
python3 scripts/build_raw_source_manifest.py
python3 scripts/validate_design_extraction.py
```

If the new raw files should become extracted output:
- run extraction and export steps too

### Pipeline logic change

Examples:
- `pipeline.py`
- `pipeline_v2.py`
- files under `extractors/`

Expected action:

```bash
python3 scripts/export_for_sch_review.py
python3 scripts/validate_exports.py --summary
python3 test_regression.py
python3 -m pytest -q
```

### Export shaper change

Examples:
- `scripts/export_for_sch_review.py`
- schema-sensitive shaping helpers

Expected action:
- regenerate `data/sch_review_export/`
- validate exports
- run regression

### FPGA parser change

Examples:
- `scripts/parse_fpga_pinout.py`
- `scripts/parse_gowin_pinout.py`
- `scripts/parse_lattice_pinout.py`
- `scripts/parse_intel_pinout.py`

Expected action:
- regenerate affected pinout outputs
- regenerate affected sch-review exports
- run regression

### Schema change

Examples:
- `schemas/sch-review-device.schema.json`
- `schemas/domains/*.schema.json`

Expected action:
- validate all exports
- usually regenerate outputs if the schema meaning changed
- confirm migration compatibility expectations

## Minimum release gate

For a release or merge with real output impact:

```bash
python3 scripts/doctor.py --dev
./scripts/run_checks.sh
```

## Escalate before doing a mass re-export when

- the whole export directory will churn
- schema compatibility with older checked-in outputs may break
- downstream consumers need contract updates
- a migration step spans multiple output layers
