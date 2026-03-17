# OpenDatasheet First 30 Minutes

> Fast path for a contributor or reviewer who has just opened the repo and needs working context quickly.

## 1. Prove the repo is healthy

```bash
python3 scripts/doctor.py --dev
./scripts/run_checks.sh
```

What this gives you:
- Confirms Python and package imports.
- Confirms key repository paths exist.
- Runs schema validation, regression, and `pytest`.

## 2. Read only three files first

Open these in order:
- `README.md`
- `GUIDE.md`
- `docs/index.md`

This gets you:
- repository purpose
- repo navigation
- topic routing into the deeper docs

## 3. Pick your lane

If you need to add or refresh extracted data:
- read `docs/adding-normal-ic-datasheet.md`
- read `docs/batch-processing-runbook.md`

If you need to validate checked-in outputs:
- read `docs/export-validation-playbook.md`
- read `docs/regression-workflow.md`

If you need to consume repository outputs downstream:
- read `docs/sch-review-integration.md`
- read `docs/consumer-query-recipes.md`

If you need FPGA-specific context:
- read `docs/fpga-pinout-parser-overview.md`
- read `docs/fpga-export-review-checklist.md`

## 4. Learn the three data layers

The repo has three main checked-in output layers:

- `data/raw/`
  Original source files and reproducibility inventory.
- `data/extracted_v2/`
  Pipeline-native extraction results.
- `data/sch_review_export/`
  Normalized downstream contract used by schematic review consumers.

Do not edit generated outputs casually. Prefer fixing the generating script and then regenerating the relevant layer.

## 5. Understand the default repo loop

Typical engineering loop:

```bash
python3 scripts/doctor.py --dev
./scripts/run_checks.sh
python3 scripts/validate_exports.py --summary
python3 test_regression.py
python3 -m pytest -q
```

For data changes:

```bash
python3 scripts/build_raw_source_manifest.py
python3 batch_all.py --limit 5
python3 scripts/export_for_sch_review.py
python3 scripts/validate_exports.py --summary
```

## 6. Common surprises

- `validate_exports.py` does not implement argparse help. Use it as `python3 scripts/validate_exports.py --summary` or pass file paths directly.
- `export_design_bundle.py` and `generate_design_extraction_report.py` require `PyMuPDF` because they import `fitz`.
- `parse_gowin_pinout.py` requires `openpyxl`.
- A documentation-only change usually does not require export regeneration.

## 7. Good next reads

- `docs/local-setup-playbook.md`
- `docs/release-regeneration-matrix.md`
- `docs/schema-v2-domains-guide.md`
