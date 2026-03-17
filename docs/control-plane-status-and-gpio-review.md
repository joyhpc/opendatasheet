# Control Plane Status And GPIO Review

> Review checklist for interrupts, status lines, enables, and other low-speed control-plane signals that quietly decide whether the board is debuggable.

## Review points

- signal direction is explicit
- default state during reset and partial power is explicit
- pull-up or pull-down ownership is explicit
- voltage domain is compatible with both ends
- status signal is actually observable in the lab

## Common mistakes

- interrupt pin treated as generic GPIO
- active-low status not documented and later misread in firmware
- enables chained without a clear owner
- slow control signals routed through unnecessary translators

## Good policy

- list all control-plane signals in one table
- include polarity
- include default state
- include observability path
