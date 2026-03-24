# OpenDatasheet Documentation Index

> Topic-oriented map of the repository docs. Use this page when you know **what kind of question** you have, but not yet **which file** to open.

## Start Here

- [`../README.md`](../README.md) — Repository overview, setup, checks, CI, contribution/security/support entry points. **Best for:** first-time readers, contributors, reviewers.
- [`../GUIDE.md`](../GUIDE.md) — Reading guide across data, architecture, code, and workflow. **Best for:** anyone trying to understand the repo quickly.
- [`top-10-entry-points.md`](top-10-entry-points.md) — Compressed high-value navigation across the most useful docs. **Best for:** readers who want the shortest path to the right document.
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
- [`page-classification-and-routing.md`](page-classification-and-routing.md) — L0 routing model, page categories, and why narrow page selection is the primary cost-control layer. **Best for:** pipeline contributors tuning selectors or adding domains.
- [`extractor-registry-contract.md`](extractor-registry-contract.md) — `BaseExtractor` contract, registry order semantics, and rules for adding a new domain. **Best for:** extractor authors and reviewers.
- [`domain-cost-control.md`](domain-cost-control.md) — Cost-class thinking for cheap, medium, and expensive domains. **Best for:** maintainers deciding whether a domain belongs on the always-on path.
- [`discrete-component-fast-path.md`](discrete-component-fast-path.md) — Why and how simple discrete semiconductors take a narrowed extraction path. **Best for:** contributors working on Transistor / diode / TVS / MOSFET corpora.
- [`extractor-domain-map.md`](extractor-domain-map.md) — Ownership map for modular extractor domains and why boundaries matter. **Best for:** pipeline contributors, schema maintainers.
- [`schema-v2-domains-guide.md`](schema-v2-domains-guide.md) — Practical notes on `device-knowledge/2.0` and the `domains` container. **Best for:** schema maintainers, migration reviewers.
- [`a57-class-fpga-architecture-notes.md`](a57-class-fpga-architecture-notes.md) — Deep architecture notes from an A57-class automotive camera/domain-controller platform viewpoint, focusing on DDR, MIPI, SerDes, and heterogeneous FPGA partitioning. **Best for:** board architects, schematic owners, and platform review.
- [`fpga-board-architecture-comparison.md`](fpga-board-architecture-comparison.md) — Board-architect comparison of AMD, Intel/Altera, Lattice, and Gowin using the currently validated FPGA families. **Best for:** schematic owners, platform architects, FPGA selection reviews.
- [`roadmap-v2.md`](roadmap-v2.md) — Near-term direction and planned improvements. **Best for:** maintainers, planning discussions.

## Hardware Engineering

- [`hardware-engineer-index.md`](hardware-engineer-index.md) — Landing page for board architects, schematic owners, and bring-up engineers. **Best for:** hardware engineers who want the curated path through this doc set.
- [`hardware-best-practice-source-basis.md`](hardware-best-practice-source-basis.md) — Official-source baseline used to tighten the hardware engineering docs. **Best for:** reviewers who want primary-source grounding.
- [`hardware-engineering/`](hardware-engineering/) — Advanced single-topic hardware engineering library covering power, clocks, FPGA, DDR, interfaces, and analog front ends. **Best for:** engineers who want focused deep dives after the main index.
- [`schematic-freeze-checklist.md`](schematic-freeze-checklist.md) — Final pre-freeze review list for complex boards. **Best for:** schematic owners and board leads.
- [`power-tree-review-checklist.md`](power-tree-review-checklist.md) — Rail-planning questions that should be answered before layout. **Best for:** power owners, platform reviewers.
- [`clock-source-and-refclk-ownership.md`](clock-source-and-refclk-ownership.md) — Treating clocks and refclks as ownership problems, not just frequencies. **Best for:** FPGA/high-speed board architects.
- [`test-point-and-observability-strategy.md`](test-point-and-observability-strategy.md) — Observability planning for bring-up and failure isolation. **Best for:** bring-up engineers.
- [`mcu-fpga-boundary-patterns.md`](mcu-fpga-boundary-patterns.md) — Partitioning control-plane and protocol complexity between MCU and FPGA. **Best for:** mixed MCU-FPGA platform designers.
- [`bank-vcco-planning.md`](bank-vcco-planning.md) — FPGA bank-voltage planning before pin usage hardens into layout debt. **Best for:** FPGA schematic owners.
- [`mipi-dphy-board-review.md`](mipi-dphy-board-review.md) — Board-level review for MIPI ingress implementation. **Best for:** camera-ingress board designers.
- [`serdes-link-budget-review.md`](serdes-link-budget-review.md) — End-to-end loss and margin thinking for serial links. **Best for:** high-speed board reviewers.
- [`pcie-aic-board-review.md`](pcie-aic-board-review.md) — PCIe add-in-card and edge-connector review checklist. **Best for:** PCIe board designers.
- [`ddr-buffering-and-margin-budget.md`](ddr-buffering-and-margin-budget.md) — Treating DDR as elasticity and debug budget, not just capacity. **Best for:** video and routing platform architects.
- [`thermal-risk-review.md`](thermal-risk-review.md) — Early thermal review that ties back to power and workload. **Best for:** board leads and bring-up teams.
- [`i2c-control-bus-review.md`](i2c-control-bus-review.md) — Practical control-bus review for pull-ups, capacitance, and segmentation. **Best for:** board designers and bring-up engineers.
- [`esd-tvs-selection-review.md`](esd-tvs-selection-review.md) — ESD and TVS review grounded in placement and return path. **Best for:** connector and interface owners.

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

