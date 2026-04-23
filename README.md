# OpenDatasheet

[![CI](https://github.com/joyhpc/opendatasheet/actions/workflows/ci.yml/badge.svg)](https://github.com/joyhpc/opendatasheet/actions/workflows/ci.yml)
[![Schema](https://img.shields.io/badge/schema-sch--review--device%2F1.1-2f81f7)](schemas/sch-review-device.schema.json)
[![Exports](https://img.shields.io/badge/exports-250%20files-8250df)](data/sch_review_export/)
[![Docs](https://img.shields.io/badge/docs-index-238636)](docs/index.md)

AI-powered electronic component datasheet parameter extraction pipeline.
PDF datasheets → structured JSON for schematic review DRC engines.

## 📖 [Reading Guide](GUIDE.md) — Start here

## Quick Start

- **Setup**: `pip install -r requirements.txt` and `pip install -r requirements-dev.txt`
- **Raw Sources**: new `pdf/xlsx/csv` go to `data/raw/_staging/` first, then run `python3 scripts/build_raw_source_manifest.py` after canonical placement
- **Credentials**: `export GEMINI_API_KEY='<your-api-key>'`
- **First 30 Minutes**: `docs/first-30-minutes.md`
- **Setup Playbook**: `docs/local-setup-playbook.md`
- **Hardware Engineer Hub**: `docs/hardware-engineer-index.md`
- **Doctor**: `python3 scripts/doctor.py --dev`
- **Checks**: `./scripts/run_checks.sh`
- **CI**: `.github/workflows/ci.yml`
- **Contributing**: `CONTRIBUTING.md`
- **Support**: `SUPPORT.md`
- **Security**: `SECURITY.md`
- **Maintenance**: `docs/maintenance.md`
- **Docs Index**: `docs/index.md`
- **Command Cheat Sheet**: `docs/commands.md`
- **FAQ**: `docs/faq.md`
- **Troubleshooting**: `docs/troubleshooting.md`
- **Release Notes**: `RELEASE.md`
- **Maintainers**: `MAINTAINERS.md`

## Who Should Read What?

- **New here?** Start with `GUIDE.md`, then use `docs/index.md` for topic routing.
- **Integrating exports?** Read `docs/sch-review-integration.md` and `schemas/sch-review-device.schema.json`.
- **Maintaining the repo?** Use `docs/maintenance.md`, `MAINTAINERS.md`, and `RELEASE.md`.

## Quick Links

- [First 30 Minutes](docs/first-30-minutes.md) — Fast orientation for new contributors and reviewers
- [Local Setup Playbook](docs/local-setup-playbook.md) — Practical environment bring-up and validation loop
- [Hardware Engineer Index](docs/hardware-engineer-index.md) — Board-review and bring-up oriented hardware docs
- [Extraction Methodology](docs/extraction-methodology.md) — How the Vision + Text hybrid pipeline works
- [Schematic Review Integration](docs/sch-review-integration.md) — Data structures, examples, and Python code for consumers
- [Schema](schemas/sch-review-device.schema.json) — `sch-review-device/1.1` JSON Schema (生成输出已收敛到 `device-knowledge/2.0`)
- [Exported Data](data/sch_review_export/) — 250 checked-in device files ready for consumption

## Pipeline

```
PDF → L0 Page Classification (PyMuPDF + regex)
    → L1a Vision Extraction (Gemini Flash, page images)
    → L1b Pin Extraction (Gemini Flash, page images)
    → L2 Physics Validation (unit/range/consistency checks)
    → L3 Cross-Validation (extracted values vs PDF raw text, 95-100% coverage)
```

## Coverage

| Type | Count | Examples |
|------|-------|---------|
| Normal IC | 167 | LDO, Buck, OpAmp, Switch, ADC/DAC, Interface, SerDes |
| FPGA | 83 | AMD UltraScale+, Gowin GW5AT/GW5AR/GW5AS, Lattice ECP5/CrossLink-NX, Intel Agilex 5 |
| **Total** | **250** | Batch processing 346 PDFs (in progress) |

## Stack

- **PyMuPDF** — PDF rendering + text extraction
- **Gemini 3 Flash** — Multimodal Vision extraction (page images → structured JSON)
- **Pydantic-style validation** — L2 physics rules
- **Cross-validation** — L3 PDF raw text vs extracted values

## Environment

- Set `GEMINI_API_KEY` before running extraction scripts.
- Example: `export GEMINI_API_KEY='<your-api-key>'`
- The pipelines no longer fall back to any hardcoded API key.

## Setup

- Runtime dependencies: `pip install -r requirements.txt`
- Raw-source inventory refresh after adding or moving original source files: `python3 scripts/build_raw_source_manifest.py`
- Strict raw-source reproducibility check: `python3 scripts/build_raw_source_manifest.py --check`
- Dev/test dependencies: `pip install -r requirements-dev.txt`
- Environment self-check: `python3 scripts/doctor.py --dev`
- One-shot local gate: `./scripts/run_checks.sh`
- Optional shortcuts if `make` is available: `make validate`, `make regression`, `make pytest`, `make check`

## CI

- GitHub Actions workflow: `.github/workflows/ci.yml`
- CI runs `./scripts/run_checks.sh`, covering syntax compilation, export schema validation, regression suite, and `pytest` on every push / pull request.

## Raw Source Workflow

- Store finalized canonical originals under `data/raw/`; put unreviewed downloads in `data/raw/_staging/` first
- Rebuild the raw-source manifest with `python3 scripts/build_raw_source_manifest.py` after any `pdf/xlsx/csv` add/move/remove
- Run `python3 scripts/validate_design_extraction.py` for normal validation; use `--strict` before merge/release to catch stale manifest entries
- See `docs/raw-source-storage.md` for the full storage policy and manifest field definitions
