# OpenDatasheet First 30 Minutes

> Fast path for a contributor or reviewer who has just opened the repo and needs working context quickly.

## 1. Prove the repo is healthy

```bash
python3 scripts/doctor.py --dev
./scripts/run_checks.sh
```

What this gives you:
- confirms Python and package imports
- confirms key repository paths exist
- runs schema validation, regression checks, docs link checks, and `pytest`

If your local Windows Python has a broken `_sqlite3` extension while pytest plugins autoload, use:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q
```

## 2. Read the reliable entry set first

Open these in order:
- `README.md`
- `GUIDE.md`
- `docs/current-state.md`
- `docs/architecture.md`
- `docs/index.md`

This gives you:
- current repository purpose and scope
- audited data counts and extraction provenance
- architecture and module boundaries
- routing into deeper workflow, schema, FPGA, and hardware docs

## 3. Pick your lane

If you need to understand current extraction behavior:
- read `docs/extraction-methodology.md`
- read `docs/extractor-domain-map.md`
- read `docs/gemini-api-operations.md` only for the Gemini-backed path

If you need to add or refresh extracted data:
- read `docs/adding-normal-ic-datasheet.md`
- read `docs/batch-processing-runbook.md`
- confirm raw input availability before assuming a full replay is possible

If you need to validate checked-in outputs:
- read `docs/export-validation-playbook.md`
- read `docs/regression-workflow.md`

If you need to consume repository outputs downstream:
- read `docs/sch-review-integration.md`
- read `docs/consumer-query-recipes.md`

If you need FPGA-specific context:
- read `docs/fpga-pinout-parser-overview.md`
- read `docs/fpga-export-review-checklist.md`

## 4. Learn the data layers

The repo has these important checked-in data layers:

- `data/raw/`
  Source-file inventory and local raw inputs. In the current checkout this layer is partial relative to the public export set, so do not assume every export can be regenerated from local raw files.
- `data/extracted_v2/`
  Pipeline-native extraction and curated profile outputs. The top-level normal-IC files are mixed provenance, including Gemini-backed and manual/curated profiles.
- `data/extracted_v2/fpga/pinout/`
  Deterministic FPGA package parse outputs.
- `data/sch_review_export/`
  Normalized downstream contract used by schematic review consumers. This is the public integration layer.

Do not edit generated outputs casually. Prefer fixing the generating script and regenerating the relevant layer.

## 5. Understand the default repo loop

Typical engineering loop:

```bash
python3 scripts/doctor.py --dev
./scripts/run_checks.sh
python3 scripts/validate_exports.py --summary
python3 scripts/validate_design_extraction.py --strict
python3 -m pytest -q
```

For export-only validation:

```bash
python3 scripts/validate_exports.py --summary
python3 scripts/validate_design_extraction.py --strict
```

For data regeneration, choose the narrow path for the data you are changing. Normal IC extraction, FPGA parsing, and export normalization are separate responsibilities.

## 6. Common surprises

- The current public export layer is `device-knowledge/2.0`.
- `scripts/validate_exports.py` also accepts older schema versions because archived or transitional files may still exist outside the current public export set.
- `GEMINI_API_KEY` is only required for Gemini-backed extraction commands, not for docs, schema inspection, or export validation.
- The current local raw corpus is partial, so some public exports are not fully replayable from local raw files alone.
- A documentation-only change usually does not require export regeneration.

## 7. Good next reads

- `docs/top-10-entry-points.md`
- `docs/local-setup-playbook.md`
- `docs/release-regeneration-matrix.md`
- `docs/schema-v2-domains-guide.md`
