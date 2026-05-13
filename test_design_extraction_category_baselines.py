import json
from pathlib import Path

import pytest

from scripts.export_design_bundle import _index_extracted_records
from scripts.validate_design_extraction import (
    CATEGORY_BASELINE_EXPECTATIONS,
    has_full_pdf_corpus,
    load_exports,
    summarize_by_category,
    summarize_corpus,
    validate_category_baselines,
)

REPO_ROOT = Path(__file__).resolve().parent


def test_category_baselines_pass_current_corpus():
    if not has_full_pdf_corpus(REPO_ROOT / "data/raw/datasheet_PDF"):
        pytest.skip("full datasheet PDF corpus is not available")

    devices = load_exports(REPO_ROOT / "data/sch_review_export")
    extracted_index = _index_extracted_records(REPO_ROOT / "data/extracted_v2")
    counts, contexts = summarize_corpus(devices, extracted_index, REPO_ROOT / "data/raw/datasheet_PDF")
    category_counts = summarize_by_category(devices, contexts)

    assert "Buck" in category_counts
    assert "LDO" in category_counts
    assert category_counts["Buck"]["with_design_pages"] >= CATEGORY_BASELINE_EXPECTATIONS["Buck"]["design_pages_min"]
    assert not validate_category_baselines(category_counts)
