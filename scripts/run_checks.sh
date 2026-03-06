#!/usr/bin/env bash
set -euo pipefail

python3 -m py_compile \
  pipeline.py \
  pipeline_v2.py \
  scripts/export_for_sch_review.py \
  scripts/validate_exports.py \
  test_regression.py \
  test_pin_extraction.py \
  test_drc_hints_v2.py

python3 scripts/check_markdown_links.py
python3 scripts/validate_exports.py --summary
python3 test_regression.py
python3 -m pytest -q
