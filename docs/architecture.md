# OpenDatasheet Architecture

Last audited from code and checked-in data: 2026-05-17.

This document describes the repository as it exists now. It intentionally avoids
assuming that old planning docs or README-era pipeline claims are still true.

## What The Repository Is

OpenDatasheet is a mixed device-knowledge repository with a validated public
export contract.

It contains:

- checked-in intermediate extraction/profile data
- deterministic FPGA pinout parser outputs
- a model-backed PDF extraction implementation
- export and normalization code
- JSON Schema contracts
- validation and regression tests
- hardware-review reference docs

It is not currently a fully replayable raw-source pipeline. The raw files in the
checkout are partial relative to the public exports.

## Current Data Flow

Canonical public export generation:

```text
data/extracted_v2/*.json
  -> scripts/export_for_sch_review.py
  -> data/sch_review_export/*.json
  -> scripts/validate_exports.py
```

FPGA package flow:

```text
vendor pinout source
  -> scripts/parse_pinout.py or vendor parser
  -> data/extracted_v2/fpga/pinout/*.json
  -> scripts/export_for_sch_review.py
  -> data/sch_review_export/*_{package}.json
  -> data/sch_review_export/_fpga_catalog.json
```

Raw-source reproducibility metadata:

```text
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

The optional model-backed path requires `GEMINI_API_KEY`.

## Module Responsibilities

| Area | Current owner | Responsibility | Should not own |
|------|---------------|----------------|----------------|
| Public schema | `schemas/sch-review-device.schema.json`, `schemas/domains/*.schema.json` | External contract for public exports | ad hoc behavior not represented in exporters |
| Public export writer | `scripts/export_for_sch_review.py` | Canonical generation of `data/sch_review_export/*.json`, `_manifest.json`, `_fpga_catalog.json` | raw PDF extraction |
| Normal-IC export shaping | `scripts/normal_ic_contract.py`, helpers in `scripts/` | Build v2 `domains` and flat compatibility fields for normal ICs | FPGA package parsing |
| FPGA pinout parsing | `scripts/parse_pinout.py`, `scripts/parse_*_pinout.py` | Convert vendor source formats into normalized package pinout JSON | normal IC electrical extraction |
| Model-backed extraction | `pipeline_v2.py`, `extractors/` | Page classification, rendered-page extraction, domain validation, legacy flat extraction output | public export compatibility policy |
| Export reading | `scripts/device_export_view.py` | Compatibility reads for flat and `domains` payloads | writing exports |
| Validation | `scripts/validate_exports.py`, `scripts/validate_design_extraction.py`, `test_regression.py`, `test_*.py` | Schema, semantic, corpus, and regression gates | silent data regeneration |
| Raw source inventory | `data/raw/`, `scripts/build_raw_source_manifest.py` | Reproducibility metadata for canonical raw files present in the checkout | field semantics |
| Derived outputs | `data/selection_profile/`, `data/design_bundle/`, `data/debugtool_interface/` | Consumer-friendly projections from public exports and supporting data | canonical schema decisions |

## Contract Hierarchy

Use this order when files disagree:

1. `schemas/`
2. `scripts/export_for_sch_review.py`
3. `scripts/validate_exports.py`
4. checked-in `data/sch_review_export/*.json`
5. checked-in intermediate data under `data/extracted_v2/`
6. docs

## Public Schema Model

The public export schema currently accepts:

- `sch-review-device/1.0`
- `sch-review-device/1.1`
- `device-knowledge/2.0`

All current checked-in public exports use `device-knowledge/2.0`.

The v2 model keeps flat compatibility fields and adds a `domains` container.
The current allowed domain keys are:

- `pin`
- `electrical`
- `thermal`
- `design_context`
- `register`
- `timing`
- `power_sequence`
- `design_guide`
- `parametric`
- `protocol`
- `package`

Do not infer that every allowed domain is populated. See
[Current State](current-state.md) for current coverage.

## Extractor Registry

The registered extractor order is defined in `extractors/__init__.py`:

1. `ElectricalExtractor`
2. `PinExtractor`
3. `ThermalExtractor`
4. `DesignContextExtractor`
5. `RegisterExtractor`
6. `TimingExtractor`
7. `PowerSequenceExtractor`
8. `ParametricExtractor`
9. `ProtocolExtractor`
10. `PackageExtractor`
11. `DesignGuideExtractor`

Important implementation detail: not every extractor is a model call.

- `electrical`, `pin`, `register`, `timing`, `power_sequence`, `protocol`,
  `package`, and the vision half of `design_guide` call the Gemini JSON helper
  when selected pages exist.
- `design_context` reads PDF text and uses `design_info_utils.py`.
- `thermal` derives data from the electrical result.
- `parametric` is intended to derive data from electrical results, but current
  `pipeline_v2.py` does not pass the electrical result into it.

## Entry Points

| Task | Command |
|------|---------|
| Validate public exports | `python scripts/validate_exports.py --summary` |
| Regenerate public exports | `python scripts/export_for_sch_review.py` |
| Build raw-source manifest | `python scripts/build_raw_source_manifest.py` |
| Check raw-source manifest | `python scripts/build_raw_source_manifest.py --check` |
| Parse FPGA pinout | `python scripts/parse_pinout.py <input> -o <output>` |
| Extract one PDF through model-backed path | `python pipeline_v2.py <pdf-path>` |
| Validate design extraction metadata | `python scripts/validate_design_extraction.py --strict` |
| Run strict local gate | `./scripts/run_checks.sh` |

## FPGA Parser Boundary

FPGA package pinout truth is deterministic parser output. Do not replace it with
generic vision extraction unless a specific vendor source format cannot be
parsed structurally and the provenance is recorded.

Current parser families include:

- AMD/Xilinx TXT package files
- Gowin XLSX and some PDF-style pinout sources
- Lattice CSV-style files
- Intel Agilex 5 OOXML workbooks
- Anlogic PH1A package workbooks

Expected normalized FPGA facts:

- physical pin records
- bank structure
- differential pairs
- lookup maps
- power/config/ground/special classification
- source traceability where available

## Validation Gates

Use the smallest relevant gate while developing, then run the broader gate
before publishing data changes.

| Change type | Minimum validation |
|-------------|--------------------|
| Public export shape | `python scripts/validate_exports.py --summary` |
| Schema change | export validation plus focused schema/export tests |
| FPGA parser change | parser tests, export validation, `_fpga_catalog.json` review |
| Raw source add/move/remove | `python scripts/build_raw_source_manifest.py --check` |
| Domain extractor change | focused extractor tests plus affected export tests |
| Design extraction behavior | `python scripts/validate_design_extraction.py --strict` |
| Docs only | `python scripts/check_markdown_links.py` |

## Known Architectural Gaps

- The current raw corpus is partial relative to generated exports.
- Historical model-backed outputs are not uniformly audit-traceable.
- `pipeline_v2.py` still mixes orchestration, compatibility output shaping, and
  validation helpers.
- `scripts/export_for_sch_review.py` remains a large canonical writer and is a
  future split candidate.
- `parametric` is registered but not correctly wired into `pipeline_v2.py`.
- Several docs are historical design notes and should not be used as current
  architecture references.
