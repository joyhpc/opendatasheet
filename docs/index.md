# OpenDatasheet Documentation Index

> Topic-oriented map of the repository docs. Use this page when you know **what kind of question** you have, but not yet **which file** to open.

## Start Here

- [`../README.md`](../README.md) — Repository overview, setup, checks, CI, contribution/security/support entry points. **Best for:** first-time readers, contributors, reviewers.
- [`../GUIDE.md`](../GUIDE.md) — Reading guide across data, architecture, code, and workflow. **Best for:** anyone trying to understand the repo quickly.
- [`first-30-minutes.md`](first-30-minutes.md) — Fast orientation for contributors and reviewers in their first half hour. **Best for:** new collaborators, reviewers, drive-by contributors.
- [`local-setup-playbook.md`](local-setup-playbook.md) — Practical environment setup and minimum local validation loop. **Best for:** anyone bringing up a fresh checkout.
- [`maintenance.md`](maintenance.md) — Validation, regeneration, migration, and maintainer guardrails. **Best for:** maintainers, release owners, parallel contributors.
- [`commands.md`](commands.md) — Short command reference for setup, checks, export, and release workflows. **Best for:** contributors, maintainers, reviewers.
- [`faq.md`](faq.md) — Short answers to common repository workflow questions. **Best for:** first-time contributors, support triage, reviewers.
- [`troubleshooting.md`](troubleshooting.md) — Common failure modes and recovery steps. **Best for:** contributors, maintainers, support triage.

## Role Quick Reference

- **Contributors** → Start with [`../CONTRIBUTING.md`](../CONTRIBUTING.md), then [`first-30-minutes.md`](first-30-minutes.md), then [`local-setup-playbook.md`](local-setup-playbook.md).
- **Consumers / Integrators** → Start with [`sch-review-integration.md`](sch-review-integration.md), then [`consumer-query-recipes.md`](consumer-query-recipes.md), then confirm field rules in [`../schemas/sch-review-device.schema.json`](../schemas/sch-review-device.schema.json).
- **Maintainers / Release Owners** → Start with [`maintenance.md`](maintenance.md), then [`release-regeneration-matrix.md`](release-regeneration-matrix.md), then [`../RELEASE.md`](../RELEASE.md).
- **Reviewers** → Start with [`../GUIDE.md`](../GUIDE.md), then jump to [`design-document.md`](design-document.md), [`export-validation-playbook.md`](export-validation-playbook.md), and [`regression-workflow.md`](regression-workflow.md).
- **FPGA Contributors** → Start with [`fpga-pinout-parser-overview.md`](fpga-pinout-parser-overview.md), then use the vendor-specific workflow docs below.

## Architecture

- [`design-document.md`](design-document.md) — Project positioning, system architecture, data flow, and design rationale. **Best for:** architects, reviewers, downstream integrators.
- [`extraction-methodology.md`](extraction-methodology.md) — End-to-end extraction method and why the pipeline uses hybrid Vision + Text. **Best for:** pipeline contributors, evaluators of extraction quality.
- [`extractor-domain-map.md`](extractor-domain-map.md) — Ownership map for modular extractor domains and why boundaries matter. **Best for:** pipeline contributors, schema maintainers.
- [`schema-v2-domains-guide.md`](schema-v2-domains-guide.md) — Practical notes on `device-knowledge/2.0` and the `domains` container. **Best for:** schema maintainers, migration reviewers.
- [`a57-class-fpga-architecture-notes.md`](a57-class-fpga-architecture-notes.md) — Deep architecture notes from an A57-class automotive camera/domain-controller platform viewpoint, focusing on DDR, MIPI, SerDes, and heterogeneous FPGA partitioning. **Best for:** board architects, schematic owners, and platform review.
- [`fpga-board-architecture-comparison.md`](fpga-board-architecture-comparison.md) — Board-architect comparison of AMD, Intel/Altera, Lattice, and Gowin using the currently validated FPGA families. **Best for:** schematic owners, platform architects, FPGA selection reviews.
- [`roadmap-v2.md`](roadmap-v2.md) — Near-term direction and planned improvements. **Best for:** maintainers, planning discussions.

