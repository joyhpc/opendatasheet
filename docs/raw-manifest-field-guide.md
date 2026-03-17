# Raw Manifest Field Guide

> Field-by-field guide to `data/raw/_source_manifest.json`.

## Purpose

The raw manifest is not extracted content. It is a reproducibility inventory for original source files.

It answers:
- what original file is stored
- where it lives
- what kind of source it is
- whether it is canonical, duplicate, staging, or archive
- how to verify file identity by hash

## How to rebuild it

```bash
python3 scripts/build_raw_source_manifest.py
```

Check-only mode:

```bash
python3 scripts/build_raw_source_manifest.py --check
```

## Top-level fields

- `policy_version`
- `root`
- `entry_count`
- `summary`
- `entries`

## Summary fields

`summary` includes rollups such as:
- `by_storage_tier`
- `by_doc_type`
- `by_source_group`
- `by_format`

These are useful for inventory drift checks.

## Entry fields

Each entry typically contains:
- `path`
  repository-relative path under `data/raw/`
- `filename`
- `format`
  such as `pdf`, `xlsx`, `csv`
- `doc_type`
  such as `datasheet`, `pinout`, `design_guide`, `reference`
- `storage_tier`
  such as `canonical`, `duplicate`, `staging`, `archive`
- `source_group`
  top-level grouping under `data/raw/`
- `vendor_hint`
- `family_hint`
- `material_hint`
- `size_bytes`
- `sha256`

## How tiers are inferred

Directory names drive the tier:
- paths containing `_duplicates` become `duplicate`
- paths containing `_staging` become `staging`
- paths containing `_archive` become `archive`
- otherwise `canonical`

## Why this file matters

It keeps raw-source movement reviewable.

Without it, the repo can silently drift:
- same document duplicated
- canonical files misplaced
- family/source coverage misunderstood

## Good workflow

After any raw source add, move, or delete:

```bash
python3 scripts/build_raw_source_manifest.py
python3 scripts/validate_design_extraction.py
```
