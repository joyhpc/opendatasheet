# Unused Pin And NC Policy

> How to treat `NC`, reserved pins, optional straps, and stuffing placeholders without leaving hidden risk.

## Categories to separate

- vendor-declared `NC`
- reserved pins with mandatory tie requirements
- optional feature pins
- do-not-stuff population options
- “leave open for now” placeholders

## Review rules

- never treat reserved pins as generic `NC`
- every no-stuff resistor or zero-ohm option should have a stated future purpose
- every optional clock or reset path should be tied to a bring-up plan

## Common failure modes

- `NC` used as a mental bucket for unknowns
- reserved ground pins left floating
- stuffing options added with no test intent
- alternate boot or refclk position impossible to rework after assembly

## Bring-up implication

If an option exists, document:
- default stuffing
- alternate stuffing
- reason the alternate exists
- how to tell which state the board is in
