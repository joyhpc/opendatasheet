#!/usr/bin/env python3
"""Extract TI hot-swap / ideal diode IC datasheets using pipeline_v2."""

import json
import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pipeline_v2 import process_single_pdf, OUTPUT_DIR

PDF_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "pdfs", "ti")

# TPS2490 and TPS2491 share the same datasheet
PDFS = [
    "lm5060_ds.pdf",
    "lm5069_ds.pdf",
    "lm74610q1_ds.pdf",
    "tps2490_ds.pdf",
    "tps2596_ds.pdf",
    "lm5064_ds.pdf",
]

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    errors = []

    for i, pdf_name in enumerate(PDFS):
        pdf_path = os.path.join(PDF_DIR, pdf_name)
        out_name = pdf_name.replace(".pdf", ".json")
        out_path = OUTPUT_DIR / out_name

        if out_path.exists() and out_path.stat().st_size > 100:
            print(f"\n⏭ Skipping (already done): {pdf_name}")
            results.append(pdf_name)
            continue

        print(f"\n[{i+1}/{len(PDFS)}] Processing {pdf_name}...")
        try:
            result = process_single_pdf(pdf_path)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            ext = result.get("extraction", {})
            if "error" in ext:
                print(f"  ⚠️ Extraction had error: {ext['error']}")
                errors.append((pdf_name, ext["error"]))
            else:
                amr = len(ext.get("absolute_maximum_ratings", []))
                ec = len(ext.get("electrical_characteristics", []))
                pins = len(result.get("pin_extraction", {}).get("logical_pins", []))
                print(f"  ✓ {amr} abs_max, {ec} elec_chars, {pins} pins → {out_name}")
            results.append(pdf_name)
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            errors.append((pdf_name, str(e)))

        # Rate limit between API calls
        if i < len(PDFS) - 1:
            print("  Waiting 5s for rate limit...")
            time.sleep(5)

    print(f"\n{'='*60}")
    print(f"Done: {len(results)}/{len(PDFS)} processed, {len(errors)} errors")
    if errors:
        for name, err in errors:
            print(f"  ✗ {name}: {err}")

if __name__ == "__main__":
    main()
