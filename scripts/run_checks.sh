#!/usr/bin/env bash
set -euo pipefail

python3 -m py_compile \
  pipeline.py \
  pipeline_v2.py \
  scripts/build_raw_source_manifest.py \
  scripts/export_for_sch_review.py \
  scripts/validate_design_extraction.py \
  scripts/validate_exports.py \
  test_regression.py \
  test_pin_extraction.py \
  test_drc_hints_v2.py \
  test_raw_source_manifest.py \
  test_validate_design_extraction_manifest.py \
  extractors/__init__.py \
  extractors/base.py \
  extractors/register.py \
  extractors/timing.py \
  extractors/power_sequence.py

echo "=== Extractor Registry Check ==="
python3 -c "from extractors import EXTRACTOR_REGISTRY; assert len(EXTRACTOR_REGISTRY) >= 7, 'Expected at least 7 extractors'; print(f'  {len(EXTRACTOR_REGISTRY)} extractors registered')"

if ! python3 scripts/build_raw_source_manifest.py --check; then
  echo "raw-source manifest is missing or stale; run: python3 scripts/build_raw_source_manifest.py" >&2
  exit 1
fi

python3 scripts/check_markdown_links.py
python3 scripts/validate_exports.py --summary
python3 scripts/validate_design_extraction.py --strict
python3 test_regression.py
python3 -m pytest -q
