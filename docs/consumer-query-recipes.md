# Consumer Query Recipes

> Short recipes for downstream tools reading `data/sch_review_export/`.

## 1. Load a normal IC by MPN

Use the file:
- `data/sch_review_export/{MPN}.json`

Typical use:
- retrieve pin names
- retrieve `drc_hints`
- inspect absolute maximum ratings

## 2. Load an FPGA by device and package

Use the file:
- `data/sch_review_export/{Device}_{Package}.json`

Typical use:
- map physical pin to signal name
- inspect bank compatibility
- verify differential pair completeness

## 3. Fast pin lookup

Prefer:
- `lookup.pin_to_name`
- `lookup.name_to_pin`

These are cheaper than repeatedly scanning the full `pins` list.

## 4. Voltage-limit check for a normal IC

Prefer:
- `drc_hints.vin_abs_max` when available

Fallback to:
- `absolute_maximum_ratings`

Use the fallback when:
- you need conditions
- there are multiple supply rails
- you need source-level nuance

## 5. FPGA bank-aware checks

Use:
- `banks`
- `pins`

Good examples:
- VCCO compatibility
- bank occupancy review
- package-level routing feasibility

## 6. Diff pair integrity

Use:
- `diff_pairs`

Typical check:
- if one side of a pair is connected, the complement should also be reviewed

## 7. Capability-aware review

Use:
- `capability_blocks`
- `constraint_blocks`

This is especially important for:
- MIPI
- refclk
- transceiver use
- MCU debug/boot/clock behavior

## 8. Good consumer policy

- treat filenames as discovery helpers, not the only identity source
- use structured fields for logic
- treat package-specific FPGA data as authoritative over family assumptions
