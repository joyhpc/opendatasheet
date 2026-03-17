# Design Domain Guidelines

## Scope

This repository has more than one “design-related” domain. They should not be merged casually.

## `design_context`

Purpose:

- cheap extraction of design hints from application and layout text
- topology clues
- external component mentions
- layout recommendations

Characteristics:

- text-oriented
- broad but shallow
- good for schematic-start assistance

## `design_guide`

Purpose:

- richer structured guidance for sequencing, constraints, or design rules
- closer to a reusable design checklist

Characteristics:

- more domain-specific
- more expensive
- should run only when the source clearly contains design-guide quality material

## Relationship Between The Two

Use `design_context` for discovery and `design_guide` for structured rules. If both are always enabled together on every corpus, the boundary is probably wrong.

## Why The Separation Matters

Application pages are common. High-value design-guide pages are not.

If the pipeline treats all design prose as equal:

- costs rise
- prompts become unfocused
- noisy hints dilute actionable rules

## Operational Rule

Prefer `design_context` as the default, and enable `design_guide` only when:

- the device class justifies it
- the page classifier finds real design material
- downstream users need structured constraints, not just hints
