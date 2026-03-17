# Test Strategy And Regression

## Goal

This repository needs tests that protect architecture decisions, not just individual helper functions.

## Current Test Layers

### Unit-style validation tests

These cover local invariants inside domains such as:

- package validation
- protocol field rules
- register parsing rules
- power-sequence consistency

### Pipeline behavior tests

These check routing and policy decisions, for example:

- discrete fast-path detection
- downstream discrete export support

### Corpus or export regression tests

These protect:

- schema stability
- baseline extraction quality
- export structure for downstream consumers

## What Good Regression Looks Like

- a failing test points to one policy boundary
- tests encode why a routing rule exists
- domain validators are exercised without needing a live Gemini call
- downstream export expectations are covered where normalization matters

## What To Add When Fixing A Bug

When a real incident happens, prefer adding:

- one test for the trigger condition
- one test for the expected policy behavior

For the discrete routing work, that meant:

- discrete detection by category
- discrete detection by description
- discrete detection by source path
- invalid PDF header rejection
- export support for TVS and MOSFET-like outputs

## Review Rule

If a change affects routing, corpus hygiene, or export semantics and no new regression exists, the fix is probably under-specified.
