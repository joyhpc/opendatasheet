# Package Domain Guidelines

## Role

The `package` domain extracts mechanical and ordering-package information that is useful for downstream physical design and packaging review, but it is not universally required for every corpus.

## Typical Value

Package extraction is most useful when a datasheet contains:

- multiple package options
- package dimensions
- exposed-pad information
- pitch, reflow, MSL, and thermal-package properties

This information is important for complete IC integration and layout review.

## Why It Is Often Expensive

Package information commonly lives on:

- dense drawing pages
- ordering tables
- package outline appendices

These pages are visually noisy and often large. They are a poor fit for an always-on domain on simple discrete corpora.

## Enablement Guidance

Run `package` when:

- the device is a complex IC with multiple package options
- package choice materially affects downstream design
- the corpus genuinely contains readable package drawings

Skip or defer `package` when:

- the device has one obvious tiny package and downstream value is low
- the source is a short discrete datasheet
- cost and reliability matter more than mechanical completeness

## Validation Focus

Package validation should catch:

- impossible dimensions
- broken pitch ranges
- inconsistent pin counts
- duplicate package names
- contradictory summary fields

## Design Rule

If a downstream consumer only needs pin numbering and logical names, use the `pin` domain first. Do not use `package` as a backdoor replacement for missing pin modeling.
