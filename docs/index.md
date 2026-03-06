# OpenDatasheet Documentation Index

> Topic-oriented map of the repository docs. Use this page when you know **what kind of question** you have, but not yet **which file** to open.

## Start Here

- [`../README.md`](../README.md) — Repository overview, setup, checks, CI, contribution/security/support entry points. **Best for:** first-time readers, contributors, reviewers.
- [`../GUIDE.md`](../GUIDE.md) — Reading guide across data, architecture, code, and workflow. **Best for:** anyone trying to understand the repo quickly.
- [`maintenance.md`](maintenance.md) — Validation, regeneration, migration, and maintainer guardrails. **Best for:** maintainers, release owners, parallel contributors.
- [`commands.md`](commands.md) — Short command reference for setup, checks, export, and release workflows. **Best for:** contributors, maintainers, reviewers.
- [`faq.md`](faq.md) — Short answers to common repository workflow questions. **Best for:** first-time contributors, support triage, reviewers.
- [`troubleshooting.md`](troubleshooting.md) — Common failure modes and recovery steps. **Best for:** contributors, maintainers, support triage.


## Role Quick Reference

- **Contributors** → Start with [`../CONTRIBUTING.md`](../CONTRIBUTING.md), then use [`maintenance.md`](maintenance.md) for validation and regeneration rules.
- **Consumers / Integrators** → Start with [`sch-review-integration.md`](sch-review-integration.md), then confirm field rules in [`../schemas/sch-review-device.schema.json`](../schemas/sch-review-device.schema.json).
- **Maintainers / Release Owners** → Start with [`maintenance.md`](maintenance.md), then use [`../RELEASE.md`](../RELEASE.md) before publishing or coordinating a release.
- **Reviewers** → Start with [`../GUIDE.md`](../GUIDE.md) for context, then jump to [`design-document.md`](design-document.md) / [`maintenance.md`](maintenance.md) depending on whether the change is architectural or operational.

## Architecture

- [`design-document.md`](design-document.md) — Project positioning, system architecture, data flow, and design rationale. **Best for:** architects, reviewers, downstream integrators.
- [`extraction-methodology.md`](extraction-methodology.md) — End-to-end extraction method and why the pipeline uses hybrid Vision + Text. **Best for:** pipeline contributors, evaluators of extraction quality.
- [`roadmap-v2.md`](roadmap-v2.md) — Near-term direction and planned improvements. **Best for:** maintainers, planning discussions.

## Integration

- [`sch-review-integration.md`](sch-review-integration.md) — Export contract, field meanings, and downstream usage patterns. **Best for:** consumers of `data/sch_review_export/`, DRC/integration developers.
- [`design-bundle-export.md`](design-bundle-export.md) — Layered design-helper bundle format for schematic/module bring-up. **Best for:** hardware designers starting a module from a single device export.
- [`design-extraction-validation.md`](design-extraction-validation.md) — Corpus baseline and sample outputs for PDF-aware design extraction. **Best for:** reviewers validating parsing quality and regression coverage.
- [`../schemas/sch-review-device.schema.json`](../schemas/sch-review-device.schema.json) — Formal schema definition for exported device knowledge. **Best for:** schema/tooling maintainers, downstream validators.

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

- Want to understand the repo quickly? → [`../GUIDE.md`](../GUIDE.md)
- Want to run checks safely? → [`maintenance.md`](maintenance.md)
- Want to consume exported JSON? → [`sch-review-integration.md`](sch-review-integration.md)
- Want schematic-oriented starter files? → [`design-bundle-export.md`](design-bundle-export.md)
- Want to change schema or export behavior? → [`../schemas/sch-review-device.schema.json`](../schemas/sch-review-device.schema.json), [`design-document.md`](design-document.md), [`maintenance.md`](maintenance.md)
- Not sure whether something is support, bug, feature, or security? → [`../SUPPORT.md`](../SUPPORT.md), [`../SECURITY.md`](../SECURITY.md)
