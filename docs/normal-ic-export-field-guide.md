# Normal IC Export Field Guide

> Quick reference for the flat normal-IC export shape used by `data/sch_review_export/`.

## Core fields

- `_schema`
  Schema version such as `sch-review-device/1.1`
- `_type`
  Must be `normal_ic`
- `mpn`
  Canonical device name used for the export file
- `manufacturer`
  Vendor string when available
- `category`
  Normalized device category
- `description`
  Human-readable device description

## Package section

`packages` is keyed by package name.

Each package contains:
- `pin_count`
- `pins`

Each pin typically contains:
- `name`
- `direction`
- `signal_type`
- `description`
- `unused_treatment`

## Numeric spec sections

### `absolute_maximum_ratings`

Keyed by symbol or symbol-plus-condition.

Typical fields:
- `parameter`
- `min`
- `max`
- `unit`
- `conditions`

### `electrical_parameters`

Keyed by symbol or symbol-plus-condition.

Typical fields:
- `parameter`
- `min`
- `typ`
- `max`
- `unit`
- `conditions`

## Derived helper sections

### `drc_hints`

Repository-specific convenience values for downstream DRC.

Typical examples:
- `vref`
- `vin_abs_max`
- other design-rule-oriented shortcuts

### `thermal`

Normalized thermal metrics where available.

## Additional normalized blocks

Some exports may also contain:
- `capability_blocks`
- `constraint_blocks`

These are increasingly important for devices with meaningful interface or system-behavior semantics.

## Consumer advice

Use `drc_hints` when a consumer needs one stable shortcut.

Use `absolute_maximum_ratings` or `electrical_parameters` when:
- full provenance matters
- you need conditions
- you need to reason about multiple variants of the same symbol

## Review questions

- Is the `mpn` stable and recognizable?
- Are package names consistent with pin maps?
- Are duplicated symbols disambiguated by conditions when needed?
- Are derived hints still justified by source data?
