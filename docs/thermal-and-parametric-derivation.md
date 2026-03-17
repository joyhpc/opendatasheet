# Thermal And Parametric Derivation

## Purpose

Not every domain should start with a fresh Gemini image pass. `thermal` and parts of `parametric` are most useful when they are treated as low-cost normalization or derivation layers.

## Thermal Domain

In the current pipeline, `thermal` runs after `electrical` and post-processes that result.

That design is intentional:

- thermal values such as `θJA` and `θJC` often appear near electrical tables
- many devices expose only a small thermal subset
- re-reading the PDF just for thermal numbers often adds cost without adding new signal

## Parametric Domain

`parametric` is useful for building normalized key fields that downstream tools expect:

- voltage limits
- current limits
- resistance or capacitance markers
- part-family comparison handles

This domain should prefer reuse over rediscovery. It is a good place to convert domain-shaped extraction into stable lookup-friendly forms.

## Design Principle

Ask this question before adding a new image-heavy flow:

“Is the information genuinely missing from prior domains, or is it merely not normalized yet?”

If the answer is normalization, do not add another expensive multimodal call.

## Why This Matters For Discrete Parts

Discrete parts usually need:

- core electrical values
- simple pin mapping
- thermal sanity
- normalized selection/export hints

That is exactly why the fast path keeps `thermal` and `parametric` while skipping more speculative domains.

## Review Checklist

- Does `thermal` derive cleanly from `electrical`?
- Is `parametric` adding stable, reusable fields instead of duplicating raw values?
- Could this work remain correct if Gemini is temporarily unavailable after `electrical` succeeds?
