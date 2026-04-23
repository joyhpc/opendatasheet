# Export Validation Playbook

> How to validate `data/sch_review_export/` and interpret the failure modes.

## Main command

```bash
python3 scripts/validate_exports.py --summary
```

What it checks:
- JSON Schema validity
- semantic rules layered on top of schema checks

## Validate one file

```bash
python3 scripts/validate_exports.py data/sch_review_export/AMS1117.json
python3 scripts/validate_exports.py data/sch_review_export/XCKU3P_FFVB676.json
```

## Current schema realities

The validator accepts:
- `sch-review-device/1.0`
- `sch-review-device/1.1`
- `device-knowledge/2.0`

Current export generation target is:
- `device-knowledge/2.0`

Compatibility expectation:
- new exports may still carry flat `sch-review-device/1.1`-style fields alongside `domains`

## What semantic validation adds

Schema validity alone is not enough. The validator also checks repository-specific expectations, for example:

- FPGA exports with high-speed interfaces should include `capability_blocks`
- FPGA refclk-capable exports should include `constraint_blocks.refclk_requirements`
- MCU-like devices with debug, boot, or clock pins should include matching capability and constraint blocks

## Typical failure classes

### Flat schema mismatch

Symptoms:
- missing required field
- wrong enum value
- wrong type

Likely cause:
- export-shaping logic changed
- checked-in output is stale

### Semantic FPGA gap

Symptoms:
- missing `mipi_phy`
- missing `high_speed_serial`
- missing `refclk_requirements`

Likely cause:
- pinout-derived capability extraction is incomplete
- export shaper stopped filling a derived block

### Semantic MCU-like gap

Symptoms:
- missing `debug_access`
- missing `boot_configuration`
- missing `clocking`

Likely cause:
- capability inference logic regressed

## Safe workflow after export changes

```bash
python3 scripts/export_for_sch_review.py
python3 scripts/validate_exports.py --summary
python3 test_regression.py
python3 -m pytest -q
```

## Important caveat

`validate_exports.py` does not parse `--help` with argparse. Treat extra arguments as file paths except for `--summary`.

## When not to re-export

Usually do not regenerate exports when the change is:
- documentation only
- CI only
- workflow notes only
- support or contributor guidance only

Use `docs/release-regeneration-matrix.md` for the broader decision table.
