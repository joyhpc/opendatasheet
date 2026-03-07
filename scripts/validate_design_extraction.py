#!/usr/bin/env python3
"""Validate PDF-aware design extraction on a curated corpus and coverage baseline."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.build_raw_source_manifest import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_RAW_MANIFEST,
    build_manifest,
)
from scripts.export_design_bundle import (  # noqa: E402
    _index_extracted_records,
    _load_datasheet_design_context,
    build_design_intent,
    build_quickstart_markdown,
)

DEFAULT_EXPORT_DIR = REPO_ROOT / "data/sch_review_export"
DEFAULT_EXTRACTED_DIR = REPO_ROOT / "data/extracted_v2"
DEFAULT_PDF_DIR = REPO_ROOT / "data/raw/datasheet_PDF"

CURATED_EXPECTATIONS = {
    "TPS62147": {
        "min_design_pages": 2,
        "min_layout": 1,
        "required_roles": {"inductor", "feedback_divider"},
    },
    "LP5907": {
        "min_design_pages": 2,
        "min_layout": 1,
        "required_roles": {"input_capacitor", "output_capacitor"},
    },
    "ADM7155": {
        "min_design_pages": 2,
        "min_layout": 1,
        "min_equations": 1,
        "required_roles": {"output_capacitor"},
    },
    "AD8571/AD8572/AD8574": {
        "min_design_pages": 1,
        "min_layout": 1,
        "min_equations": 1,
    },
    "ADG706/ADG707": {
        "min_design_pages": 1,
    },
}

BASELINE_EXPECTATIONS = {
    "pdf_text_min": 100,
    "design_pages_min": 110,
    "components_min": 80,
    "layout_min": 85,
    "equations_min": 40,
}

CATEGORY_BASELINE_EXPECTATIONS = {
    "Buck": {
        "pdf_text_min": 35,
        "design_pages_min": 35,
        "components_min": 35,
        "layout_min": 33,
        "equations_min": 18,
    },
    "LDO": {
        "pdf_text_min": 35,
        "design_pages_min": 35,
        "components_min": 30,
        "layout_min": 25,
        "equations_min": 20,
    },
    "Switch": {
        "design_pages_min": 6,
        "layout_min": 2,
        "equations_min": 1,
    },
    "OpAmp": {
        "design_pages_min": 1,
        "layout_min": 1,
        "equations_min": 1,
    },
    "Interface": {
        "design_pages_min": 2,
        "components_min": 1,
        "layout_min": 1,
    },
    "DAC": {
        "design_pages_min": 1,
        "components_min": 1,
    },
}


def load_exports(export_dir: Path) -> dict[str, dict]:
    devices = {}
    for path in sorted(export_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        mpn = payload.get("mpn")
        if mpn:
            devices[mpn] = payload
    return devices


def summarize_corpus(devices: dict[str, dict], extracted_index: dict[str, Path], pdf_dir: Path) -> tuple[Counter, dict[str, dict]]:
    counts: Counter = Counter()
    contexts = {}
    for mpn, device in devices.items():
        ctx = _load_datasheet_design_context(device, extracted_index, pdf_dir)
        contexts[mpn] = ctx
        mode = ctx.get("source_mode", "unavailable")
        counts[mode] += 1
        if ctx.get("design_page_candidates"):
            counts["with_design_pages"] += 1
        if ctx.get("recommended_external_components"):
            counts["with_components"] += 1
        if ctx.get("layout_hints"):
            counts["with_layout"] += 1
        if ctx.get("design_equation_hints"):
            counts["with_equations"] += 1
    return counts, contexts


def summarize_by_category(devices: dict[str, dict], contexts: dict[str, dict]) -> dict[str, Counter]:
    category_counts: dict[str, Counter] = defaultdict(Counter)
    for mpn, device in devices.items():
        category = device.get("category") or "Unknown"
        ctx = contexts.get(mpn, {})
        counts = category_counts[category]
        counts["total"] += 1
        counts[ctx.get("source_mode", "unavailable")] += 1
        if ctx.get("design_page_candidates"):
            counts["with_design_pages"] += 1
        if ctx.get("recommended_external_components"):
            counts["with_components"] += 1
        if ctx.get("layout_hints"):
            counts["with_layout"] += 1
        if ctx.get("design_equation_hints"):
            counts["with_equations"] += 1
    return dict(category_counts)


def validate_curated(devices: dict[str, dict], contexts: dict[str, dict]) -> list[str]:
    failures = []
    for mpn, expectation in CURATED_EXPECTATIONS.items():
        device = devices.get(mpn)
        ctx = contexts.get(mpn)
        if not device or not ctx:
            failures.append(f"missing device: {mpn}")
            continue
        design_intent = build_design_intent(device, datasheet_design_context=ctx)
        quickstart = build_quickstart_markdown(device, design_intent)
        roles = {item.get("role") for item in design_intent.get("external_components", [])}

        if len(ctx.get("design_page_candidates", [])) < expectation.get("min_design_pages", 0):
            failures.append(f"{mpn}: design pages {len(ctx.get('design_page_candidates', []))} < {expectation['min_design_pages']}")
        if len(ctx.get("layout_hints", [])) < expectation.get("min_layout", 0):
            failures.append(f"{mpn}: layout hints {len(ctx.get('layout_hints', []))} < {expectation['min_layout']}")
        if len(ctx.get("design_equation_hints", [])) < expectation.get("min_equations", 0):
            failures.append(f"{mpn}: equations {len(ctx.get('design_equation_hints', []))} < {expectation['min_equations']}")
        missing_roles = expectation.get("required_roles", set()) - roles
        if missing_roles:
            failures.append(f"{mpn}: missing roles {sorted(missing_roles)}")
        if ctx.get("design_page_candidates") and "Datasheet design pages" not in quickstart:
            failures.append(f"{mpn}: quickstart missing design page section")
    return failures


def validate_baseline(counts: Counter) -> list[str]:
    failures = []
    if counts["pdf_text"] < BASELINE_EXPECTATIONS["pdf_text_min"]:
        failures.append(f"pdf_text count too low: {counts['pdf_text']}")
    if counts["with_design_pages"] < BASELINE_EXPECTATIONS["design_pages_min"]:
        failures.append(f"design page coverage too low: {counts['with_design_pages']}")
    if counts["with_components"] < BASELINE_EXPECTATIONS["components_min"]:
        failures.append(f"component coverage too low: {counts['with_components']}")
    if counts["with_layout"] < BASELINE_EXPECTATIONS["layout_min"]:
        failures.append(f"layout coverage too low: {counts['with_layout']}")
    if counts["with_equations"] < BASELINE_EXPECTATIONS["equations_min"]:
        failures.append(f"equation coverage too low: {counts['with_equations']}")
    return failures


def validate_category_baselines(category_counts: dict[str, Counter]) -> list[str]:
    failures = []
    metric_map = {
        "pdf_text_min": "pdf_text",
        "design_pages_min": "with_design_pages",
        "components_min": "with_components",
        "layout_min": "with_layout",
        "equations_min": "with_equations",
    }
    for category, expectation in CATEGORY_BASELINE_EXPECTATIONS.items():
        counts = category_counts.get(category, Counter())
        for metric_name, threshold in expectation.items():
            counter_key = metric_map[metric_name]
            actual = counts[counter_key]
            if actual < threshold:
                failures.append(f"{category}: {counter_key} {actual} < {threshold}")
    return failures


def validate_raw_source_manifest(raw_root: Path, strict: bool = False, manifest_path: Path | None = None) -> list[str]:
    failures: list[str] = []
    manifest_path = manifest_path or (raw_root / DEFAULT_RAW_MANIFEST.name)

    if not manifest_path.exists():
        return [f"raw manifest missing: {manifest_path}"]

    try:
        current_text = manifest_path.read_text(encoding="utf-8")
        current = json.loads(current_text)
    except Exception as exc:
        return [f"raw manifest unreadable: {manifest_path} ({exc})"]

    if current.get("entry_count", 0) <= 0:
        failures.append(f"raw manifest empty: {manifest_path}")

    entries = current.get("entries") or []
    if not isinstance(entries, list):
        failures.append(f"raw manifest malformed entries: {manifest_path}")
        return failures

    if not any((item.get("storage_tier") == "canonical") for item in entries if isinstance(item, dict)):
        failures.append(f"raw manifest has no canonical entries: {manifest_path}")

    if strict:
        rendered = json.dumps(build_manifest(raw_root), indent=2, ensure_ascii=False) + "\n"
        if current_text != rendered:
            failures.append(f"raw manifest stale: {manifest_path}")

    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--extracted-dir", type=Path, default=DEFAULT_EXTRACTED_DIR)
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    devices = load_exports(args.export_dir)
    extracted_index = _index_extracted_records(args.extracted_dir)
    counts, contexts = summarize_corpus(devices, extracted_index, args.pdf_dir)
    category_counts = summarize_by_category(devices, contexts)
    raw_root = args.pdf_dir.parent if args.pdf_dir.name == "datasheet_PDF" else args.pdf_dir
    failures = (
        validate_raw_source_manifest(raw_root, strict=args.strict)
        + validate_curated(devices, contexts)
        + validate_baseline(counts)
        + validate_category_baselines(category_counts)
    )

    print("counts", dict(counts))
    print("category_counts", {key: dict(value) for key, value in sorted(category_counts.items()) if key in CATEGORY_BASELINE_EXPECTATIONS})
    if failures:
        print("failures")
        for item in failures:
            print("-", item)
        return 1 if args.strict else 0
    print("validation=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
