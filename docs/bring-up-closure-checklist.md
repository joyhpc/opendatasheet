# Bring-Up Closure Checklist

> Checklist for deciding whether a board is ready for first article power-on and debug.

## Minimum closure items

- rail names, targets, and measurement points are frozen
- clock sources and expected waveforms are documented
- reset release sequence is documented
- assembly options are documented
- debug entry path is available
- known-high-risk links have a loopback or observation plan

## For FPGA-heavy boards

- package-specific pinout facts are frozen
- VCCO and bank planning are frozen
- refclk ownership is frozen
- configuration boot path is testable

## For camera/display/high-speed platforms

- ingress path can be validated independently
- egress path can be validated independently
- local buffering assumptions are written down

## Closure is not

- “the schematic looks complete”
- “firmware can sort it out”
- “layout will probably make room”

Closure means the board has a credible first-debug path.
