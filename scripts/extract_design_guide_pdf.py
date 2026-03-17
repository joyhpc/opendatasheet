#!/usr/bin/env python3
"""Extract a standalone design-guide PDF into machine-readable design_guide JSON.

This is a thin harness over the existing DesignGuideExtractor so family guide
PDFs can enter the normal opendatasheet extraction chain without bespoke
one-off helpers. It works in two modes:

1. Vision + text, when Gemini credentials are available.
2. Text-only fallback, when Gemini is unavailable or the call fails.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from extractors.design_guide import DesignGuideExtractor
from pipeline_v2 import GEMINI_MODEL, classify_pages, get_gemini_client, render_pages_to_images


def extract_design_guide_pdf(pdf_path: Path) -> dict:
    pages = classify_pages(str(pdf_path), is_fpga=True)
    try:
        client = get_gemini_client()
    except Exception:
        client = None

    extractor = DesignGuideExtractor(
        client=client,
        model=GEMINI_MODEL,
        pdf_path=str(pdf_path),
        page_classification=pages,
        is_fpga=True,
    )
    selected_pages = extractor.select_pages()
    images = render_pages_to_images(str(pdf_path), selected_pages) if selected_pages else []
    result = extractor.extract(images)
    validation = extractor.validate(result)

    return {
        "source_pdf": str(pdf_path),
        "selected_pages": selected_pages,
        "domains": {
            "design_guide": result,
        },
        "domain_validations": {
            "design_guide": validation,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Path to the design-guide PDF")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output JSON path, e.g. data/extracted_v2/fpga/gowin_gw5ar_design_guide.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = extract_design_guide_pdf(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
