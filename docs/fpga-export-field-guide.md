# FPGA Export Field Guide

> Quick reference for the flat FPGA export shape used by `data/sch_review_export/`.

## Core identity

- `_schema`
- `_type`
  Must be `fpga`
- `mpn`
- `package`

Many exports also carry richer identity under:
- `device_identity`

Useful identity components include:
- vendor
- family
- series
- base device
- concrete device
- package

## Primary physical sections

### `pins`

Flat list of physical pins with fields such as:
- `pin`
- `name`
- `function`
- `bank`
- `drc`

Common `function` values:
- `IO`
- `POWER`
- `GROUND`
- `CONFIG`
- `GT`
- `GT_POWER`
- `SPECIAL`
- `NC`

### `banks`

Per-bank grouping and electrical metadata used for bank-aware review.

### `diff_pairs`

Concrete P/N pair definitions for:
- general IO diff pairs
- transceiver RX/TX pairs
- refclk pairs

### `lookup`

Fast reverse maps such as:
- `pin_to_name`
- `name_to_pin`

## Electrical and policy sections

### `supply_specs`

Power-rail facts when extracted or normalized.

### `drc_rules`

Repository-level rule templates or review expectations for FPGA integration.

### `capability_blocks`

High-value capability summaries, for example:
- `mipi_phy`
- `high_speed_serial`
- `hard_processor`

### `constraint_blocks`

Review-critical implementation constraints, for example:
- `refclk_requirements`
- debug or interface-specific constraints

## Why these extra blocks matter

A pin map alone is not enough for FPGA review. Downstream tooling often needs:
- refclk ownership
- lane-group compatibility
- bank-level voltage constraints
- whether a device actually exposes a capability in this package or ordering variant

## Consumer advice

Use `lookup` for fast pin resolution.

Use `banks` and `diff_pairs` for electrical and routing checks.

Use `capability_blocks` and `constraint_blocks` when the review question is architectural rather than pin-by-pin.

## Review questions

- Are high-speed capabilities present only when source-backed?
- Are refclk details concrete rather than implied?
- Does package-specific reality override family-level marketing assumptions?
