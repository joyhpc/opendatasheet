# Top 10 Entry Points

> High-value navigation for people who do not want to browse the whole documentation tree.
> For repository architecture and extraction behavior, start with the current-state and architecture docs before reading historical notes.

## 1. Current Repository State

- [`current-state.md`](current-state.md)

Use this first when you need the audited facts:
- current checked-in export count
- schema target and validation status
- which extraction paths are actually present
- known gaps and caveats

## 2. Repository Architecture

- [`architecture.md`](architecture.md)

Use this for:
- data flow across raw inputs, extracted data, normalized exports, and validation
- module responsibilities
- extractor registry behavior
- schema and export boundaries

## 3. Schematic Review Integration

- [`sch-review-integration.md`](sch-review-integration.md)

Use this when consuming `data/sch_review_export/` from a schematic review or DRC tool.

## 4. Schema V2 Domains Guide

- [`schema-v2-domains-guide.md`](schema-v2-domains-guide.md)

Use this when you need the public export shape, domain meanings, compatibility rules, and coverage expectations.

## 5. Extractor Domain Map

- [`extractor-domain-map.md`](extractor-domain-map.md)

Use this when you need to know which extractor owns each domain, which domains are model-backed, and which domains are derived or currently sparse.

## 6. Extraction Methodology

- [`extraction-methodology.md`](extraction-methodology.md)

Use this to avoid the common mistake of describing the repo as a pure Gemini Vision pipeline. The current corpus combines model-backed extraction, deterministic FPGA parsing, manual/curated profiles, and derived domains.

## 7. FPGA Pinout Parser Overview

- [`fpga-pinout-parser-overview.md`](fpga-pinout-parser-overview.md)

Use this for FPGA package data, vendor parser behavior, bank/differential-pair structure, and FPGA export review.

## 8. Export Validation Playbook

- [`export-validation-playbook.md`](export-validation-playbook.md)

Use this before trusting a refreshed export set or changing the schema/export path.

## 9. Hardware Engineer Hub

- [`hardware-engineer-index.md`](hardware-engineer-index.md)

Use this for hardware review tasks such as schematic review, power, clocks, reset, FPGA board planning, and bring-up.

## 10. Troubleshooting And Commands

- [`troubleshooting.md`](troubleshooting.md)
- [`commands.md`](commands.md)

Use these when you need the exact local commands or an explanation for common local failures.

## If You Only Open Three Docs

Open these:
- [`current-state.md`](current-state.md)
- [`architecture.md`](architecture.md)
- [`sch-review-integration.md`](sch-review-integration.md)
