from __future__ import annotations

from pathlib import Path

import fitz

from design_info_utils import detect_design_page_kind, extract_design_context


DEFAULT_DATASHEET_PDF_DIR = Path(__file__).resolve().parent.parent / "data/raw/datasheet_PDF"
DCDC_CATEGORIES = {"Buck", "Boost", "Buck-Boost", "SEPIC", "Flyback", "PMIC"}


def should_auto_extract_design_context(category: str | None) -> bool:
    return category in DCDC_CATEGORIES


def _build_design_text_pages_from_pdf(extracted_record: dict, pdf_dir: Path) -> list[dict]:
    pdf_name = extracted_record.get("pdf_name")
    if not pdf_name:
        return []

    pdf_path = pdf_dir / pdf_name
    if not pdf_path.exists():
        return []

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return []

    text_pages = []
    page_classification = extracted_record.get("page_classification", [])
    if page_classification:
        for page in page_classification:
            page_num = page.get("page_num")
            if page_num is None or page_num >= len(doc):
                continue
            text = doc[page_num].get_text("text", sort=True)
            kind = detect_design_page_kind(text) or detect_design_page_kind(page.get("text_preview", ""))
            if kind:
                text_pages.append({"page_num": page_num, "kind": kind, "text": text})
    else:
        for page_num in range(len(doc)):
            text = doc[page_num].get_text("text", sort=True)
            kind = detect_design_page_kind(text)
            if kind:
                text_pages.append({"page_num": page_num, "kind": kind, "text": text})
    doc.close()
    return text_pages


def _build_design_text_pages_from_preview(extracted_record: dict) -> list[dict]:
    text_pages = []
    for page in extracted_record.get("page_classification", []):
        preview = page.get("text_preview", "")
        kind = detect_design_page_kind(preview)
        if not kind:
            continue
        text_pages.append({"page_num": page.get("page_num"), "kind": kind, "text": preview})
    return text_pages


def load_design_context_for_export_record(extracted_record: dict, pdf_dir: Path = DEFAULT_DATASHEET_PDF_DIR) -> dict:
    text_pages = _build_design_text_pages_from_pdf(extracted_record, pdf_dir)
    if text_pages:
        design_context = extract_design_context(text_pages)
        design_context["source_mode"] = "pdf_text"
        design_context["pdf_name"] = extracted_record.get("pdf_name")
        return design_context

    preview_pages = _build_design_text_pages_from_preview(extracted_record)
    if preview_pages:
        design_context = extract_design_context(preview_pages)
        design_context["source_mode"] = "preview_only"
        design_context["pdf_name"] = extracted_record.get("pdf_name")
        return design_context

    return {}
