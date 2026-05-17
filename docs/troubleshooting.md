# OpenDatasheet Troubleshooting

Use this page for common local failures. For current architecture and counts,
read [Current State](current-state.md).

## Environment Dependencies

Typical symptoms:

- `ModuleNotFoundError`
- `ImportError`
- `python scripts/doctor.py --dev` reports a missing package

First checks:

```bash
python scripts/doctor.py --dev
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

If the failure appears only in tests, make sure dev dependencies are installed.

## Missing `GEMINI_API_KEY`

Typical symptoms:

- `pipeline.py` or `pipeline_v2.py` reports `Missing GEMINI_API_KEY environment variable`
- `python scripts/doctor.py --dev --strict-env` fails

Fix:

```bash
export GEMINI_API_KEY='<your-api-key>'
```

Then run only flows that actually need Gemini, for example:

```bash
python pipeline_v2.py <pdf-path>
```

You do not need `GEMINI_API_KEY` for:

- `python scripts/validate_exports.py --summary`
- `python scripts/export_for_sch_review.py`
- FPGA pinout parsing
- raw-source manifest checks
- reading public exports

## Export Validation Failure

Typical symptoms:

- `python scripts/validate_exports.py --summary` reports `Failed > 0`
- regression tests fail around export schema validation

Start with:

```bash
python scripts/validate_exports.py --summary
```

Then determine whether the failure is:

- one stale generated export
- a schema change without exporter updates
- an exporter change without regenerated outputs
- a semantic validation failure in an FPGA capability/constraint block

Do not hand-edit many generated export JSON files as a lasting fix. Fix the
source/intermediate data or exporter, regenerate, and validate again.

Current expected schema state:

- validator accepts `sch-review-device/1.0`, `sch-review-device/1.1`, and
  `device-knowledge/2.0`
- current checked-in public exports are `device-knowledge/2.0`

## Pytest Collection Or Plugin Failure

Typical symptoms:

- pytest fails before collecting repository tests
- stack trace mentions an unrelated plugin such as `pytest_cov`
- on Windows, stack trace mentions `_sqlite3` DLL load failure

Focused workaround:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
```

This disables external pytest plugin autoload. It is useful when the local
Python environment is broken before repository tests can run.

## Raw Source Manifest Failure

Typical symptoms:

- `scripts/build_raw_source_manifest.py --check` reports stale entries
- `./scripts/run_checks.sh` stops at raw-source manifest validation

Fix after adding, moving, or deleting canonical raw sources:

```bash
python scripts/build_raw_source_manifest.py
python scripts/build_raw_source_manifest.py --check
```

Only canonical raw files under `data/raw/` should be represented in the manifest.

## Unsure Whether To Re-Export

Usually re-export after changes to:

- `scripts/export_for_sch_review.py`
- `scripts/normal_ic_contract.py`
- export normalization helpers
- schema semantics
- checked-in extracted inputs
- FPGA pinout parser outputs

Commands:

```bash
python scripts/export_for_sch_review.py
python scripts/validate_exports.py --summary
```

Usually do not re-export for:

- docs-only changes
- CI-only changes
- support or issue-template changes
- navigation and contributor guidance

## Gemini Call Hangs

A long Gemini call is not proof that Gemini is required for that device class.

Check:

- which extractor was active
- how many pages were selected
- whether the domain is relevant to the component class
- whether a deterministic parser or derived domain would be better

Read [Gemini API Operations](gemini-api-operations.md) for more detail.

## When To Escalate

Stop treating the issue as a quick fix if you need to:

- change schema semantics
- remove old schema compatibility
- alter the meaning of `normal_ic` or `fpga`
- force downstream consumer code changes
- perform a large semantic regeneration

Read:

- [Architecture](architecture.md)
- [Maintenance](maintenance.md)
- [Release Regeneration Matrix](release-regeneration-matrix.md)
