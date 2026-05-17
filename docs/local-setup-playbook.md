# Local Setup Playbook

> Practical setup steps for running validation, extraction, and export commands locally.
> Read [`current-state.md`](current-state.md) first if you need audited counts, current schema target, or extraction provenance.

## Prerequisites

- Python `>= 3.11`
- `pip`
- network access if you plan to run model-backed extraction against external APIs

## Install runtime dependencies

```bash
pip install -r requirements.txt
```

Needed for normal repo work:
- `PyMuPDF` via `fitz`
- `httpx`
- `google-genai`
- `jsonschema`
- `openpyxl`

## Install dev dependencies

```bash
pip install -r requirements-dev.txt
```

This is needed for:
- `pytest`
- full local validation

## Set extraction credentials when needed

```bash
export GEMINI_API_KEY='<your-api-key>'
```

Notes:
- `scripts/doctor.py --strict-env` will fail if the variable is missing.
- Docs-only, schema-only, export validation, deterministic FPGA parsing, and many inspection workflows do not need the key.
- The current repository should not be summarized as a pure Gemini pipeline; see [`extraction-methodology.md`](extraction-methodology.md).

## Run the environment doctor

```bash
python3 scripts/doctor.py --dev
```

Healthy output should show:
- Python version passes
- dependencies import cleanly
- core repo paths exist
- `GEMINI_API_KEY` status is visible

## Run the normal local gate

```bash
./scripts/run_checks.sh
```

This runs:
- syntax compilation
- extractor registry sanity check
- raw source manifest freshness check
- markdown link validation
- export validation
- design extraction validation
- regression suite
- `pytest`

## Fast minimum commands

If you do not want the full gate:

```bash
python3 scripts/validate_exports.py --summary
python3 scripts/validate_design_extraction.py --strict
python3 test_regression.py
python3 -m pytest -q
```

## Common setup failures

### `python: command not found`

Use `python3`, not `python`.

### `ModuleNotFoundError: No module named 'fitz'`

Install runtime dependencies:

```bash
pip install -r requirements.txt
```

### `pip install openpyxl`

That message comes from `scripts/parse_gowin_pinout.py`. Install runtime dependencies or install `openpyxl` directly.

### `GEMINI_API_KEY missing`

Only blocking if:
- you run Gemini-backed extraction commands
- or you explicitly choose `--strict-env`

### Pytest fails while importing `_sqlite3`

This can come from local pytest plugins rather than repository code. Use:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q
```

## Recommended first checks after setup

```bash
python3 scripts/doctor.py --dev
python3 scripts/check_markdown_links.py docs
python3 scripts/validate_exports.py --summary
```
