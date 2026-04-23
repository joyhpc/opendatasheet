# OpenDatasheet Maintenance Guide

> Maintainer-oriented checklist for validating repository health, deciding when to regenerate outputs, and handling the current schema migration safely.

## 1. Local checks

Run these in order when touching pipeline logic, export logic, schema, tests, or checked-in generated data.

### Fast environment check

```bash
python3 scripts/doctor.py --dev
```

Verifies:
- Python version
- required runtime/dev dependencies
- key repository paths
- `GEMINI_API_KEY` presence (warning-only unless strict mode is used)

### Full local gate

```bash
./scripts/run_checks.sh
```

Runs:
- Python syntax compilation
- export/schema validation
- regression suite
- pytest entrypoint

### Individual checks

```bash
python3 scripts/validate_exports.py --summary
python3 test_regression.py
python3 -m pytest -q
```

Use these when iterating on a narrower area.

## 2. Export validation

The canonical export validation command is:

```bash
python3 scripts/validate_exports.py --summary
```

Expected healthy state today:
- all checked-in exports validate successfully
- validator accepts `sch-review-device/1.0`, `sch-review-device/1.1`, and `device-knowledge/2.0`
- newly generated exports should target `device-knowledge/2.0`
- flat `1.1` fields remain as compatibility output inside generated exports when needed

If validation fails:
1. identify whether the break is in generation logic, schema rules, or a one-off checked-in artifact
2. prefer fixing generation logic over hand-editing exported JSON
3. rerun validation before touching regression tests

## 3. When to re-export data

Re-export `data/sch_review_export/` when changes affect any of the following:
- `pipeline.py`
- `pipeline_v2.py`
- `scripts/export_for_sch_review.py`
- `schemas/sch-review-device.schema.json`
- raw extracted inputs under `data/extracted_v2/`
- normalization or field-shaping rules for export consumers

Typical re-export command:

```bash
python3 scripts/export_for_sch_review.py
python3 scripts/validate_exports.py --summary
python3 test_regression.py
```

`scripts/export_for_sch_review.py` now treats `data/sch_review_export/` as a managed output set:
- files produced from current `data/extracted_v2/` inputs are rewritten
- stale top-level device JSONs that are no longer generated are removed automatically
- `_manifest.json` and `_fpga_catalog.json` are regenerated after cleanup

Do **not** re-export just because docs, CI, templates, or support files changed.

## 4. When not to re-export

Avoid mass regeneration when:
- the change is documentation-only
- the change is CI/tooling-only
- the change affects contributor workflow but not export semantics
- the repository is in a migration window and the current checked-in artifacts already validate cleanly

This keeps diff size small and avoids unnecessary churn in generated artifacts.

## 5. Schema migration policy

Current state:
- checked-in schema document accepts `sch-review-device/1.0`, `sch-review-device/1.1`, and `device-knowledge/2.0`
- validator remains compatible with historical `1.0` and `1.1` artifacts during migration
- export generation should emit `device-knowledge/2.0`
- checked-in device exports should now converge on `device-knowledge/2.0`; legacy `1.0`/`1.1` support exists only for validation/backward compatibility

Maintainer rule of thumb:
- **new output** → emit `device-knowledge/2.0`
- **flat top-level fields** → keep them only for compatibility with current consumers
- **historical checked-in output** → do not preserve it by accident; stale device files should disappear on regeneration
- **manual compatibility notes** → must remain schema-compatible

Before ending migration, confirm all of the following:
1. all checked-in exports have been intentionally regenerated or reviewed
2. downstream consumers no longer rely on `1.0`-only assumptions
3. validator compatibility can be tightened without breaking repository health

## 6. Collaboration guardrails

When multiple contributors or agents are working in parallel:
- avoid hand-editing generated exports unless absolutely necessary
- do not revert unrelated in-flight changes
- keep non-architectural changes focused and easy to review
- mention whether a change touched source, generated data, or docs/tooling only
- include exact validation commands in handoff notes

For issue routing:
- support / usage questions → `SUPPORT.md`
- security-sensitive reports → `SECURITY.md`
- contribution workflow → `CONTRIBUTING.md`

## 7. Recommended maintenance sequence

For routine repository upkeep, use this order:

```bash
python3 scripts/doctor.py --dev
./scripts/run_checks.sh
```

For export-contract changes, use this order:

```bash
python3 scripts/export_for_sch_review.py
python3 scripts/validate_exports.py --summary
python3 test_regression.py
python3 -m pytest -q
```

## 8. Escalation cues

Pause and discuss before making a larger change if any of the following become true:
- a change requires mass regeneration of checked-in exports
- schema compatibility with `1.0` needs to be removed
- downstream consumers need contract changes
- pipeline entrypoints or data model layers need restructuring
- a fix changes how normal IC and FPGA exports are conceptually modeled

Those are no longer “lightweight engineering” changes; they affect repository architecture and release coordination.
