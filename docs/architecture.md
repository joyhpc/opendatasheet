# OpenDatasheet Architecture Map

This page is the routing map for contributors who need to decide where a
change belongs. It does not replace the deeper docs; it names the current
boundaries, data flow, public entry points, and contracts that should stay
stable while the codebase is gradually split into clearer modules.

## Current Data Flow

```text
data/raw
  -> pipeline_v2.py + extractors/
  -> data/extracted_v2
  -> scripts/export_for_sch_review.py
  -> schemas/sch-review-device.schema.json + data/sch_review_export
  -> scripts/export_selection_profile.py
  -> data/selection_profile

data/sch_review_export
  -> scripts/export_design_bundle.py
  -> data/design_bundle

data/extracted_v2/fpga/pinout + data/sch_review_export
  -> scripts/build_fpga_catalog.py
  -> data/sch_review_export/_fpga_catalog.json

data/sch_review_export + data/raw/_source_manifest.json + tests
  -> scripts/validate_exports.py
  -> scripts/validate_design_extraction.py --strict
  -> test_regression.py
  -> python3 -m pytest -q
  -> scripts/run_checks.sh
```

FPGA pinout sources enter through vendor-specific parsers under `scripts/`
before they join the common export path:

```text
data/raw/... pinout source
  -> scripts/parse_pinout.py or scripts/parse_*_pinout.py
  -> data/extracted_v2/fpga/pinout
  -> scripts/export_for_sch_review.py
```

## Module Responsibilities

| Area | Current owner | Responsibility | Should not own |
|------|---------------|----------------|----------------|
| Raw sources | `data/raw/`, `scripts/build_raw_source_manifest.py` | Original PDF/XLS/XLSX/CSV inventory and reproducibility metadata | Extracted facts or normalized export fields |
| Extraction | `pipeline_v2.py`, `extractors/` | Turn datasheet pages into domain-oriented extracted records | Downstream export compatibility policy |
| FPGA parsing | `scripts/parse_pinout.py`, `scripts/parse_*_pinout.py` | Turn vendor pinout files into package pin maps | Normal IC export shaping |
| Export writing | `scripts/export_for_sch_review.py` | Canonical writer for `data/sch_review_export/*.json`, `_manifest.json`, and `_fpga_catalog.json` | Derived design-helper presentation logic |
| Export reading | `scripts/device_export_view.py` | Compatibility accessors for flat and `domains` export shapes | Writing or mutating checked-in exports |
| Selection profiles | `scripts/export_selection_profile.py` | Comparison-oriented cards from public exports | Re-extracting datasheet content |
| Design bundles | `scripts/export_design_bundle.py`, `scripts/normal_ic_bundle_service.py` | Hardware-design helper bundles from public exports plus extracted design context | Canonical export schema decisions |
| Validation | `scripts/validate_exports.py`, `scripts/validate_design_extraction.py`, `test_regression.py`, `test_*.py` | Enforce schema, semantic expectations, regressions, and corpus checks | Silent data regeneration |
| Schema | `schemas/sch-review-device.schema.json`, `schemas/domains/*.schema.json` | External JSON contract for consumers and validators | Implementation-specific helper behavior |

## Entry Points

Use these commands as the public surface. Internal functions may move during
future package refactors, but these commands should remain stable or keep
compatibility wrappers.

| Task | Entry point | Notes |
|------|-------------|-------|
| Extract one datasheet | `python3 pipeline_v2.py data/raw/path/to/file.pdf` | Requires `GEMINI_API_KEY`; writes extracted JSON. |
| Parse FPGA pinout data | `python3 scripts/parse_pinout.py ...` or vendor-specific `scripts/parse_*_pinout.py` | Produces `data/extracted_v2/fpga/pinout/*.json`. |
| Export public device knowledge | `python3 scripts/export_for_sch_review.py` | Canonical writer for `data/sch_review_export/`; currently uses positional directory arguments for overrides. |
| Validate public exports | `python3 scripts/validate_exports.py --summary` | Schema plus repository semantic checks. |
| Build selection profiles | `python3 scripts/export_selection_profile.py` | Consumes `data/sch_review_export/` by default. |
| Build design bundles | `python3 scripts/export_design_bundle.py --device <MPN>` | Consumes public exports and optional extracted design context. |
| Run the strict local gate | `./scripts/run_checks.sh` | Includes syntax, registry, raw manifest, Markdown links, export validation, design extraction validation, regression, and pytest. |
| Run a syntax-only loop | `./scripts/run_checks.sh --compile-only` | Useful when raw source staging is intentionally incomplete. |

## Contract Hierarchy

When code, schema, checked-in data, and docs disagree, use this order:

1. `schemas/` defines the external JSON contract.
2. `scripts/export_for_sch_review.py` is the only canonical writer for
   `data/sch_review_export/`.
