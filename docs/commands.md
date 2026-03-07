# OpenDatasheet Command Cheat Sheet

> Short command reference for the current repository entrypoints.

## Setup

```bash
./scripts/bootstrap.sh
pip install -r requirements.txt
pip install -r requirements-dev.txt
export GEMINI_API_KEY='<your-api-key>'
```

## Doctor

```bash
python3 scripts/doctor.py --dev
python3 scripts/doctor.py --dev --strict-env
```

## Checks

```bash
./scripts/run_checks.sh
python3 scripts/validate_exports.py --summary
python3 scripts/validate_design_extraction.py
python3 scripts/validate_design_extraction.py --strict
```

## Export

```bash
python3 scripts/build_raw_source_manifest.py
python3 scripts/build_raw_source_manifest.py --check
python3 scripts/export_for_sch_review.py
python3 scripts/export_design_bundle.py --device TPS62147
python3 scripts/export_design_bundle.py --limit 10
python3 scripts/organize_datasheet_pdfs.py --apply
python3 scripts/validate_design_extraction.py --strict
python3 pipeline_v2.py <pdf-path>
python3 pipeline_v2.py <batch-limit>
```

## Tests

```bash
python3 test_regression.py
python3 -m pytest -q
```

## Release

```bash
python3 scripts/doctor.py --dev
./scripts/run_checks.sh
python3 scripts/export_for_sch_review.py
python3 scripts/validate_exports.py --summary
python3 test_regression.py
python3 -m pytest -q
```
