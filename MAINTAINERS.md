# Maintainers

Lightweight maintainer guide for OpenDatasheet. This file defines ownership boundaries, what can move forward without architecture review, and what should be escalated before merging or release coordination.

## Maintainer Role Boundary

Maintainers are expected to:
- keep repository health green
- preserve export/schema compatibility expectations
- review whether a change affects source logic, generated data, or docs/tooling only
- require explicit validation evidence for changes that touch pipeline, export, schema, or checked-in artifacts
- stop and escalate changes that cross architecture or downstream contract boundaries

Maintainers are **not** expected to silently approve:
- schema contract changes without downstream review
- mass regeneration without a clear reason and validation trail
- data model restructuring presented as “tooling only”
- security-sensitive disclosures through public review threads

## Lightweight Changes Maintainers Can Usually Approve Directly

These typically do **not** need architecture discussion if validation stays green:
- docs, navigation, contributor guidance, and support/security routing
- CI, templates, local scripts, and repository hygiene
- test harness cleanup that does not change contract semantics
- dependency manifest / bootstrap improvements
- validation/reporting improvements that do not change schema meaning
- release/process/maintenance documentation

Rule of thumb:
- if exports do not need regeneration
- if downstream consumers do not need to change behavior
- if the normal IC / FPGA conceptual model is unchanged
- and if `./scripts/run_checks.sh` remains green

then the change is usually lightweight.

## Changes That Must Be Escalated To Architecture Discussion

Pause and escalate before merge if a change affects any of the following:
- `schemas/sch-review-device.schema.json` semantics, not just wording
- compatibility removal for historical `sch-review-device/1.0` artifacts
- field meaning, normalization rules, or contract shape used by downstream consumers
- conceptual modeling for `normal_ic` or `fpga`
- pipeline/data-layer boundaries, entrypoint expectations, or failure-handling policy
- mass regeneration caused by contract changes instead of routine regeneration
- changes that require consumer coordination, release blocking behavior, or migration planning

Rule of thumb:
- if the answer to “will consumers or generated data meaning change?” is yes,
- treat it as architecture-level until proven otherwise.

## Expected Handoff Information

When handing off work, include:
- summary of what changed
- whether the change touched source, generated data, or docs/tooling only
- exact validation commands run
- whether exports were regenerated
- whether schema versioning or migration compatibility was affected
- any deferred cleanup or follow-up risk
- whether architecture discussion is still needed

Preferred validation evidence for non-trivial changes:
- `python3 scripts/doctor.py --dev`
- `./scripts/run_checks.sh`
- `python3 scripts/validate_exports.py --summary`
- `python3 test_regression.py`
- `python3 -m pytest -q`

## Collaboration Guardrails

When multiple people or agents are working in parallel:
- do not revert unrelated in-flight edits
- prefer touching the smallest possible file set
- prefer fixing generators over hand-editing generated artifacts
- make it explicit when a change is safe to merge independently
- if uncertain whether a change is architectural, escalate early instead of normalizing risk in review comments

## Maintainer Go / No-Go Shortcut

A change is usually **go** when:
- scope is clearly lightweight
- validation is green
- no hidden contract change exists
- handoff notes clearly describe blast radius

A change is **no-go / escalate** when:
- schema meaning changes
- downstream expectations change
- mass regeneration is required for semantic reasons
- release notes cannot explain the impact cleanly
