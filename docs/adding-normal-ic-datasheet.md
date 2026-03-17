# Adding A Normal IC Datasheet

> Practical flow for taking a new raw datasheet from intake to validated downstream export.

## 1. Place the raw file correctly

If the file is not yet reviewed:
- put it in `data/raw/_staging/`

If the file is ready to become canonical:
- place it under the appropriate subtree in `data/raw/datasheet_PDF/`

Then refresh the manifest:

```bash
python3 scripts/build_raw_source_manifest.py
```

## 2. Process a small batch first

Use a limited run:

```bash
python3 batch_all.py --limit 1
```

Or constrain by filename prefix:

```bash
python3 batch_all.py --category 0130-01 --limit 1
```

## 3. Inspect the extraction result

Look in:
- `data/extracted_v2/<pdf-stem>.json`

Check for:
- `component.mpn`
- extracted absolute maximum ratings
- electrical characteristics
- package or pin extraction content
- obvious extraction errors

## 4. Export to sch-review format

```bash
python3 scripts/export_for_sch_review.py
```

This writes normalized outputs to:
- `data/sch_review_export/`

## 5. Validate the result

```bash
python3 scripts/validate_exports.py --summary
python3 test_regression.py
```

## 6. Optional downstream views

Generate design-helper bundles:

```bash
python3 scripts/export_design_bundle.py --device <MPN>
```

Generate selection profile outputs:

```bash
python3 scripts/export_selection_profile.py --summary
```

## Common operator mistakes

- putting canonical raw files directly into an ad hoc directory
- forgetting to rebuild `_source_manifest.json`
- mass-running extraction before validating one sample
- hand-editing generated exports instead of fixing the generator

## Good acceptance checklist

- raw file placed under the right `data/raw/` subtree
- manifest refreshed
- extraction JSON exists
- normalized export exists
- export validation passes
- regression remains green
