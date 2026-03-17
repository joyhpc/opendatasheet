# Assembly Options And Stuffing Strategy

> How to review DNP parts, zero-ohm options, and alternate populations as an engineering tool rather than schematic clutter.

## Good assembly options

- provide a real bring-up branch
- provide a real recovery path
- provide a real feature-selection path

## Bad assembly options

- exist only because the designer was unsure
- have no default population note
- cannot be reworked safely after assembly

## Review questions

- what problem does this option solve
- what is the default stuffing
- what is the alternate stuffing
- how will the lab identify current population state

## Tie-in with other docs

Use this together with:
- `unused-pin-and-nc-policy.md`
- `bring-up-closure-checklist.md`
