# OpenDatasheet Documentation Index

This index separates current authoritative docs from historical notes and
topic-specific hardware reference material. Start with the current-state docs
when repository architecture, counts, or data provenance matters.

## Trust Tiers

### Tier 1: Current Repository Facts

Read these first. They are maintained against code, schema, validators, and
checked-in data.

- [Current State](current-state.md): audited counts, provenance, coverage, gaps.
- [Architecture](architecture.md): current data flow, module boundaries, contracts.
- [Schematic Review Integration](sch-review-integration.md): public export usage.
- [Schema v2 Domains Guide](schema-v2-domains-guide.md): current domain model.
- [Extractor Domain Map](extractor-domain-map.md): extractor ownership and status.
- [README](../README.md): short repository overview.
- [Reading Guide](../GUIDE.md): quick reader routing.
- [Schema](../schemas/sch-review-device.schema.json): formal contract.

### Tier 2: Workflow And Contract Docs

These should match current code, but they are narrower than Tier 1.

- [First 30 Minutes](first-30-minutes.md)
- [Local Setup Playbook](local-setup-playbook.md)
- [Commands](commands.md)
- [Maintenance](maintenance.md)
- [Export Validation Playbook](export-validation-playbook.md)
- [Regression Workflow](regression-workflow.md)
- [Test Strategy And Regression](test-strategy-and-regression.md)
- [Release Regeneration Matrix](release-regeneration-matrix.md)
- [Raw Source Storage](raw-source-storage.md)
- [Raw Manifest Field Guide](raw-manifest-field-guide.md)
- [Raw Source Quality Gates](raw-source-quality-gates.md)
- [Export File Naming](export-file-naming.md)
- [Consumer Query Recipes](consumer-query-recipes.md)
- [Selection Profile Guide](selection-profile-guide.md)
- [Design Bundle Workflow](design-bundle-workflow.md)
- [Design Bundle Export](design-bundle-export.md)

### Tier 3: Historical, Planning, Or Case Notes

These are useful context, but may contain old counts, old schema names, or
plans that were not fully implemented. Do not treat them as source of truth
unless they agree with Tier 1 and code.

- [Design Document](design-document.md)
- [Roadmap v2](roadmap-v2.md)
- [AMS1117 Vision Result](ams1117-vision-result.md)
- [Q1 Negative Value Validation](Q1-negative-value-validation.md)
- [Q2 Negative Text Matching](Q2-negative-text-matching.md)
- [Q3 Pin Schema Design](Q3-pin-schema-design.md)
- [Q4 FPGA DRC Data Loading Strategy](Q4-fpga-drc-data-loading-strategy.md)
- [Transistor Batch Postmortem 2026-03](transistor-batch-postmortem-2026-03.md)
- [CXD4984 Closure Note](cxd4984-closure-note.md)
- [Automotive Video SerDes Normalization](automotive-video-serdes-normalization.md)

## Architecture And Extraction

- [Architecture](architecture.md)
- [Extraction Methodology](extraction-methodology.md)
- [Page Classification And Routing](page-classification-and-routing.md)
- [Extractor Registry Contract](extractor-registry-contract.md)
- [Extractor Domain Map](extractor-domain-map.md)
- [Domain Cost Control](domain-cost-control.md)
- [Thermal And Parametric Derivation](thermal-and-parametric-derivation.md)
- [Electrical Domain Contract](electrical-domain-contract.md)
- [Pin Domain Contract](pin-domain-contract.md)
- [Package Domain Guidelines](package-domain-guidelines.md)
- [Design Domain Guidelines](design-domain-guidelines.md)
- [Timing Domain Guidelines](timing-domain-guidelines.md)
- [Register Domain Guidelines](register-domain-guidelines.md)
- [Protocol Domain Guidelines](protocol-domain-guidelines.md)
- [Power Sequence Domain Guidelines](power-sequence-domain-guidelines.md)
- [Discrete Component Fast Path](discrete-component-fast-path.md)
- [Discrete Export Normalization](discrete-export-normalization.md)