3. `scripts/device_export_view.py` is the compatibility reader for existing
   flat exports and newer `domains` exports.
4. `scripts/export_selection_profile.py` and `scripts/export_design_bundle.py`
   consume public exports. They may use extracted context where explicitly
   required, but they should not become alternate export writers.
5. `scripts/validate_exports.py`, `scripts/validate_design_extraction.py`,
   `test_regression.py`, and `test_*.py` enforce the contract.
6. Checked-in JSON under `data/` is a generated artifact and regression corpus,
   not the source of truth for field semantics.
7. Docs explain intent, workflow, and review framing. They do not override the
   schema or exporter.

## Scripts Boundary Rule

The target direction is:

```text
scripts/*.py
  -> argparse, filesystem wiring, progress output, exit code

opendatasheet/export/...
  -> export shaping, schema-facing normalization, manifest/catalog builders

opendatasheet/bundle/...
  -> design bundle assembly and hardware-facing presentation

opendatasheet/validation/...
  -> schema and semantic validators

opendatasheet/accessors/...
  -> compatibility readers such as the current device_export_view layer
```

The repository is not there yet. Until a package split lands, keep new logic in
small importable functions and keep `main()` thin. Treat
`scripts/export_selection_profile.py` as the near-term migration example:
`parse_args()` owns CLI parsing, `main()` wires paths and iteration, and helper
functions own domain behavior. The next candidates for extraction are:

- `scripts/export_for_sch_review.py`: split normal IC accessors, FPGA shaping,
  schema/domain builders, manifest writing, and CLI wiring.
- `scripts/export_design_bundle.py`: keep CLI and filesystem writes thin; move
  bundle rules into service modules like `scripts/normal_ic_bundle_service.py`.
- `scripts/device_export_view.py`: promote compatibility accessors before
  downstream tools duplicate flat-vs-domains handling.
- `scripts/validate_exports.py`: separate schema loading from semantic policy
  checks before adding more device-family rules.

## Raw Source Manifest Gate

`./scripts/run_checks.sh` currently runs:

```bash
python3 scripts/build_raw_source_manifest.py --check
```

That manifest builder walks every `pdf`, `xls`, `xlsx`, and `csv` file under
`data/raw/`, excluding only `_source_manifest.json` itself. Files in
`_staging`, `_duplicates`, and `_archive` are intentionally inventoried with a
`storage_tier`.

`scripts/validate_design_extraction.py --strict` also checks the raw source
manifest. Its PDF-dependent curated and baseline checks run only when the
configured PDF directory has the full corpus; partial checkouts print
`pdf_corpus=partial` and skip only those coverage baselines.

Policy for now:

- Strict gates should include the raw source manifest because it is a
  reproducibility contract.
- Local, unreviewed source files should either be placed outside `data/raw/` or
  committed with a refreshed manifest before running the strict gate.
- Use `./scripts/run_checks.sh --compile-only` for a fast syntax loop when local
  raw-source staging is intentionally dirty.
- If this becomes too disruptive, add a separate smoke-check command rather
  than weakening the strict gate.

## Change Routing

| Change type | Start here | Expected validation |
|-------------|------------|---------------------|
| New extracted domain field | `extractors/`, `schemas/domains/` | Focused extractor tests plus affected export tests |
| New public export field | `schemas/sch-review-device.schema.json`, `scripts/export_for_sch_review.py` | `python3 scripts/validate_exports.py --summary`, export contract tests |
| Export compatibility read | `scripts/device_export_view.py` | Tests for both flat and `domains` payloads |
| Selection or comparison output | `scripts/export_selection_profile.py` | Selection-profile tests and generated output review |
| Design helper bundle behavior | `scripts/export_design_bundle.py`, `scripts/normal_ic_bundle_service.py` | Design bundle tests and targeted bundle generation |
| FPGA pinout support | `scripts/parse_*_pinout.py`, `data/extracted_v2/fpga/pinout/` | Vendor parser tests, FPGA export validation, `_fpga_catalog.json` review |
| Validation policy | `scripts/validate_exports.py`, `scripts/validate_design_extraction.py` | Validator tests plus one known-pass corpus run |
| Documentation-only workflow note | `docs/` | `python3 scripts/check_markdown_links.py` |

## Related Docs

- [`design-document.md`](design-document.md) for product framing and older
  high-level diagrams.
- [`sch-review-integration.md`](sch-review-integration.md) for the downstream
  export contract and consumer examples.
- [`export-validation-playbook.md`](export-validation-playbook.md) for export
  validation commands and failure classes.
- [`selection-profile-guide.md`](selection-profile-guide.md) for selection
  profile usage.
- [`design-bundle-workflow.md`](design-bundle-workflow.md) for design bundle
  generation workflow.
- [`raw-manifest-field-guide.md`](raw-manifest-field-guide.md) for raw source
  manifest fields.
