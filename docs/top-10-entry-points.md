# Top 10 Entry Points

> High-value navigation for people who do not want to browse the whole documentation tree.

## 1. Hardware Engineer Hub

- [`hardware-engineer-index.md`](hardware-engineer-index.md)

Use this first if your question is about:
- schematic review
- power
- clocks
- reset
- FPGA board planning
- bring-up

## 2. Official Best-Practice Baseline

- [`hardware-best-practice-source-basis.md`](hardware-best-practice-source-basis.md)

Use this when you want:
- official-source grounding
- TI / ADI / AMD / Intel / NXP reference pointers
- a sanity check before turning rules into review checklists

## 3. Schematic Freeze Checklist

- [`schematic-freeze-checklist.md`](schematic-freeze-checklist.md)

Use this before:
- schematic release
- layout handoff
- architecture signoff

## 4. Bring-Up Closure Checklist

- [`bring-up-closure-checklist.md`](bring-up-closure-checklist.md)

Use this when asking:
- can first article boards be debugged
- do we have enough observability
- are clocks, resets, rails, and straps actually testable

## 5. FPGA Export Review Checklist

- [`fpga-export-review-checklist.md`](fpga-export-review-checklist.md)

Use this if the task is:
- FPGA package validation
- bank / diff-pair / refclk review
- parser or export sanity checking

## 6. Clock And Refclk Ownership

- [`clock-source-and-refclk-ownership.md`](clock-source-and-refclk-ownership.md)

Use this for:
- SerDes
- PCIe
- display
- any board where “who owns the reference clock” is more important than raw frequency

## 7. Power Tree Review

- [`power-tree-review-checklist.md`](power-tree-review-checklist.md)

Use this for:
- rail architecture
- regulator topology review
- sequencing and measurement planning

## 8. SerDes Link Budget Review

- [`serdes-link-budget-review.md`](serdes-link-budget-review.md)

Use this for:
- high-speed channel loss review
- connector / mux / retimer / refclk path review
- “Gbps looks fine on paper but board risk is unclear” situations

## 9. DDR Buffering And Margin Budget

- [`ddr-buffering-and-margin-budget.md`](ddr-buffering-and-margin-budget.md)

Use this for:
- video ingest / egress systems
- local buffering strategy
- bad-frame capture and replay budget

## 10. Repository Master Index

- [`index.md`](index.md)

Use this only when:
- the task does not fit the nine routes above
- you need a complete map of architecture, data contracts, workflows, FPGA docs, and hardware docs

## If You Only Open Three Docs

Open these:
- [`hardware-engineer-index.md`](hardware-engineer-index.md)
- [`hardware-best-practice-source-basis.md`](hardware-best-practice-source-basis.md)
- one task-specific checklist from the hub
