# OpenDatasheet Command Cheat Sheet

> Short command reference for current repository entry points. Commands are grouped by intent because normal-IC extraction, FPGA parsing, export normalization, and validation are separate paths.

## Setup

```bash
./scripts/bootstrap.sh
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Set a Gemini key only when running model-backed extraction:

```bash
export GEMINI_API_KEY='<your-api-key>'
```

## Doctor

```bash
python3 scripts/doctor.py --dev
python3 scripts/doctor.py --dev --strict-env
```

Use `--strict-env` when you want missing extraction credentials to fail the check.

## Validation

```bash
./scripts/run_checks.sh
python3 scripts/check_markdown_links.py
python3 scripts/validate_exports.py --summary
python3 scripts/validate_design_extraction.py
python3 scripts/validate_design_extraction.py --strict
python3 scripts/prompt_registry.py
```

If pytest plugin autoload hits a local `_sqlite3` problem:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q
```

## Normal IC Extraction

```bash
python3 pipeline_v2.py <pdf-path>
python3 pipeline_v2.py <batch-limit>
```

This path uses the extractor registry in `extractors/__init__.py`. Model-backed extractors require `GEMINI_API_KEY`; derived/text extractors do not all call the model.

## FPGA Pinout Parsing

```bash
python3 scripts/parse_gowin_pinout.py <xlsx-path>
```

See `docs/fpga-pinout-parser-overview.md` for vendor-specific parser coverage and output structure.

## Export

```bash
python3 scripts/build_raw_source_manifest.py
python3 scripts/build_raw_source_manifest.py --check
python3 scripts/export_for_sch_review.py
python3 scripts/export_design_bundle.py --device TPS62147
python3 scripts/export_design_bundle.py --limit 10
```

`data/sch_review_export/` is the downstream contract layer. Validate it before relying on refreshed outputs.

## Tests

```bash
python3 test_regression.py
python3 -m pytest -q
```

Targeted smoke set:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test_extractor_framework.py test_model_trace.py test_export_contract.py test_fpga_parse_schema.py test_parametric_extraction.py -q
```

## Release Gate

```bash
python3 scripts/doctor.py --dev
./scripts/run_checks.sh
python3 scripts/export_for_sch_review.py
python3 scripts/validate_exports.py --summary
python3 scripts/validate_design_extraction.py --strict
python3 test_regression.py
python3 -m pytest -q
```