## Data Contracts

- [Schematic Review Integration](sch-review-integration.md)
- [Schema v2 Domains Guide](schema-v2-domains-guide.md)
- [Normal IC Export Field Guide](normal-ic-export-field-guide.md)
- [FPGA Export Field Guide](fpga-export-field-guide.md)
- [FPGA Catalog Usage](fpga-catalog-usage.md)
- [Export File Naming](export-file-naming.md)
- [Consumer Query Recipes](consumer-query-recipes.md)
- [Selection Profile Guide](selection-profile-guide.md)
- [Design Extraction Validation](design-extraction-validation.md)
- [Design Extraction Reporting](design-extraction-reporting.md)

## FPGA Workflows

- [FPGA Pinout Parser Overview](fpga-pinout-parser-overview.md)
- [AMD Pinout Workflow](amd-pinout-workflow.md)
- [Gowin Pinout Workflow](gowin-pinout-workflow.md)
- [Lattice Pinout Workflow](lattice-pinout-workflow.md)
- [Intel Agilex 5 Pinout Workflow](intel-agilex5-pinout-workflow.md)
- [Anlogic PH1A Source Intake](anlogic-ph1a-source-intake.md)
- [FPGA Export Review Checklist](fpga-export-review-checklist.md)

## Operations

- [Adding Normal IC Datasheet](adding-normal-ic-datasheet.md)
- [Batch Processing Runbook](batch-processing-runbook.md)
- [Gemini API Operations](gemini-api-operations.md)
- [Invalid PDF Triage](invalid-pdf-triage.md)
- [Troubleshooting](troubleshooting.md)
- [FAQ](faq.md)
- [Release Regeneration Matrix](release-regeneration-matrix.md)
- [Maintenance](maintenance.md)
- [Contributing](../CONTRIBUTING.md)
- [Support](../SUPPORT.md)
- [Security](../SECURITY.md)

## Hardware Engineering Reference

The hardware-engineering docs are a board-review knowledge base. They are useful
for schematic review and bring-up thinking, but they are not the source of truth
for repository architecture or data counts.

- [Hardware Engineer Index](hardware-engineer-index.md)
- [Hardware Best Practice Source Basis](hardware-best-practice-source-basis.md)
- [Hardware Engineering Library Index](hardware-engineering/index.md)
- [Schematic Freeze Checklist](schematic-freeze-checklist.md)
- [Power Tree Review Checklist](power-tree-review-checklist.md)
- [Bank VCCO Planning](bank-vcco-planning.md)
- [Clock Source And Refclk Ownership](clock-source-and-refclk-ownership.md)
- [Test Point And Observability Strategy](test-point-and-observability-strategy.md)
- [MCU FPGA Boundary Patterns](mcu-fpga-boundary-patterns.md)
- [MIPI D-PHY Board Review](mipi-dphy-board-review.md)
- [SerDes Link Budget Review](serdes-link-budget-review.md)
- [PCIe AIC Board Review](pcie-aic-board-review.md)
- [DDR Buffering And Margin Budget](ddr-buffering-and-margin-budget.md)
- [Thermal Risk Review](thermal-risk-review.md)
- [I2C Control Bus Review](i2c-control-bus-review.md)
- [ESD TVS Selection Review](esd-tvs-selection-review.md)

## Quick Routing

- Need current counts or provenance? Read [Current State](current-state.md).
- Need to know where a code change belongs? Read [Architecture](architecture.md).
- Need to consume exports? Read [Schematic Review Integration](sch-review-integration.md).
- Need schema details? Read [Schema v2 Domains Guide](schema-v2-domains-guide.md) and the JSON schema.
- Need FPGA parser context? Read [FPGA Pinout Parser Overview](fpga-pinout-parser-overview.md).
- Need local validation commands? Read [Commands](commands.md) and [Export Validation Playbook](export-validation-playbook.md).
- Need board-review guidance? Start from [Hardware Engineer Index](hardware-engineer-index.md).
