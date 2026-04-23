# Schema v2 Domains Guide

> Practical notes for the `device-knowledge/2.0` direction and the `domains` container.

## Current compatibility state

The checked-in schema accepts:
- `sch-review-device/1.0`
- `sch-review-device/1.1`
- `device-knowledge/2.0`

That means the validator is in a compatibility phase.

For new export generation, treat `device-knowledge/2.0` as the canonical internal contract.
Keep flat `sch-review-device/1.1` fields only as a compatibility surface for downstream consumers and checked-in historical artifacts.

## What `device-knowledge/2.0` adds

It introduces a `domains` object whose keys map to self-contained sub-schemas, including:
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

## Why this direction is useful

It separates:
- source extraction concerns
- validation concerns
- downstream consumption concerns

This makes it easier to:
- extend one domain without destabilizing all others
- keep provenance close to the relevant data
- support both normal IC and FPGA modeling under one umbrella

## Practical guardrails

- Do not assume every checked-in export already uses `device-knowledge/2.0`.
- Do not delete flat-field compatibility casually.
- If a field exists in both flat and domain forms, the `domains` representation is canonical for new generation logic.
- Flat fields should be derived compatibility output, not the primary design surface for new domains.

## When to use domain language in docs or code reviews

Use domain terminology when discussing:
- architecture direction
- new extraction surfaces
- normalization boundaries

Use flat export terminology when discussing:
- current checked-in consumer contracts
- `data/sch_review_export/`
- regression behavior

## Good review questions

- Is the new fact really a new domain, or part of an existing one?
- Does the proposal improve ownership clarity?
- Can downstream users still consume the current flat contract?