## Data Contracts

- [`sch-review-integration.md`](sch-review-integration.md) — Export contract, field meanings, and downstream usage patterns. **Best for:** consumers of `data/sch_review_export/`, DRC/integration developers.
- [`consumer-query-recipes.md`](consumer-query-recipes.md) — Short downstream lookup patterns for normal IC and FPGA data. **Best for:** integrators, DRC/tool authors.
- [`export-file-naming.md`](export-file-naming.md) — Naming rules for extracted, exported, and FPGA package-qualified outputs. **Best for:** maintainers, tooling authors, reviewers.
- [`normal-ic-export-field-guide.md`](normal-ic-export-field-guide.md) — Quick reference for flat normal-IC export fields. **Best for:** downstream consumers, reviewers.
- [`fpga-export-field-guide.md`](fpga-export-field-guide.md) — Quick reference for flat FPGA export fields. **Best for:** downstream consumers, FPGA DRC developers.
- [`raw-manifest-field-guide.md`](raw-manifest-field-guide.md) — Field guide for `data/raw/_source_manifest.json`. **Best for:** maintainers, raw-source curators.
- [`selection-profile-guide.md`](selection-profile-guide.md) — How to generate and use comparison-oriented selection profile outputs. **Best for:** selector tooling, component comparison work.
- [`design-bundle-export.md`](design-bundle-export.md) — Layered design-helper bundle format for schematic/module bring-up. **Best for:** hardware designers starting a module from a single device export.
- [`design-bundle-workflow.md`](design-bundle-workflow.md) — Practical generation workflow for design bundles. **Best for:** hardware contributors, maintainers.
- [`design-extraction-validation.md`](design-extraction-validation.md) — Corpus baseline and sample outputs for PDF-aware design extraction. **Best for:** reviewers validating parsing quality and regression coverage.
- [`design-extraction-reporting.md`](design-extraction-reporting.md) — How to regenerate the human-readable design extraction report and samples. **Best for:** maintainers, extraction reviewers.
- [`../schemas/sch-review-device.schema.json`](../schemas/sch-review-device.schema.json) — Formal schema definition for exported device knowledge. **Best for:** schema/tooling maintainers, downstream validators.

## Workflows

- [`adding-normal-ic-datasheet.md`](adding-normal-ic-datasheet.md) — Intake-to-export workflow for a new normal IC datasheet. **Best for:** data curators, extraction contributors.
- [`batch-processing-runbook.md`](batch-processing-runbook.md) — Safe batch-processing patterns for `batch_all.py`. **Best for:** extraction operators, maintainers.
- [`export-validation-playbook.md`](export-validation-playbook.md) — How to run and interpret export validation. **Best for:** maintainers, reviewers.
- [`regression-workflow.md`](regression-workflow.md) — How to use `test_regression.py` and `pytest` efficiently. **Best for:** maintainers, contributors.
- [`release-regeneration-matrix.md`](release-regeneration-matrix.md) — Decision table for whether a change needs regeneration. **Best for:** maintainers, release owners, reviewers.
- [`raw-source-storage.md`](raw-source-storage.md) — Storage policy for original source files. **Best for:** maintainers, data curators.

## FPGA Workflows

