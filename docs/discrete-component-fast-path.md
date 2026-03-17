# Discrete Component Fast Path

## Problem

Small discrete semiconductors do not need the same extraction path as complex ICs.

A diode, TVS, or MOSFET datasheet rarely contains useful content for:

- `timing`
- `register`
- `protocol`
- `power_sequence`
- `design_guide`

Before the fast path was added, these parts could still reach heavy domains and waste Gemini calls on pages that had no relevant structure.

## Current Strategy

`pipeline_v2.py` now enables a discrete fast path in two ways:

- by inspecting the source path early, for example `.../Transistor/...`
- by inspecting the `electrical` domain result after component identity becomes available

If a file is classified as a discrete device, only a small allowlist runs:

- `electrical`
- `pin`
- `thermal`
- `parametric`

All other domains are marked as skipped with `_skipped: "discrete_component"`.

## Why Path-Based Detection Exists

Relying only on `electrical` is too late when:

- the key is invalid
- the network call hangs
- the first Gemini request fails before identity is returned

Path-based pre-enabling cuts off unnecessary heavy domains before the first expensive failure cascades.

## Detection Inputs

The current implementation uses:

- normalized component category
- component description
- MPN text
- source path keywords

Examples of matched families:

- diode
- schottky
- zener
- TVS
- ESD
- MOSFET
- JFET
- transistor

## Expected Benefits

- lower latency on discrete corpora
- lower multimodal cost
- fewer meaningless timeout surfaces
- clearer logs when a genuine extraction failure happens

## Guardrails

Do not expand the allowlist casually. Each added domain should answer:

- what concrete value it adds for discrete parts
- whether it can be derived more cheaply
- whether the domain has enough signal on typical two-page or three-page datasheets

## Regression Coverage

The repository now includes targeted tests for:

- category-based discrete detection
- description-based discrete detection
- source-path-based pre-enabling
- non-discrete negative cases
