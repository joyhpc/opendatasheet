# Power Sequence Domain Guidelines

## Role

The `power_sequence` domain models rail ordering, enable dependencies, UVLO or OTP thresholds, and startup or shutdown requirements.

## Best-Fit Devices

- PMICs
- hot-swap or sequencing controllers
- devices with explicit multi-rail startup rules
- complex ICs with power-good and enable dependencies

## Poor-Fit Devices

- two-terminal protection parts
- simple discretes
- components with no startup sequencing semantics beyond absolute maximum ratings

## Why This Domain Is Expensive

Power sequencing details are often scattered across:

- feature pages
- application notes
- startup waveforms
- truth-table-like bullet lists

That means a broad page search can quickly become costly and ambiguous.

## Validation Focus

- missing sequence order gaps
- contradictory rules
- category validity
- threshold sanity

## Operational Rule

Do not infer that every power-related device needs `power_sequence`. A regulator or switch may have rich electrical data but still not justify a structured sequencing domain.
