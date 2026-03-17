# Raw Source Quality Gates

## Purpose

The pipeline can only be as reliable as `data/raw/`. If raw source hygiene is weak, maintainers end up debugging ingestion noise instead of extraction logic.

## Required Quality Gates

### 1. Canonical placement

Raw source files belong under `data/raw/` with stable organization. Unreviewed drops should enter staging before being treated as canonical.

### 2. Manifest refresh

Whenever files are added, removed, or moved:

```bash
python3 scripts/build_raw_source_manifest.py
python3 scripts/build_raw_source_manifest.py --check
```

### 3. Basic file-type sanity

For PDFs, verify the file is actually a PDF. Do not trust the suffix.

### 4. Duplicate awareness

If the same source appears multiple times, decide whether it is canonical, duplicate, archive, or staging. Do not leave that ambiguous.

## What To Delete Immediately

- non-PDF blobs named as `.pdf`
- truncated files that cannot be opened
- accidental encrypted wrappers or download-manager payloads
- files that have no clear provenance and cannot be validated

## Why This Matters

Bad source hygiene creates false alarms in:

- PyMuPDF parsing
- Gemini extraction
- batch success metrics
- regression triage

Deleting bad inputs is often the correct technical fix.

## Maintainer Rule

If a file is proven invalid at the raw layer, do not “work around” it in the extractor. Remove or replace the source instead.
