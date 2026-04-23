# Selection Profile Guide

> How to generate and use `data/selection_profile/` outputs.

## Purpose

Selection profiles are comparison-oriented summaries derived from `data/sch_review_export/`.

They are useful when you want:
- lightweight filtering
- normalized comparison cards
- category-level browsing

They are not a replacement for the full sch-review export contract.

## Generate profiles

```bash
python3 scripts/export_selection_profile.py
```

Useful options:

```bash
python3 scripts/export_selection_profile.py --summary
python3 scripts/export_selection_profile.py --output-dir /tmp/selection_profile
python3 scripts/export_selection_profile.py --export-dir data/sch_review_export
```

## Outputs

The script writes:
- one profile JSON per device
- `_index.json` for comparative browsing
- and removes stale top-level profile JSONs that no longer map to the current `sch_review_export` set

Default location:
- `data/selection_profile/`

## What a profile emphasizes

Compared with full exports, a selection profile prioritizes:
- category
- key numeric specs
- operating ranges
- packages
- thermal highlights

## Good use cases

- component selection dashboards
- procurement-friendly comparisons
- quick filtering before deeper schematic review

## Bad use cases

Do not use selection profiles when you need:
- per-pin reasoning
- bank-aware FPGA checks
- detailed DRC hints
- full constraint provenance

For those, use:
- `data/sch_review_export/`

## Safe workflow after export changes

```bash
python3 scripts/export_for_sch_review.py
python3 scripts/export_selection_profile.py --summary
```

If selection profiles look wrong, debug the underlying sch-review export first.
