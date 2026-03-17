# Power Entry Protection Review

> What to review at the board’s power entry before downstream rails even matter.

## Entry path checklist

- input voltage range matches the actual product envelope
- reverse battery or reverse polarity behavior is explicit
- hot-plug or inrush limit strategy exists
- fuse or eFuse reset behavior is known
- TVS choice matches surge energy and standoff voltage
- ideal diode or OR-ing assumptions are validated

## Common mistakes

- selecting a TVS by headline wattage only
- using an eFuse without checking startup into downstream bulk caps
- forgetting cable inductance and hot-plug overshoot
- assuming a bench supply represents vehicle or field behavior

## When this matters most

- automotive or industrial power entry
- boards with large bulk capacitance
- boards with expensive FPGA/SoC downstream loads

## What this repo can help with

OpenDatasheet exports can quickly surface:
- absolute max voltage
- UVLO-like hints
- device category for hot-swap/eFuse/reverse protection parts

Use them to shorten review, not replace full entry-path analysis.

## Official practice baseline

Use `hardware-best-practice-source-basis.md` for TI and ADI protection and ESD references.
