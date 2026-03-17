# Discrete Export Normalization

## Purpose

Getting discrete parts through extraction is not enough. They must also normalize into downstream export shapes that schematic review and selection-profile tooling can use.

## Current Support Surface

The repository already contains regression coverage showing that downstream exporters can normalize:

- TVS-like parts from generic or `Other` categories
- MOSFET-like parts from description-driven identity

This is important because raw vendor categorization is often inconsistent.

## Why Normalization Is Necessary

A device may arrive with:

- category `Other`
- a description such as `TVS diode for transient voltage suppression`
- parameters like `VRWM`, `VC`, or `RDS(ON)` that clearly identify its real class

If downstream export logic preserves the weak original label, selection and DRC tooling lose useful semantics.

## What Downstream Tools Need

### For TVS / ESD parts

- reverse or standoff voltage
- clamp voltage
- pulse power or surge capability
- simple passive pin model

### For MOSFET-like parts

- drain-source voltage
- drain current
- on-resistance
- simple package-aware pin semantics

## Design Rule

Export normalization should be conservative but not naive:

- use explicit electrical evidence and description text
- avoid overfitting to one vendor naming style
- preserve enough original traceability that the normalized category is explainable

## Why This Connects To Fast Path

The discrete fast path only pays off if the kept domains still provide enough information for export normalization. The current test coverage confirms that this is true for at least TVS and MOSFET-like examples.
