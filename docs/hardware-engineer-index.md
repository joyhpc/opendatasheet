# Hardware Engineer Index

> Practical document hub for schematic owners, board architects, bring-up engineers, and FPGA platform reviewers.

## Start Here

- `top-10-entry-points.md`
- `hardware-best-practice-source-basis.md`
- `schematic-freeze-checklist.md`
- `bring-up-closure-checklist.md`
- `power-tree-review-checklist.md`
- `clock-source-and-refclk-ownership.md`
- `test-point-and-observability-strategy.md`

## Power

- `power-entry-protection-review.md`
- `rail-sequencing-review.md`
- `decoupling-placement-review.md`
- `power-rail-measurement-plan.md`
- `thermal-risk-review.md`

## Clocks, Reset, Debug

- `oscillator-and-crystal-review.md`
- `reset-and-supervisor-review.md`
- `jtag-swd-debug-header-review.md`
- `flash-boot-chain-review.md`
- `field-recovery-and-safe-mode-design.md`

## FPGA And High-Speed

- `mcu-fpga-boundary-patterns.md`
- `bank-vcco-planning.md`
- `lane-swapping-and-polarity-review.md`
- `diff-pair-return-path-review.md`
- `board-partitioning-center-edge-fpga.md`

## Interface Reviews

- `mipi-dphy-board-review.md`
- `camera-deserializer-ingress-review.md`
- `display-interface-review.md`
- `serdes-link-budget-review.md`
- `redriver-retimer-switch-review.md`
- `pcie-aic-board-review.md`
- `ddr-buffering-and-margin-budget.md`
- `i2c-control-bus-review.md`
- `control-plane-status-and-gpio-review.md`
- `level-shifting-and-voltage-domain-review.md`
- `connector-and-cable-review.md`
- `esd-tvs-selection-review.md`
- `assembly-options-and-stuffing-strategy.md`
- `aging-stress-platform-review.md`

## Why these docs exist

This repo is not only about extracting datasheets. It is increasingly a working knowledge base for turning device facts into board-level decisions.

Use these docs together with:
- `data/sch_review_export/`
- `docs/a57-class-fpga-architecture-notes.md`
- `docs/fpga-board-architecture-comparison.md`
- `docs/fpga-export-review-checklist.md`

## Advanced Topic Library

For deeper single-topic notes, also use:
- `hardware-engineering/`

Examples:
- `hardware-engineering/fpga-transceiver-reference-clock.md`
- `hardware-engineering/ddr-layout-review-checklist.md`
- `hardware-engineering/ethernet-phy-bringup-checklist.md`
- `hardware-engineering/usb2-protection-and-routing.md`
