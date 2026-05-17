# Export Validation Playbook

This page explains how to validate `data/sch_review_export/` and interpret
common failure modes.

## Main Command

```bash
python scripts/validate_exports.py --summary
```

Current expected result:

```text
Total: 255  |  Passed: 255  |  Failed: 0
Schema versions: device-knowledge/2.0=255
All files valid
```

## Validate One File

```bash
python scripts/validate_exports.py data/sch_review_export/AMS1117.json
python scripts/validate_exports.py data/sch_review_export/XCKU3P_FFVB676.json
```

## Current Schema Reality

The validator accepts:

- `sch-review-device/1.0`
- `sch-review-device/1.1`
- `device-knowledge/2.0`

Current public exports use:

- `device-knowledge/2.0`

Compatibility expectation:

- v2 exports may still include flat compatibility fields alongside `domains`
- consumers should prefer `domains` but keep fallback reads for flat fields

## What Validation Checks

`validate_exports.py` checks:

- JSON Schema validity
- repository-specific semantic expectations

Examples of semantic checks:

- FPGA exports with high-speed interfaces should expose capability blocks
- refclk-capable FPGA exports should expose refclk constraints
- MCU-like devices with debug, boot, or clock pins should expose matching
  capability or constraint blocks

## Typical Failure Classes

### Schema Mismatch

Symptoms:

- missing required field
- wrong enum value
- wrong type
- unexpected domain key

Likely cause:

- schema changed without exporter update
- exporter changed without regenerating outputs
- hand-edited JSON drifted away from schema

### Semantic FPGA Gap

Symptoms:

- missing high-speed capability blocks
- missing refclk constraints
- missing package-derived bank/pair facts

Likely cause:

- parser output is incomplete
- export shaper stopped deriving a block
- package identity no longer matches expected source data

### Consumer Compatibility Gap

Symptoms:

- data validates, but downstream code cannot read it

Likely cause:

- downstream code assumes only flat fields or only domain fields
- compatibility accessor is missing

Use `scripts/device_export_view.py` as the reader pattern.

## Safe Workflow After Export Changes

```bash
python scripts/export_for_sch_review.py
python scripts/validate_exports.py --summary
python test_regression.py
python -m pytest -q
```

On Windows, if unrelated pytest plugins fail during collection:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
```

## When Not To Re-Export

Usually do not regenerate exports when the change is:

- documentation only
- CI only
- workflow notes only
- support/contributor guidance only

Use [Release Regeneration Matrix](release-regeneration-matrix.md) for broader
decisions.
