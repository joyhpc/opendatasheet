# Changelog

All notable changes to this repository are documented here.

## Unreleased

### Added
- Added `requirements.txt` and `requirements-dev.txt` for explicit runtime and dev dependencies.
- Added `scripts/run_checks.sh` as a one-shot local validation gate.
- Added GitHub CI workflow in `.github/workflows/ci.yml`.
- Added `CONTRIBUTING.md` for contributor onboarding and repository safety guidelines.
- Added GitHub collaboration templates: PR template, issue config, bug report, and feature request.
- Added `.editorconfig` and centralized pytest config in `pyproject.toml`.
- Added `scripts/bootstrap.sh` for local environment bootstrap.

### Changed
- Removed hardcoded Gemini API key fallback; extraction now requires `GEMINI_API_KEY`.
- Unified export generation to `sch-review-device/1.1` while keeping validation compatibility with historical `1.0` artifacts.
- Updated README, GUIDE, and integration docs to match the current schema/version and repository workflow.
- Refined test entrypoints so `pytest` only collects the standardized regression entrypoint.

### Fixed
- Restored schema validation for all checked-in exports (`194/194` valid locally).
- Restored regression health (`52/52` passing locally).
