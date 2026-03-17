# Aging Stress Platform Review

> Review pattern for boards intended to run long-duration camera, display, or domain-controller stress tests.

## Architecture priorities

- ingress and egress paths can be stressed independently
- bad-frame capture has buffer budget
- link-loss and recovery paths are observable
- thermal steady-state behavior is part of the design, not only the test plan

## Board-level priorities

- rails can be monitored over long runs
- clocks and refclks have failure observability
- logging path survives the failure modes you care about

## Common mistakes

- platform designed for nominal demo, then repurposed for aging
- no buffer reserved for failure capture
- no thought given to what happens after partial link loss

## Strong companion docs

- `a57-class-fpga-architecture-notes.md`
- `ddr-buffering-and-margin-budget.md`
- `thermal-risk-review.md`
