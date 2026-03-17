# Invalid PDF Triage

## Problem

Not every file with a `.pdf` suffix is an actual PDF. In this repository, some raw source entries were binary blobs with no `%PDF-` header and PyMuPDF failed with `FileDataError`.

Treating those files as extraction failures creates noise and sends maintainers in the wrong direction.

## Current Guardrail

`pipeline_v2.py` now validates the first 1024 bytes before any PyMuPDF or Gemini work:

- valid file: header contains `%PDF-`
- invalid file: raise `InvalidPdfError`

This makes the failure explicit and cheap.

## Why Header Validation Matters

Without a header check, a bad source file can be misread as:

- a PyMuPDF parser bug
- a Gemini extraction issue
- a page classifier defect
- a timeout problem

That is wasted debugging time.

## Triage Workflow

### Step 1: Confirm the file type

Useful commands:

```bash
file bad.pdf
xxd -l 24 bad.pdf
```

If `%PDF-` is absent, stop there. It is a source-quality problem.

### Step 2: Remove bad corpus entries

If the file is canonical raw input and confirmed invalid:

- delete the local raw file
- delete any mirrored copy you can prove maps to the same bad source
- refresh `data/raw/_source_manifest.json`

### Step 3: Do not generate downstream output

Bad raw files should not have:

- extracted JSON
- exported design bundles
- selection profiles based on fake parsing attempts

## Repository-Specific Signature

The bad Transistor files inspected during the March 2026 cleanup started with binary signatures such as `E-SafeNet`, not `%PDF-`. They were not malformed PDFs. They were non-PDF payloads misnamed as PDFs.

## Maintenance Rule

When a batch fails on many files at `fitz.open()`, inspect file headers before changing pipeline logic.
