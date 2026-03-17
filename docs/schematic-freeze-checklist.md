# Schematic Freeze Checklist

> Final review list before declaring a board ready for layout or release.

## Freeze only when these are true

- every power rail has owner, load list, tolerance, and measurement plan
- every clock has a named source, consumers, and startup assumption
- every reset has source, polarity, pull strategy, and release condition
- every high-speed link has refclk owner, lane map, and bring-up loop
- every FPGA bank has a voltage plan, not just pin usage
- every `NC` and stuffing option has an explicit policy
- every debug path has at least one realistic entry point

## High-risk omissions

- DDR budgeted by capacity but not by burst absorption margin
- MIPI or SerDes reviewed by lane count only
- FPGA package chosen from family summary rather than package facts
- MCU pins overloaded with timing-sensitive responsibilities
- test points omitted because “firmware can tell us”

## What to pull from this repo

- normal IC limits from `data/sch_review_export/{MPN}.json`
- FPGA banks, pairs, and lookup from `data/sch_review_export/{Device}_{Package}.json`
- architecture context from `docs/a57-class-fpga-architecture-notes.md`

## Freeze package

Before freeze, keep these artifacts together:
- schematic revision
- rail table
- clock tree table
- reset tree table
- FPGA bank ownership table
- bring-up checklist
- assembly-option table