- [`fpga-pinout-parser-overview.md`](fpga-pinout-parser-overview.md) — Cross-vendor map of the FPGA pinout parsers in this repo. **Best for:** FPGA contributors, reviewers.
- [`amd-pinout-workflow.md`](amd-pinout-workflow.md) — Workflow for AMD/Xilinx UltraScale+ TXT pinout parsing. **Best for:** AMD FPGA contributors.
- [`gowin-pinout-workflow.md`](gowin-pinout-workflow.md) — Workflow for Gowin XLSX pinout parsing. **Best for:** Gowin FPGA contributors.
- [`lattice-pinout-workflow.md`](lattice-pinout-workflow.md) — Workflow for Lattice ECP5 / CrossLink-NX pinout parsing. **Best for:** Lattice FPGA contributors.
- [`intel-agilex5-pinout-workflow.md`](intel-agilex5-pinout-workflow.md) — Workflow for Intel Agilex 5 OOXML workbook parsing. **Best for:** Intel/Altera FPGA contributors.
- [`fpga-export-review-checklist.md`](fpga-export-review-checklist.md) — Concrete review checklist for new or regenerated FPGA exports. **Best for:** reviewers, maintainers.
- [`fpga-catalog-usage.md`](fpga-catalog-usage.md) — How to generate and use `_fpga_catalog.json`. **Best for:** coverage review, navigation tooling.

## Technical Deep Dives

- [`Q1-negative-value-validation.md`](Q1-negative-value-validation.md) — Negative-value interpretation and dual-rail inference. **Best for:** validation logic maintainers.
- [`Q2-negative-text-matching.md`](Q2-negative-text-matching.md) — Minus-sign normalization and text matching details. **Best for:** cross-validation and parsing maintainers.
- [`Q3-pin-schema-design.md`](Q3-pin-schema-design.md) — Multi-package logical pin model design. **Best for:** export/schema maintainers.
- [`Q4-fpga-drc-data-loading-strategy.md`](Q4-fpga-drc-data-loading-strategy.md) — FPGA DRC data loading and code/LLM responsibility split. **Best for:** FPGA and downstream DRC maintainers.

## Operations

- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — Contributor workflow, generated data policy, and validation expectations. **Best for:** contributors preparing a PR.
- [`../SUPPORT.md`](../SUPPORT.md) — Bug/support/feature/security routing guide. **Best for:** users unsure which channel to use.
- [`../SECURITY.md`](../SECURITY.md) — Private security reporting policy and response boundary. **Best for:** reporters of secrets exposure or exploitable issues.
- [`../RELEASE.md`](../RELEASE.md) — Lightweight release and regeneration checklist. **Best for:** release owners.
- [`../MAINTAINERS.md`](../MAINTAINERS.md) — Maintainer review boundary and escalation guide. **Best for:** maintainers, reviewers, parallel contributors.

## Example / Reference Artifacts

- [`ams1117-vision-result.md`](ams1117-vision-result.md) — Human-readable example of a vision extraction result. **Best for:** readers wanting a concrete sample.
- [`ams1117-vision-raw.json`](ams1117-vision-raw.json) — Raw example output for the same sample. **Best for:** debugging output shape or prompt behavior.

## Quick Routing

- Want the fastest repo orientation? → [`first-30-minutes.md`](first-30-minutes.md)
- Want setup and local checks? → [`local-setup-playbook.md`](local-setup-playbook.md)
- Want to add a new datasheet? → [`adding-normal-ic-datasheet.md`](adding-normal-ic-datasheet.md)
- Want to batch-process PDFs? → [`batch-processing-runbook.md`](batch-processing-runbook.md)
- Want to understand the export contract? → [`sch-review-integration.md`](sch-review-integration.md), [`normal-ic-export-field-guide.md`](normal-ic-export-field-guide.md), [`fpga-export-field-guide.md`](fpga-export-field-guide.md)
- Want to consume exported JSON? → [`consumer-query-recipes.md`](consumer-query-recipes.md)
- Want design-helper bundles? → [`design-bundle-workflow.md`](design-bundle-workflow.md)
- Want schema or domain migration context? → [`schema-v2-domains-guide.md`](schema-v2-domains-guide.md), [`../schemas/sch-review-device.schema.json`](../schemas/sch-review-device.schema.json)
- Want FPGA parser context? → [`fpga-pinout-parser-overview.md`](fpga-pinout-parser-overview.md)
- Want release / regeneration rules? → [`release-regeneration-matrix.md`](release-regeneration-matrix.md)
- Not sure whether something is support, bug, feature, or security? → [`../SUPPORT.md`](../SUPPORT.md), [`../SECURITY.md`](../SECURITY.md)
