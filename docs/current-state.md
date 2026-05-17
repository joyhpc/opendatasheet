# OpenDatasheet Current State

Last audited from code and checked-in data: 2026-05-17.

This is the first document to read when a count, workflow, or architecture claim
matters. It is intentionally based on code, schema, validation scripts, and
checked-in JSON rather than older explanatory docs.

## Source Of Truth

Use this order when two files disagree:

1. `schemas/`
2. `scripts/export_for_sch_review.py`
3. `scripts/validate_exports.py`
4. checked-in `data/sch_review_export/*.json`
5. checked-in intermediate data under `data/extracted_v2/`
6. docs

The docs are a map. They do not override schema, exporters, validators, or the
actual JSON corpus.

## Public Export Snapshot

`data/sch_review_export/` currently contains 255 public device-knowledge files,
excluding `_manifest.json` and `_fpga_catalog.json`.

| Metric | Current value |
|--------|---------------|
| Total public exports | 255 |
| `normal_ic` exports | 172 |
| `fpga` exports | 83 |
| Schema version | all 255 use `device-knowledge/2.0` |
| Export validation | 255 passed, 0 failed with `python scripts/validate_exports.py --summary` |

Current domain coverage in public exports:

| Domain | Non-empty exports | Meaning |
|--------|-------------------|---------|
| `pin` | 248 | package pins or FPGA physical pins |
| `electrical` | 167 | absolute maximum, electrical parameters, DRC hints |
| `thermal` | 63 | thermal-derived values |
| `design_context` | 48 | application/layout/component hints |
| `design_guide` | 15 | mostly Gowin FPGA design-guide overlays |
| `power_sequence` | 13 | mostly Gowin FPGA design-guide-derived sequencing |
| `protocol` | 6 | automotive video SerDes profiles |
| `package` | 1 | package/mechanical domain data |
| `register` | 0 | schema/framework exists; no current non-empty public exports |
| `timing` | 0 | schema/framework exists; no current non-empty public exports |
| `parametric` | 0 | schema/framework exists; no current non-empty public exports |

## Intermediate Data Snapshot

Top-level files in `data/extracted_v2/`, excluding `_summary.json`:

| Metric | Current value |
|--------|---------------|
| Files | 179 |
| `model=gemini-3-flash-preview`, `mode=vision` | 175 |
| `model=manual_profile`, `mode=manual` | 4 |
| Files with a top-level `domains` block | 6 |
| Files with non-empty `domain_traces` | 0 |
| `_audit/*.model_trace.json` sidecar directory | not present |
| `_state/*.domain_ledger.json` sidecar directory | not present |

Interpretation:

- Existing intermediate normal-IC data is mostly legacy flat extraction output.
- Many files claim a Gemini model in their metadata, but current audit traces are
  not present, so the repository cannot prove model-call provenance for those
  historical files.
- A small number of profile-style files are explicitly manual.
- Public exports are regenerated from these intermediate files plus FPGA pinout
  inputs and normalization helpers.

## Raw Source Snapshot

`data/raw/_source_manifest.json` currently records 37 canonical entries:

| Format | Count |
|--------|-------|
| PDF | 26 |
| XLSX | 11 |

This raw corpus is partial relative to the generated public exports. Do not
assume a clean checkout can replay every public export from currently present
raw files alone.

## FPGA Snapshot

`data/extracted_v2/fpga/pinout/` currently contains 83 normalized FPGA package
pinout JSON files.

| Vendor/family group | Files |
|---------------------|-------|
| Gowin | 32 |
| Intel/Altera Agilex 5 | 10 |
| Lattice | 18 |
| Anlogic PH1A | 7 |
| AMD/Xilinx UltraScale+ | 16 |

Across those package files:

| Metric | Current value |
|--------|---------------|
| Minimum pins in one package file | 90 |
| Maximum pins in one package file | 1591 |
| Average pins per package file | 489.3 |
| Average banks per package file | 10.8 |
| Average differential pairs per package file | 75.6 |

FPGA package data comes primarily from deterministic parser outputs, not generic
vision extraction.

## Implemented Extraction Paths

### Model-backed path

`pipeline_v2.py` implements a model-backed extraction path:

1. `classify_pages()` reads PDF text with PyMuPDF and assigns page categories.
2. Each registered extractor chooses pages.
3. Selected pages are rendered to PNG.
4. Model-backed extractors call `client.models.generate_content(...)` through
   `extractors/gemini_json.py`.
5. The pipeline writes legacy flat output plus `domains` where available.

This path requires `GEMINI_API_KEY`.

### Text and derived paths

Some extractors do not call a model:

- `design_context` reads PDF text and calls `design_info_utils.py`.
- `thermal` derives thermal entries from the electrical result.
- `parametric` is intended to derive comparison specs from electrical data, but
  current `pipeline_v2.py` does not pass electrical data into it.

### Manual/curated path

Some current files are manual profiles. They should be treated as curated data
inputs, not model outputs.

### FPGA parser path

FPGA pinout sources enter through deterministic vendor parsers:

- `scripts/parse_pinout.py`
- `scripts/parse_fpga_pinout.py`
- `scripts/parse_gowin_pinout.py`
- `scripts/parse_lattice_pinout.py`
- `scripts/parse_intel_pinout.py`
- `scripts/parse_anlogic_ph1a_pinout.py`

These produce package-specific pinout JSON consumed by
`scripts/export_for_sch_review.py`.

## Current Architecture In One Picture

```text
data/extracted_v2/*.json
  -> scripts/export_for_sch_review.py
  -> data/sch_review_export/*.json
  -> scripts/validate_exports.py

data/extracted_v2/fpga/pinout/*.json
  -> scripts/export_for_sch_review.py
  -> data/sch_review_export/*_{package}.json
  -> data/sch_review_export/_fpga_catalog.json

data/raw/*
  -> scripts/build_raw_source_manifest.py
  -> data/raw/_source_manifest.json
```

Optional model-backed extraction path:

```text
PDF
  -> pipeline_v2.py
  -> extractors/
  -> data/extracted_v2/*.json
```

## Known Gaps And Risks

- Many older explanatory docs had stale counts or over-stated the Gemini Vision
  path. Prefer this file and `docs/architecture.md`.
- The current raw corpus is partial.
- Historical Gemini-labeled intermediate JSON lacks current audit sidecars.
- `register`, `timing`, and `parametric` public domains are not populated today.
- `ParametricExtractor` is not wired correctly into `pipeline_v2.py` as of this
  audit because the orchestrator does not pass the electrical result to it.
- Some docs are design history or hardware review reference material. They are
  useful, but not authoritative for repository state.

## Verification Commands

Run these after changing exports, schema, parser behavior, or core docs:

```bash
python scripts/validate_exports.py --summary
python scripts/validate_design_extraction.py --strict
python scripts/prompt_registry.py
python scripts/check_markdown_links.py
```

Run focused tests as needed:

```bash
python -m pytest -q
```

On Windows, if pytest fails while auto-loading unrelated third-party plugins
because the local Python installation lacks `_sqlite3`, disable plugin autoload:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
```
