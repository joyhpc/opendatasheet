# Domain Cost Control

## Purpose

The v2 pipeline is only sustainable if domains are treated as different cost classes instead of a flat list of equal work.

## Cost Classes

### Cheap

- page classification
- text-only design context extraction
- post-processing domains derived from previous results
- lightweight normalization and validation

### Medium

- pin extraction on 1 to 2 pages
- electrical extraction on a narrow page set

### Expensive

- timing
- register
- protocol
- power sequence
- package extraction from image-heavy ordering and drawing pages
- design-guide style multimodal extraction

## Cost Control Principles

- run expensive domains only when the component class justifies them
- keep selectors narrow before tuning prompts
- derive where possible instead of re-reading the PDF
- short-circuit early when input quality is invalid
- log skip reasons explicitly

## Practical Examples

### Good

- `thermal` derives from `electrical`
- discrete parts skip most heavy domains
- invalid PDF headers fail before any rendering or Gemini request

### Bad

- every domain runs for every file
- a routing fix is postponed and replaced with a larger prompt
- a bad source file is retried repeatedly without file-type validation

## Metrics Worth Watching

- average seconds per file
- per-domain timing
- count of skipped heavy domains
- count of failures caused by source corruption
- percent of files that make it past `electrical`

## Design Rule

When a new domain is proposed, document three things up front:

- expected corpus coverage
- expected page count
- why the same value cannot be produced from an earlier domain

Without those three items, the default answer should be not to add the domain to the always-on path.
