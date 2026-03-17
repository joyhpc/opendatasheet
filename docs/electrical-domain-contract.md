# Electrical Domain Contract

## Role

The `electrical` domain is the primary semantic anchor for most non-FPGA devices. It does more than extract parameters. It usually establishes the first trustworthy component identity.

## Expected Outputs

Typical fields include:

- `component`
- `absolute_maximum_ratings`
- `electrical_characteristics`
- sometimes lightweight pin hints found on cover or summary pages

## Why This Domain Comes First

Many later decisions depend on `electrical`:

- category normalization
- discrete-component detection
- thermal derivation
- export hints such as voltage or clamp parameters

If `electrical` is weak, the whole file usually becomes weak.

## Page Selection Rules

The selector should prefer:

- electrical characteristics tables
- absolute maximum ratings
- recommended operating conditions
- cover-page identity if it helps resolve the family or vendor

It should not drift into:

- application notes
- package drawings unless identity is missing
- long ordering appendices with no electrical data

## Validation Focus

Electrical validation should catch:

- suspicious units
- impossible or inverted min/typ/max ranges
- parameters that conflict with obvious physical rules

It does not need to solve every downstream schema concern. Its job is to produce a reliable, domain-shaped result that other layers can build on.

## Discrete-Part Importance

For discrete corpora, `electrical` is often the only truly essential multimodal domain. That is why the discrete fast path preserves it even when many other domains are skipped.

## Review Questions

- Does the domain identify the part class correctly?
- Are core electrical tables actually selected?
- Are validation warnings specific enough to explain trust level?
- If the result is empty, is the selector wrong or is the source document poor?
