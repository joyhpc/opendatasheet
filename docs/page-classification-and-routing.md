# Page Classification And Routing

## Purpose

`pipeline_v2.py` does not send whole datasheets to Gemini. It first runs a cheap L0 pass with PyMuPDF text extraction and regex heuristics, then routes only selected pages into domain extractors.

This routing layer is the main reason the repository can handle mixed corpora without paying full multimodal cost on every page.

## What L0 Produces

Each page is classified into a coarse category such as:

- `electrical`
- `pin`
- `cover`
- `application`
- `ordering`
- `other`

These labels are not the final output schema. They are routing hints that decide:

- which extractor gets page images
- which extractor can run on raw text only
- which pages are safe to skip

## Why The Router Exists

Datasheets are noisy. A 40-page document may have only:

- 1 to 4 pages with electrical tables
- 0 to 2 pages with pin definitions
- many pages of marketing, graphs, package drawings, or layout advice

Sending all pages to Gemini would increase:

- latency
- token/image cost
- timeout surface area
- false positives from irrelevant pages

The router keeps the expensive calls narrow and makes extractor results easier to debug.

## Current Routing Pattern

- `electrical` pages feed the `electrical` domain and indirectly support `thermal`
- `pin` and selected cover content feed the `pin` domain
- `application` pages are useful to `design_context`
- heavy domains such as `timing`, `register`, `protocol`, and `power_sequence` rely on their own page selectors and should only run when the part type justifies it

## Operational Rule

If a new extractor needs many pages, fix routing before tuning prompts.

In this repository, broad page selection is usually a design smell. It often means one of these is true:

- the domain boundary is too wide
- the page classifier is too weak
- the extractor is being used on the wrong component class

## Common Failure Modes

### Misclassified electrical pages

Effect:

- empty extraction
- bad page counts
- no useful vision targets

Recovery:

- expand the relevant regex patterns
- inspect the text preview emitted by L0
- prefer narrow additions over broad keywords

### Non-electrical parts taking heavy routes

Effect:

- long Gemini calls on irrelevant pages
- timeouts on simple discrete devices

Recovery:

- use component-aware or path-aware routing gates before heavy extractors run

## Review Checklist

When changing page classification logic, verify:

- target pages are included for the intended corpus
- unrelated pages are still excluded
- dry-run logs remain readable
- extractor counts and timings move in the expected direction
