# Contributing

## Quick Start

1. Install runtime dependencies:
   - `pip install -r requirements.txt`
2. Install dev/test dependencies:
   - `pip install -r requirements-dev.txt`
3. Set Gemini credentials before running extraction flows:
   - `export GEMINI_API_KEY='<your-api-key>'`
4. Run the environment doctor:
   - `python3 scripts/doctor.py --dev`
5. Run the local gate before opening a PR:
   - `./scripts/run_checks.sh`

## Development Workflow

- Use `python3 pipeline_v2.py <pdf-path>` for a single PDF.
- Use `python3 pipeline_v2.py <limit>` for batch mode.
- Use `python3 scripts/export_for_sch_review.py` to regenerate sch-review exports.
- Use `python3 scripts/validate_exports.py --summary` to confirm export/schema health.
- Use `python3 test_regression.py` for the repository regression suite.
- Use `python3 -m pytest -q` for the pytest-compatible entrypoint.
- Use `python3 scripts/doctor.py --dev` to validate local tooling and key paths.

## Agent Context Hygiene

- Treat `docs/` as a routed knowledge base, not a bulk context source.
- Start with `README.md`, `GUIDE.md`, `docs/index.md`, or `docs/hardware-engineer-index.md`.
- Open only the smallest set of docs needed for the task.
- For coding, validation, or export changes, prefer reading the actual script, schema, or test before opening more docs.
- Do not recursively scan `docs/hardware-engineering/` unless the task is explicitly a hardware review writing task.

## Generated Data Policy

- Treat `data/sch_review_export/*.json` as generated artifacts.
- Prefer fixing generation logic instead of hand-editing exported JSON.
- If a checked-in artifact needs a one-off compatibility note, keep it schema-compatible.
- During the schema migration window, both `sch-review-device/1.0` and `sch-review-device/1.1` are accepted by validation.

## Pull Request Expectations

- Keep changes focused and minimal.
- Mention whether you changed source code, generated exports, or both.
- Include the command(s) you ran locally.
- Call out any intentionally deferred issues or follow-up cleanup.

## Safety Notes

- Never reintroduce hardcoded API keys.
- Avoid tests that mutate checked-in data by default.
- Prefer failing fast over silently emitting partial/ambiguous outputs.

## Security Reporting

- Do not open public issues for secrets exposure or exploitable vulnerabilities.
- Prefer private reporting as described in `SECURITY.md`.
- For non-code help and triage, see `SUPPORT.md`.
- For repository upkeep and regeneration workflow, see `docs/maintenance.md`.
