# Release Checklist

> Lightweight release checklist for OpenDatasheet maintainers. Use this before tagging, publishing, or announcing a repository state as releasable.

## 1. Pre-release checks

Run the standard health checks first:

```bash
python3 scripts/doctor.py --dev
./scripts/run_checks.sh
```

Recommended release evidence to keep in the handoff note or PR:

```bash
python3 scripts/validate_exports.py --summary
python3 test_regression.py
python3 -m pytest -q
```

Minimum expectation for a normal release:
- environment doctor reports healthy
- checked-in exports validate successfully
- regression suite passes
- pytest entrypoint passes
- release note / PR clearly states whether generated artifacts changed

## 2. When a release requires re-export

Regenerate `data/sch_review_export/` before release if the change affects:
- `pipeline.py`
- `pipeline_v2.py`
- `scripts/export_for_sch_review.py`
- `schemas/sch-review-device.schema.json`
- checked-in extracted source data under `data/extracted_v2/`
- export normalization, field shaping, or contract semantics

Recommended sequence:

```bash
python3 scripts/export_for_sch_review.py
python3 scripts/validate_exports.py --summary
python3 test_regression.py
python3 -m pytest -q
```

If exports were regenerated, explicitly call out:
- how many generated files changed
- whether schema versions changed
- whether downstream consumers need to re-sync

## 3. When a release does not require re-export

Do **not** mass-regenerate exports for changes that are only:
- docs / metadata
- CI / templates / contributor workflow
- local tooling or repository hygiene
- support / security / ownership / maintenance documentation

In those cases, release notes should say the release is tooling-only or docs-only.

## 4. Architecture confirmation required

Pause and get explicit architecture confirmation before release if any of the following is true:
- schema compatibility with historical `1.0` artifacts is being removed
- downstream consumers need contract changes
- a release changes the conceptual model for `normal_ic` or `fpga`
- pipeline entrypoints or data layer boundaries are being restructured
- mass regeneration is required because release semantics changed, not just implementation details
- failure handling changes from degrade-gracefully to release-blocking (or the reverse)

These are no longer lightweight release tasks; they affect repository architecture and coordination.

## 5. Suggested release note contents

For a routine release, include:
- scope: source / generated data / docs / tooling
- key files or directories touched
- whether exports were regenerated
- schema state (`1.1` target, `1.0` migration compatibility if still relevant)
- commands used for validation
- any deferred follow-up items

## 6. Simple go / no-go rule

A release is normally **go** when:
- `python3 scripts/doctor.py --dev` is healthy
- `./scripts/run_checks.sh` passes
- any required regeneration was performed intentionally
- no unresolved architecture-level questions remain

A release is **no-go** when:
- validation is red
- generated data changed unintentionally
- release notes cannot explain whether exports changed
- the change crosses an architecture boundary and has not been reviewed
