# Timing Domain Guidelines

## Role

The `timing` domain is for setup, hold, propagation delay, switching windows, and other temporal constraints that matter for logic and interface behavior.

## When Timing Is Valuable

- digital ICs with explicit timing tables
- interface devices with setup/hold constraints
- FPGA- or bus-adjacent parts with clocked behavior

## When Timing Is Mostly Noise

- simple diodes
- TVS parts
- ESD protectors
- most two-terminal or three-terminal discrete semiconductors

Running `timing` on those parts increases cost without producing a meaningful output.

## Selector Expectations

Timing selectors should look for:

- AC characteristics
- propagation delay tables
- setup/hold terminology
- switching characteristics

They should not rely on vague mentions of “response time” alone unless the domain truly models that family.

## Operational Lesson

The Transistor corpus issue reinforced a simple rule:

If a domain is irrelevant for a whole component class, skip it at routing time. Do not let the extractor discover that fact expensively.

## Validation Focus

- monotonic min/typ/max behavior
- unit sanity
- consistent naming for setup vs hold vs propagation
- no mixing of timing terms with unrelated analog delay prose
