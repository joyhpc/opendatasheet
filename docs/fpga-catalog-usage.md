# FPGA Catalog Usage

> How to use the repository-wide FPGA catalog and what it is good for.

## Generator

Use:

```bash
python3 scripts/build_fpga_catalog.py
```

Default output:
- `data/sch_review_export/_fpga_catalog.json`

## What the catalog is

It is a navigation tree built from FPGA exports in `data/sch_review_export/`.

It summarizes:
- vendors
- families
- series
- base devices
- concrete devices
- packages

It also records quick package flags such as:
- device role
- HPS presence
- SerDes presence

## What the catalog is good for

- coverage review
- browsing what FPGA exports already exist
- checking whether a package is already represented
- building higher-level navigation tools

## What it is not

It is not a substitute for the per-device export JSON.

Use the catalog to discover candidate files, then open the actual export for detailed review.

## Good workflow

After adding or regenerating FPGA exports:

```bash
python3 scripts/build_fpga_catalog.py
python3 scripts/validate_exports.py --summary
```

## Typical review questions

- did a new parser add the expected package nodes
- did a package disappear unexpectedly
- did device-role or capability flags drift after export changes
