# JTAG And SWD Debug Header Review

> How to review debug access so it still works after the first bring-up failure.

## Debug header checklist

- connector standard or pinout is documented
- ground reference is present and not token-only
- target voltage reference is provided where tools expect it
- reset access exists when useful
- pull resistors on JTAG/SWD lines are intentional

## Practical mistakes

- header exists but is blocked by assembly options
- target voltage reference omitted
- debug pins reused by default boot straps without review
- series resistors or muxes make the path fragile

## For FPGA boards

Also ask:
- is configuration mode selection compatible with JTAG recovery
- are config pins and JTAG assumptions fighting each other
- can the board be recovered if flash boot is broken

## Minimal bring-up goal

A dead board should still allow:
- power verification
- clock verification
- debug attach or at least boundary access

## Official practice baseline

Use `hardware-best-practice-source-basis.md` and keep debug access aligned with the actual device boot and recovery strategy.