## Hardware Engineering

- [`hardware-engineering/index.md`](hardware-engineering/index.md) — 50 篇面向硬件工程师的评审、选型、布局、bring-up 文档总索引。 **Best for:** schematic owners, bring-up engineers, board architects.
- [`hardware-engineering/best-practice-reference-matrix.md`](hardware-engineering/best-practice-reference-matrix.md) — 这些硬件文档背后的官方最佳实践来源矩阵。 **Best for:** reviewers who want source-oriented traceability.

## Workflows

- [`adding-normal-ic-datasheet.md`](adding-normal-ic-datasheet.md) — Intake-to-export workflow for a new normal IC datasheet. **Best for:** data curators, extraction contributors.
- [`automotive-video-serdes-normalization.md`](automotive-video-serdes-normalization.md) — 车载视频 serializer / deserializer / bridge 的统一能力模型、profile 机制，以及新同类芯片进入仓库时的处理流程。 **Best for:** 维护者、下游 integrator、同类器件扩展贡献者。
- [`cxd4984-closure-note.md`](cxd4984-closure-note.md) — `CXD4984ER-W` 从 Google Drive 资料到正式 raw/extracted/export/selection 数据的闭环说明，包含下游消费建议和 Mermaid 图。 **Best for:** issue 跟进者、下游 integrator、维护者复盘具体闭环案例。
- [`batch-processing-runbook.md`](batch-processing-runbook.md) — Safe batch-processing patterns for `batch_all.py`. **Best for:** extraction operators, maintainers.
- [`gemini-api-operations.md`](gemini-api-operations.md) — Separating key failures, hangs, and structured extraction problems in Gemini-backed flows. **Best for:** extraction operators and maintainers.
- [`invalid-pdf-triage.md`](invalid-pdf-triage.md) — How to identify fake PDFs and treat them as raw-source defects instead of parser bugs. **Best for:** corpus maintainers and batch triage.
- [`raw-source-quality-gates.md`](raw-source-quality-gates.md) — Canonical raw-source hygiene rules, manifest refresh expectations, and deletion policy for bad inputs. **Best for:** data maintainers.
- [`export-validation-playbook.md`](export-validation-playbook.md) — How to run and interpret export validation. **Best for:** maintainers, reviewers.
- [`regression-workflow.md`](regression-workflow.md) — How to use `test_regression.py` and `pytest` efficiently. **Best for:** maintainers, contributors.
- [`test-strategy-and-regression.md`](test-strategy-and-regression.md) — Test layering, incident-driven regression additions, and what good policy coverage looks like. **Best for:** contributors fixing bugs or adding maintainability tests.
- [`release-regeneration-matrix.md`](release-regeneration-matrix.md) — Decision table for whether a change needs regeneration. **Best for:** maintainers, release owners, reviewers.
- [`raw-source-storage.md`](raw-source-storage.md) — Storage policy for original source files. **Best for:** maintainers, data curators.
- [`transistor-batch-postmortem-2026-03.md`](transistor-batch-postmortem-2026-03.md) — Incident review of the Transistor corpus cleanup, fast-path rollout, and bad-PDF removal. **Best for:** maintainers wanting historical context for recent routing changes.

