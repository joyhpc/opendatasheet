# Schema v2 Domains Guide

Last audited from code and checked-in data: 2026-05-17.

`device-knowledge/2.0` is the current public export target. All checked-in files
under `data/sch_review_export/`, excluding manifest/catalog sidecars, currently
use this schema version.

## Compatibility State

The checked-in schema accepts:

- `sch-review-device/1.0`
- `sch-review-device/1.1`
- `device-knowledge/2.0`

That compatibility exists so validators and readers can handle historical
payloads. New public exports should be generated as `device-knowledge/2.0`.

## What v2 Adds

v2 keeps flat compatibility fields and adds a `domains` object. The schema
currently allows these domain keys:

- `pin`
- `electrical`
- `thermal`
- `design_context`
- `register`
- `timing`
- `power_sequence`
- `design_guide`
- `parametric`
- `protocol`
- `package`

The presence of a domain key in the schema does not mean the current corpus has
non-empty data for that domain. See [Current State](current-state.md) for
coverage.

## Canonical Read Rule

For new tooling:

1. Prefer `domains.<name>` when it exists and is non-empty.
2. Fall back to flat fields for compatibility.
3. Do not write alternate export shapes outside `scripts/export_for_sch_review.py`.

For normal ICs, `scripts/normal_ic_contract.py` builds the domain block and flat
compatibility fields together.

For FPGAs, `scripts/export_for_sch_review.py` builds top-level FPGA fields and a
`domains.pin` view from normalized package pinout data.

## Current Domain Meaning

| Domain | Intended ownership | Current public coverage |
|--------|--------------------|-------------------------|
| `pin` | normal-IC packages or FPGA physical pin/bank/pair lookup | broad |
| `electrical` | absolute maximum ratings, electrical params, DRC hints | broad for normal ICs |
| `thermal` | thermal-derived parameters | partial |
| `design_context` | application/layout/component hints from datasheet context | partial |
| `design_guide` | vendor guide overlays and hardware design rules | mostly Gowin FPGA |
| `power_sequence` | sequencing rules and rail-order constraints | mostly Gowin FPGA |
| `protocol` | bus/interface/protocol capability facts | limited, SerDes-focused |
| `package` | package/mechanical facts beyond pin records | minimal |
| `register` | register maps and bitfields | no current public coverage |
| `timing` | setup/hold/propagation/switching constraints | no current public coverage |
| `parametric` | comparison-oriented normalized specs | no current public coverage |

## Schema Change Rules

When changing schema:

- update the relevant `schemas/domains/*.schema.json` file when a domain changes
- update `schemas/sch-review-device.schema.json` if top-level contract changes
- update exporter code before committing regenerated data
- run `python scripts/validate_exports.py --summary`
- add or update focused tests when behavior changes

## Common Pitfalls

- Do not assume flat fields are obsolete. They are still compatibility output.
- Do not assume every domain extractor populates public exports.
- Do not infer provenance from schema alone. Provenance belongs in source data,
  audit sidecars, or explicit profile metadata.
- Do not hand-edit public exports as a lasting fix. Regenerate them from
  checked-in source/intermediate data.
