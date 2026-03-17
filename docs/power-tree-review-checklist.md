# Power Tree Review Checklist

> Practical review points for board-level rail planning.

## Questions every rail should answer

- what does this rail power
- what current does it need at steady state and at transient peaks
- what is the startup order requirement
- what is the acceptable tolerance and noise budget
- how will it be measured during bring-up

## Review by rail class

### Entry rails

- input range matches real environment, not lab-only input
- reverse polarity, surge, and hot-plug behavior are covered

### Core rails

- FPGA/SoC core rails have transient margin
- regulator compensation and output capacitance are credible

### IO rails

- VCCO or equivalent rails match actual interface standards
- mixed-voltage assumptions are eliminated early

### Analog rails

- noise-sensitive rails are not afterthoughts
- return path and isolation strategy are explicit

## Common failure modes

- only nominal currents are listed
- rail dependencies are missing
- good regulators selected but bad distribution path
- sequence-sensitive rails treated as independent

## Useful repo data

Use exported limits and hints from:
- `data/sch_review_export/`

For FPGA-centric boards, combine with:
- `banks`
- `supply_specs`
- `constraint_blocks`

## Official practice baseline

Use `hardware-best-practice-source-basis.md` for the power, PDN, and decoupling references behind this checklist.
