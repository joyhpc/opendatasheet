"""
Test Pin Extraction L1b — 5 representative PDFs
Sirius 🌟 | 2026-02-22
"""
import json
import time
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from pipeline_v2 import (
    classify_pages, render_pages_to_images,
    DATA_DIR, GEMINI_MODEL, OUTPUT_DIR, get_gemini_client
)
from extractors.pin import PinExtractor, validate_pins

TEST_PDFS = [
    ("0130-00-00003_RT9193.pdf", "RT9193 — 多封装 (SC-70-5, SOT-23-5, WDFN-6L, MSOP-8)"),
    ("0130-00-00022_LT1964ES5-SD#TRPBF.pdf", "LT1964 — 多变体"),
    ("0130-06-00004_ADG706BRU.pdf", "ADG706 — 高 pin 数 (48 pins)"),
    ("0130-00-00014_AMS1117.pdf", "AMS1117 — 之前 pin 提取失败"),
    ("0130-06-00017_SW-FUSB340TMX.pdf.PDF", "FUSB340 — USB switch"),
]


def run_one(pdf_filename: str, label: str):
    pdf_path = str(DATA_DIR / pdf_filename)
    if not os.path.exists(pdf_path):
        print(f"  ❌ File not found: {pdf_path}")
        return None

    # Classify pages
    pages = classify_pages(pdf_path)
    extractor = PinExtractor(
        client=get_gemini_client(),
        model=GEMINI_MODEL,
        pdf_path=pdf_path,
        page_classification=pages,
        is_fpga=False,
    )
    pin_page_nums = extractor.select_pages()

    if not pin_page_nums:
        print(f"  ⚠️ No pin/cover pages found, skipping")
        return None

    print(f"  Pages for pin extraction: {pin_page_nums}")

    # Render and extract
    images = render_pages_to_images(pdf_path, pin_page_nums)
    t0 = time.time()
    result = extractor.extract(images)
    elapsed = time.time() - t0

    if "error" in result:
        print(f"  ❌ Extraction failed ({elapsed:.1f}s): {result['error']}")
        return result

    logical_pins = result.get("logical_pins", [])
    print(f"  ✅ Extracted {len(logical_pins)} logical pins ({elapsed:.1f}s)")

    # Direction distribution
    dir_dist = {}
    for p in logical_pins:
        d = p.get("direction", "?")
        dir_dist[d] = dir_dist.get(d, 0) + 1
    print(f"  Direction: {dir_dist}")

    # Signal type distribution
    sig_dist = {}
    for p in logical_pins:
        s = p.get("signal_type", "?")
        sig_dist[s] = sig_dist.get(s, 0) + 1
    print(f"  Signal type: {sig_dist}")

    # Packages
    all_pkgs = set()
    for p in logical_pins:
        pkgs = p.get("packages", {})
        if isinstance(pkgs, dict):
            all_pkgs.update(pkgs.keys())
    print(f"  Packages: {sorted(all_pkgs)}")

    # Validate
    issues = validate_pins(result)
    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]
    print(f"  Validation: {len(errors)} errors, {len(warnings)} warnings")
    for issue in issues:
        icon = "❌" if issue["level"] == "error" else "⚠️"
        print(f"    {icon} {issue['message']}")

    return result


def update_extracted_file(pdf_filename: str, pin_result: dict):
    """Update the extracted_v2 JSON file with pin_extraction data"""
    stem = pdf_filename.replace(".PDF", "").replace(".pdf", "")
    # Handle the double-extension case
    json_name = stem + ".json"
    json_path = OUTPUT_DIR / json_name
    if not json_path.exists():
        print(f"  ⚠️ No existing extraction file: {json_path}")
        return
    with open(json_path, 'r') as f:
        data = json.load(f)
    data["pin_extraction"] = pin_result
    data["pin_validation"] = validate_pins(pin_result) if "error" not in pin_result else []
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  📝 Updated {json_path.name}")


if __name__ == "__main__":
    print("=" * 60)
    print("Pin Extraction L1b — Test Suite")
    print("=" * 60)

    results = {}
    for pdf_filename, label in TEST_PDFS:
        print(f"\n{'─'*50}")
        print(f"📋 {label}")
        print(f"   {pdf_filename}")
        print(f"{'─'*50}")
        result = run_one(pdf_filename, label)
        results[pdf_filename] = result
        if result and "error" not in result:
            update_extracted_file(pdf_filename, result)
        time.sleep(3)  # Rate limit

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for pdf_filename, label in TEST_PDFS:
        r = results.get(pdf_filename)
        if r is None:
            status = "SKIPPED"
            count = 0
        elif "error" in r:
            status = "FAILED"
            count = 0
        else:
            pins = r.get("logical_pins", [])
            issues = validate_pins(r)
            errs = len([i for i in issues if i["level"] == "error"])
            status = "OK" if errs == 0 else f"{errs} ERRORS"
            count = len(pins)
        short = label.split("—")[0].strip()
        print(f"  {short:12s}: {count:3d} pins — {status}")
