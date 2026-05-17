# Normal IC Export Field Guide

This is a quick reference for normal-IC exports under `data/sch_review_export/`.
For the full contract, read [Schematic Review Integration](sch-review-integration.md)
and the JSON schema.

## Core Fields

- `_schema`: Current public exports use `device-knowledge/2.0`.

- `_type`: Must be `normal_ic`.

- `_layers`: Compatibility layer markers such as `L0_skeleton` and `L1_electrical`.

- `mpn`: Canonical device name used for the export file.

- `manufacturer`: Vendor string when available.

- `category`: Normalized device category.

- `description`: Human-readable device description.

## Package Section

`packages` is keyed by package name.

Each package contains:

- `pin_count`
- `pins`

Each pin usually contains:

- `name`
- `direction`
- `signal_type`
- `description`
- `unused_treatment`

The same information may also appear under `domains.pin.packages`.

## Numeric Spec Sections

### `absolute_maximum_ratings`

Keyed by symbol or symbol plus condition.

Typical fields:

- `parameter`
- `symbol`
- `min`
- `max`
- `unit`
- `conditions`

### `electrical_parameters`

Keyed by symbol or symbol plus condition.

Typical fields:

- `parameter`
- `symbol`
- `min`
- `typ`
- `max`
- `unit`
- `conditions`

The v2 domain view is `domains.electrical.electrical_parameters`.

## Derived Helper Sections

### `drc_hints`

Repository-specific convenience values for downstream DRC.

Typical examples:

- `vref`
- `vin_abs_max`
- `vin_operating`
- `iout_max`
- `iq`
- `enable_threshold`

Use `drc_hints` when a consumer needs one stable shortcut.

Use `absolute_maximum_ratings` or `electrical_parameters` when provenance,
conditions, variants, or full parameter coverage matter.

### `thermal`

Normalized thermal metrics where available. Current coverage is partial.

## Optional Blocks

Some normal-IC exports may contain:

- `capability_blocks`
- `constraint_blocks`
- `domains.design_context`
- `domains.protocol`
- `domains.package`

Do not assume every optional domain is present.

## Review Questions

- Is `mpn` stable and recognizable?
- Are package names consistent with pin maps?
- Are duplicated symbols disambiguated by conditions?
- Are derived DRC hints justified by source data?
- Does the `domains` view match the flat compatibility fields?
