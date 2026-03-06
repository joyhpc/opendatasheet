import json
from pathlib import Path

import fitz

from scripts.organize_datasheet_pdfs import run


def _make_pdf(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def test_organize_datasheet_pdfs_dedupes_by_mpn(tmp_path):
    raw_dir = tmp_path / "raw"
    extracted_dir = tmp_path / "extracted"
    raw_dir.mkdir()
    extracted_dir.mkdir()

    canonical_pdf = raw_dir / "0130-00-00040_LP5907SNX.pdf"
    duplicate_pdf = raw_dir / "nested" / "0130-00-00063_LP5907SNX.pdf"
    _make_pdf(canonical_pdf, "LP5907 datasheet")
    _make_pdf(duplicate_pdf, "LP5907 datasheet duplicate")

    extracted_a = {
        "pdf_name": canonical_pdf.name,
        "extraction": {"component": {"mpn": "LP5907"}},
    }
    extracted_b = {
        "pdf_name": duplicate_pdf.name,
        "extraction": {"component": {"mpn": "LP5907"}},
    }
    (extracted_dir / "a.json").write_text(json.dumps(extracted_a), encoding="utf-8")
    (extracted_dir / "b.json").write_text(json.dumps(extracted_b), encoding="utf-8")

    payload, index_path = run(raw_dir, extracted_dir, apply=True)

    assert index_path.exists()
    assert payload["summary"]["groups_with_duplicates"] == 1
    assert (raw_dir / "0130-00-00040_LP5907SNX.pdf").exists()
    assert (raw_dir / "_duplicates" / "LP5907" / "0130-00-00063_LP5907SNX.pdf").exists()
