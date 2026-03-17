# Decoupling Placement Review

> Review rules for whether decoupling is merely present or actually useful.

## The real question

Do not ask only “is there a capacitor.”

Ask:
- is it on the right rail
- is it close enough to the pins that matter
- does return current have a clean path
- does the capacitor mix reflect frequency spread

## High-value review checks

- FPGA core rails have local high-frequency decoupling near pin clusters
- GT or SerDes rails are not sharing a lazy generic strategy
- analog rails avoid noisy placement compromises
- bulk capacitance is placed where it supports the load step, not just where it fits

## Warning signs

- one generic capacitor value copied everywhere
- rail pin clusters far from the local cap cluster
- via farms that look neat but create long current loops
- decoupling present on schematic but placement impossible in layout

## What to capture before handoff

- rail-specific capacitor families
- must-place notes for sensitive rails
- rails that require local stitching or return-path care

## Official practice baseline

Use `hardware-best-practice-source-basis.md` for TI, ADI, and AMD PDN guidance.
