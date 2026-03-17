# MCU FPGA Boundary Patterns

> How to keep MCU and FPGA responsibilities separated so the board remains routable and debuggable.

## Good partition

- MCU owns lifecycle control, updates, health reporting, and operator entry points
- FPGA owns protocol adaptation, timing absorption, lane remap, and board-facing pin complexity

## Warning signs

- MCU is asked to directly absorb irregular high-speed timing
- FPGA is reduced to passive glue while MCU pin pressure explodes
- control plane and data plane are intertwined on the same fragile boundary

## Design rule

Prefer a simple, explicit MCU-FPGA boundary over a feature-rich but timing-fragile one.

## Official practice baseline

Use `hardware-best-practice-source-basis.md` together with package-specific FPGA exports and actual MCU datasheets.
