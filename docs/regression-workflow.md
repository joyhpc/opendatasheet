# Regression Workflow

> How to use `test_regression.py` and `pytest` without wasting time.

## Start with the repository regression suite

```bash
python3 test_regression.py
```

Useful variants:

```bash
python3 test_regression.py -v
python3 test_regression.py -k fpga
```

What this script covers:
- expected FPGA pinout files exist
- pin counts and metadata match expectations
- lookup maps are internally consistent
- differential pairs reference valid pins
- schema file is structurally sane
- checked-in exports validate

## Use `pytest` for broader repository coverage

```bash
python3 -m pytest -q
```

Use this when:
- pipeline logic changed
- export logic changed
- you touched tests directly
- you want the same broad gate as CI

## Practical triage order

1. `python3 scripts/validate_exports.py --summary`
2. `python3 test_regression.py`
3. `python3 -m pytest -q`

This ordering tells you quickly whether the break is:
- checked-in data
- regression contract
- or broader code behavior

## When to use keyword filtering

For targeted FPGA work:

```bash
python3 test_regression.py -k fpga
```

For a specific class of failures in `pytest`, use normal pytest selectors as needed.

## Common signals

### Missing expected pinout file

Usually means:
- parser output path changed
- file naming changed
- checked-in generated pinout was removed or renamed

### Export schema failures

Usually means:
- export shaper changed
- schema changed
- generated outputs are stale

### Diff pair reference failures

Usually means:
- parser classification changed
- pair extraction logic regressed

## Good pre-commit habit

For data-shaping or parser changes:

```bash
python3 scripts/validate_exports.py --summary
python3 test_regression.py
```

For larger changes:

```bash
./scripts/run_checks.sh
```
