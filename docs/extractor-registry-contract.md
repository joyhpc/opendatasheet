# Extractor Registry Contract

## Purpose

`extractors/__init__.py` defines `EXTRACTOR_REGISTRY`, and `pipeline_v2.py` executes extractors in that order. The registry is not just discovery metadata. It is execution policy.

## Required Extractor Interface

Every extractor inherits `BaseExtractor` and must implement:

- `DOMAIN_NAME`
- `select_pages()`
- `extract(...)`
- `validate(...)`

This contract keeps the pipeline loop simple:

1. build extractor instance
2. ask it which pages matter
3. render only those pages if needed
4. run extraction
5. run validation
6. store domain result and timing

## Why Order Matters

Some domains depend on earlier outputs.

Current examples:

- `thermal` post-processes the `electrical` result instead of reading standalone page images
- fast-path decisions for discrete components are enabled after `electrical` returns a component identity

That means registry order is part of behavior, not just style.

## What A Good Extractor Should Do

- own one domain with a clear schema boundary
- select a small, explainable page set
- return structured data or a structured error
- validate domain-specific invariants locally
- avoid leaking downstream export concerns into extraction logic

## What A Good Extractor Should Not Do

- infer unrelated domains
- assume whole-document access when only a few pages matter
- depend on registry neighbors unless the dependency is explicit and stable
- mix extraction and export normalization into one opaque step

## Adding A New Extractor

Use this sequence:

1. define the domain boundary
2. add or reuse a schema
3. implement page selection
4. implement extraction and validation
5. add focused tests for selectors, validation, and schema shape
6. place the extractor in the registry only after dependency order is clear

## Questions To Answer Before Registry Insertion

- Is the domain cheap or expensive?
- Does it require page images?
- Can it derive from prior domain outputs?
- Should it run for every component type?
- What happens when the domain is skipped?

If those answers are vague, the extractor is not ready.
