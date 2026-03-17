# Transistor Batch Postmortem 2026-03

## Summary

The `Transistor` corpus run exposed two separate issues:

1. discrete devices were reaching heavy domains that added cost without value
2. part of the raw corpus contained files that were not valid PDFs

The first issue was a pipeline design problem. The second was a source-quality problem.

## Incident Pattern

Initial symptom:

- a simple discrete part such as `BAV99` appeared to hang during Gemini Vision calls

Deeper cause:

- the pipeline allowed irrelevant domains like `timing` to run on a discrete datasheet

That expanded the number of expensive calls and increased the chance of getting stuck in an upstream network read.

## Fixes Applied

### Routing fix

- added discrete component detection from extracted identity
- added path-based pre-enabling from source path keywords such as `Transistor`
- restricted discrete-mode execution to `electrical`, `pin`, `thermal`, and `parametric`

### Source-quality fix

- added PDF header validation at pipeline entry
- removed 13 known bad `.pdf` files that were not real PDFs
- rebuilt the raw source manifest

## Batch Result

The full `Transistor` batch completed with:

- 50 files processed
- 37 successes
- 13 failures

Those 13 failures were later confirmed to be invalid raw files rather than valid PDFs with extraction defects.

## Main Lessons

- routing policy matters as much as prompt quality
- bad source files must be filtered before they look like parser bugs
- logs should separate permission failures, network hangs, and source corruption
- batch resilience is more important than forcing every file through the same domain list

## What Changed Operationally

After this cleanup, the right default stance for discrete corpora is:

- assume they need a narrow path
- justify any heavy domain explicitly
- delete invalid source files instead of repeatedly retrying them
