#!/usr/bin/env python3
"""Generate a markdown validation report and sample quickstarts for design extraction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.export_design_bundle import (  # noqa: E402
    _index_extracted_records,
    build_design_intent,
    build_quickstart_markdown,
)
from scripts.validate_design_extraction import (  # noqa: E402
    BASELINE_EXPECTATIONS,
    CATEGORY_BASELINE_EXPECTATIONS,
    load_exports,
    summarize_by_category,
    summarize_corpus,
)

DEFAULT_EXPORT_DIR = REPO_ROOT / "data/sch_review_export"
DEFAULT_EXTRACTED_DIR = REPO_ROOT / "data/extracted_v2"
DEFAULT_PDF_DIR = REPO_ROOT / "data/raw/datasheet_PDF"
DEFAULT_REPORT_PATH = REPO_ROOT / "docs/design-extraction-validation.md"
DEFAULT_SAMPLES_DIR = REPO_ROOT / "docs/design-extraction-samples"
SAMPLE_MPNS = [
    "TPS62147",
    "LP5907",
    "ADM7155",
    "AD8571/AD8572/AD8574",
    "ADG706/ADG707",
]


def _sample_slug(mpn: str) -> str:
    return mpn.replace("/", "_").replace(" ", "_")


def generate_report(export_dir: Path, extracted_dir: Path, pdf_dir: Path, report_path: Path, samples_dir: Path) -> None:
    devices = load_exports(export_dir)
    extracted_index = _index_extracted_records(extracted_dir)
    counts, contexts = summarize_corpus(devices, extracted_index, pdf_dir)
    category_counts = summarize_by_category(devices, contexts)

    samples_dir.mkdir(parents=True, exist_ok=True)
    sample_rows = []
    for mpn in SAMPLE_MPNS:
        device = devices[mpn]
        context = contexts[mpn]
        design_intent = build_design_intent(device, datasheet_design_context=context)
        quickstart = build_quickstart_markdown(device, design_intent)
        slug = _sample_slug(mpn)
        sample_path = samples_dir / f"{slug}.md"
        sample_path.write_text(quickstart, encoding="utf-8")
        try:
            sample_doc = sample_path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            sample_doc = sample_path.as_posix()
        sample_rows.append(
            {
                "mpn": mpn,
                "category": device.get("category"),
                "source_mode": context.get("source_mode"),
                "design_pages": len(context.get("design_page_candidates", [])),
                "components": len(context.get("recommended_external_components", [])),
                "layout": len(context.get("layout_hints", [])),
                "equations": len(context.get("design_equation_hints", [])),
                "sample_doc": sample_doc,
            }
        )

    lines = [
        "# Design Extraction Validation",
        "",
        "Generated from the current PDF-aware design-extraction flow.",
        "",
        "## Corpus Baseline",
        "",
        f"- `pdf_text`: {counts['pdf_text']} (threshold `{BASELINE_EXPECTATIONS['pdf_text_min']}`)",
        f"- `with_design_pages`: {counts['with_design_pages']} (threshold `{BASELINE_EXPECTATIONS['design_pages_min']}`)",
        f"- `with_components`: {counts['with_components']} (threshold `{BASELINE_EXPECTATIONS['components_min']}`)",
        f"- `with_layout`: {counts['with_layout']} (threshold `{BASELINE_EXPECTATIONS['layout_min']}`)",
        f"- `with_equations`: {counts['with_equations']} (threshold `{BASELINE_EXPECTATIONS['equations_min']}`)",
        "",
        "## Category Baselines",
        "",
        "| Category | Total | pdf_text | Design Pages | Components | Layout | Equations | Thresholds |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for category in sorted(CATEGORY_BASELINE_EXPECTATIONS):
        counts_for_category = category_counts.get(category, {})
        thresholds = ", ".join(
            f"{key.replace('_min','')}≥{value}" for key, value in CATEGORY_BASELINE_EXPECTATIONS[category].items()
        )
        lines.append(
            f"| {category} | {counts_for_category.get('total', 0)} | {counts_for_category.get('pdf_text', 0)} | {counts_for_category.get('with_design_pages', 0)} | {counts_for_category.get('with_components', 0)} | {counts_for_category.get('with_layout', 0)} | {counts_for_category.get('with_equations', 0)} | {thresholds} |"
        )

    lines.extend([
        "",
        "## Sample Devices",
        "",
        "| MPN | Category | Source | Pages | Components | Layout | Equations | Quickstart |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ])
    for row in sample_rows:
        lines.append(
            f"| {row['mpn']} | {row['category']} | {row['source_mode']} | {row['design_pages']} | {row['components']} | {row['layout']} | {row['equations']} | `{row['sample_doc']}` |"
        )

    lines.extend([
        "",
        "## Notes",
        "",
        "- This is still a text-first extraction flow; it does not yet parse schematic figures as structured netlists.",
        "- Coverage is strongest on regulators and power devices, then layout-heavy analog devices.",
        "- Larger architecture changes such as a new OCR/Vision design-extraction stage should be discussed before implementation.",
        "",
    ])
    report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--extracted-dir", type=Path, default=DEFAULT_EXTRACTED_DIR)
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--samples-dir", type=Path, default=DEFAULT_SAMPLES_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generate_report(args.export_dir, args.extracted_dir, args.pdf_dir, args.report_path, args.samples_dir)
    print(f"report={args.report_path}")
    print(f"samples={args.samples_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
