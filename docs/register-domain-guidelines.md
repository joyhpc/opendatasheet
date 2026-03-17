# Register Domain Guidelines

## Role

The `register` domain extracts memory-mapped configuration structures:

- register addresses
- access modes
- reset values
- bit fields

It is a high-value domain for configurable ICs and a zero-value domain for non-programmable discrete parts.

## When To Enable It

Run `register` when the source clearly contains:

- register maps
- address tables
- named bit fields
- reset defaults

Do not enable it just because a device is “digital”.

## Why It Is Easy To Misuse

Register pages are dense, repetitive, and expensive. A weak selector can:

- send many irrelevant pages
- produce malformed hex fields
- confuse protocol tables with register tables

## Validation Priorities

- valid hex formatting
- non-overlapping bit ranges
- unique addresses
- access-mode normalization
- field width consistency

## Operational Rule

If register extraction is failing on a corpus that should not have registers, the problem is not the prompt. The problem is routing.
