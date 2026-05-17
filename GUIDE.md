# OpenDatasheet Reading Guide

Use this guide as the first routing page. It points to the docs that are meant
to describe the current repository, not older planning notes.

## Reliable First Reads

1. [Current State](docs/current-state.md):
   The audited snapshot: counts, provenance, ingestion paths, coverage, known
   gaps, and validation commands.

2. [Architecture](docs/architecture.md):
   Code-verified module boundaries and data flow. Start here before changing
   extraction, export, schema, validation, or parser behavior.

3. [Schematic Review Integration](docs/sch-review-integration.md):
   The public `data/sch_review_export/` contract for downstream DRC and tooling.

4. [Schema](schemas/sch-review-device.schema.json):
   The formal `device-knowledge/2.0` schema. This outranks prose docs.

5. [Documentation Index](docs/index.md):
   A routed map of the rest of the docs, including which docs are historical or
   topic-specific reference material.

## What This Repository Currently Is

OpenDatasheet is a mixed device-knowledge repository:

- public exports are generated into `data/sch_review_export/`
- normal-IC inputs mostly come from checked-in `data/extracted_v2/*.json`
- some profiles are manually curated and explicitly marked `manual_profile`
- FPGA package truth comes from deterministic vendor pinout parsers
- `pipeline_v2.py` still provides a Gemini-backed image extraction path, but
  the checked-in corpus is not uniformly audit-traceable model output

Do not summarize the project as "Gemini Vision extracts everything." That is an
implementation path, not the whole current workflow.

## Current Data

| Data set | Current count |
|----------|---------------|
| Public exports | 255 |
| Normal IC exports | 172 |
| FPGA exports | 83 |
| Export schema | `device-knowledge/2.0` for all current public exports |
| Top-level extracted JSON | 179, excluding `_summary.json` |
| FPGA pinout JSON | 83 |
| Canonical raw manifest entries | 37 |

## Main Code Entry Points

| File | Role |
|------|------|
| `pipeline_v2.py` | Model-backed PDF extraction orchestrator and legacy flat-output compatibility |
| `extractors/__init__.py` | Registered domain extractor order |
| `scripts/export_for_sch_review.py` | Canonical writer for `data/sch_review_export/` |
| `scripts/normal_ic_contract.py` | Normal-IC domain assembly and flat compatibility shaping |
| `scripts/parse_pinout.py` | Unified FPGA pinout parser dispatcher |
| `scripts/validate_exports.py` | Schema and semantic validation for public exports |
| `scripts/device_export_view.py` | Compatibility reader for flat and `domains` payloads |

## Common Workflows

Set up:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
python scripts/doctor.py --dev
```

Validate exports:

```bash
python scripts/validate_exports.py --summary
```

Regenerate public exports:

```bash
python scripts/export_for_sch_review.py
```

Run the local gate:

```bash
./scripts/run_checks.sh
```

Run a focused pytest loop on Windows if third-party pytest plugins break due to
local Python DLL issues:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
```

## Topic Routes

- Adding or refreshing a normal IC: [adding-normal-ic-datasheet.md](docs/adding-normal-ic-datasheet.md)
- FPGA parser work: [fpga-pinout-parser-overview.md](docs/fpga-pinout-parser-overview.md)
- Export validation: [export-validation-playbook.md](docs/export-validation-playbook.md)
- Domain model direction: [schema-v2-domains-guide.md](docs/schema-v2-domains-guide.md)
- Hardware review docs: [hardware-engineer-index.md](docs/hardware-engineer-index.md)
- Raw-source policy: [raw-source-storage.md](docs/raw-source-storage.md)
- Release/regeneration decisions: [release-regeneration-matrix.md](docs/release-regeneration-matrix.md)

## Historical Docs

Some documents are preserved as design history or incident notes. They may
contain old counts, old schema names, or planned pipeline behavior. Read them
after the current-state docs, and do not treat them as authoritative unless they
match code, schema, and checked-in data.

Important historical/planning examples:

- [design-document.md](docs/design-document.md)
- [roadmap-v2.md](docs/roadmap-v2.md)
- [ams1117-vision-result.md](docs/ams1117-vision-result.md)
- `docs/Q*.md`