## FPGA Workflows

- [`fpga-pinout-parser-overview.md`](fpga-pinout-parser-overview.md) — Cross-vendor map of the FPGA pinout parsers in this repo. **Best for:** FPGA contributors, reviewers.
- [`anlogic-ph1a-source-intake.md`](anlogic-ph1a-source-intake.md) — Initial intake notes for the imported Anlogic `PH1A` family source bundle, including current support boundaries and missing pinout sources. **Best for:** FPGA maintainers planning Anlogic support.
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
- [`electrical-domain-contract.md`](electrical-domain-contract.md) — Role of the electrical domain as the first trustworthy component-identity anchor. **Best for:** electrical extractor maintainers.
- [`pin-domain-contract.md`](pin-domain-contract.md) — Logical pin modeling, package-aware mappings, and why `pin` remains valuable for simple discretes. **Best for:** pin/schema maintainers.
- [`thermal-and-parametric-derivation.md`](thermal-and-parametric-derivation.md) — Why `thermal` and part of `parametric` should prefer derivation over new image-heavy passes. **Best for:** maintainers deciding where to normalize vs re-extract.
- [`package-domain-guidelines.md`](package-domain-guidelines.md) — When package extraction adds real value and when it is just expensive noise. **Best for:** package-domain contributors.
- [`design-domain-guidelines.md`](design-domain-guidelines.md) — Boundary between `design_context` and `design_guide`, and how to keep design extraction focused. **Best for:** design-domain contributors.
- [`timing-domain-guidelines.md`](timing-domain-guidelines.md) — When timing extraction matters and why it should be skipped for simple discrete parts. **Best for:** timing-domain maintainers.
- [`register-domain-guidelines.md`](register-domain-guidelines.md) — Register-map extraction boundary and validation priorities. **Best for:** register-domain maintainers.
- [`protocol-domain-guidelines.md`](protocol-domain-guidelines.md) — Communication-interface extraction boundary and common selector mistakes. **Best for:** protocol-domain maintainers.
- [`power-sequence-domain-guidelines.md`](power-sequence-domain-guidelines.md) — Where structured sequencing adds value and where it should stay off. **Best for:** PMIC and sequencing-domain contributors.
- [`discrete-export-normalization.md`](discrete-export-normalization.md) — How discrete parts normalize into downstream export and selection-profile semantics. **Best for:** export and downstream tooling maintainers.

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
- Want the hardware-engineering doc hub? → [`hardware-engineer-index.md`](hardware-engineer-index.md)
- Want to add a new datasheet? → [`adding-normal-ic-datasheet.md`](adding-normal-ic-datasheet.md)
- Want to batch-process PDFs? → [`batch-processing-runbook.md`](batch-processing-runbook.md)
- Want to understand why some parts skip heavy domains? → [`discrete-component-fast-path.md`](discrete-component-fast-path.md)
- Want to debug Gemini auth vs hang behavior? → [`gemini-api-operations.md`](gemini-api-operations.md)
- Want to debug a bad raw file before touching prompts? → [`invalid-pdf-triage.md`](invalid-pdf-triage.md)
- Want to understand the export contract? → [`sch-review-integration.md`](sch-review-integration.md), [`normal-ic-export-field-guide.md`](normal-ic-export-field-guide.md), [`fpga-export-field-guide.md`](fpga-export-field-guide.md)
- Want hardware review and bring-up checklists? → [`hardware-engineering/index.md`](hardware-engineering/index.md)
- Want to consume exported JSON? → [`consumer-query-recipes.md`](consumer-query-recipes.md)
- Want design-helper bundles? → [`design-bundle-workflow.md`](design-bundle-workflow.md)
- Want schema or domain migration context? → [`schema-v2-domains-guide.md`](schema-v2-domains-guide.md), [`../schemas/sch-review-device.schema.json`](../schemas/sch-review-device.schema.json)
- Want FPGA parser context? → [`fpga-pinout-parser-overview.md`](fpga-pinout-parser-overview.md)
- Want release / regeneration rules? → [`release-regeneration-matrix.md`](release-regeneration-matrix.md)
- Not sure whether something is support, bug, feature, or security? → [`../SUPPORT.md`](../SUPPORT.md), [`../SECURITY.md`](../SECURITY.md)
