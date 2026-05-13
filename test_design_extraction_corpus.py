import json
from pathlib import Path

import pytest

from scripts.export_design_bundle import (
    _index_extracted_records,
    _load_datasheet_design_context,
    build_design_intent,
    build_quickstart_markdown,
)
from scripts.validate_design_extraction import has_full_pdf_corpus

REPO_ROOT = Path(__file__).resolve().parent
EXPORT_DIR = REPO_ROOT / "data/sch_review_export"
EXTRACTED_DIR = REPO_ROOT / "data/extracted_v2"
PDF_DIR = REPO_ROOT / "data/raw/datasheet_PDF"
SAMPLES = {
    "TPS62147": {"roles": {"inductor", "feedback_divider"}, "layout_min": 1},
    "LP5907": {"roles": {"input_capacitor", "output_capacitor"}, "layout_min": 1},
    "ADM7155": {"roles": {"output_capacitor"}, "layout_min": 1, "equations_min": 1},
    "AD8571/AD8572/AD8574": {"layout_min": 1, "equations_min": 1},
}


def _load_devices():
    devices = {}
    for path in EXPORT_DIR.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("mpn"):
            devices[payload["mpn"]] = payload
    return devices


def test_design_extraction_curated_closed_loop():
    if not has_full_pdf_corpus(PDF_DIR):
        pytest.skip("full datasheet PDF corpus is not available")

    devices = _load_devices()
    extracted_index = _index_extracted_records(EXTRACTED_DIR)

    for mpn, expectation in SAMPLES.items():
        device = devices[mpn]
        context = _load_datasheet_design_context(device, extracted_index, PDF_DIR)
        design_intent = build_design_intent(device, datasheet_design_context=context)
        quickstart = build_quickstart_markdown(device, design_intent)
        roles = {item.get("role") for item in design_intent.get("external_components", [])}

        assert context.get("design_page_candidates"), mpn
        assert len(context.get("layout_hints", [])) >= expectation.get("layout_min", 0), mpn
        assert len(context.get("design_equation_hints", [])) >= expectation.get("equations_min", 0), mpn
        assert expectation.get("roles", set()).issubset(roles), mpn
        assert "Datasheet design pages" in quickstart, mpn
