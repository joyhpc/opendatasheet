# Design Extraction Reporting

> How to regenerate the design extraction validation report and why it exists.

## Main command

```bash
python3 scripts/generate_design_extraction_report.py
```

Useful overrides:

```bash
python3 scripts/generate_design_extraction_report.py --report-path /tmp/report.md
python3 scripts/generate_design_extraction_report.py --samples-dir /tmp/design-samples
```

## Default outputs

- report: `docs/design-extraction-validation.md`
- samples: `docs/design-extraction-samples/`

## What the report does

It summarizes:
- corpus-level design extraction coverage
- category-level coverage
- curated sample devices

It depends on:
- checked-in exports
- extracted records
- raw PDF location

## Important dependency

This report path imports `export_design_bundle.py`, which imports `fitz`.

If `PyMuPDF` is missing, the command will fail with:
- `ModuleNotFoundError: No module named 'fitz'`

## When to regenerate

Regenerate when changes affect:
- design-context extraction
- design-page detection
- design-helper bundle logic
- validation baseline expectations

Usually do not regenerate for:
- docs-only changes
- unrelated export-contract changes

## Companion validator

For the pass/fail gate, use:

```bash
python3 scripts/validate_design_extraction.py
```

Use the report when you want a reviewable human-readable summary, not just a test outcome.
