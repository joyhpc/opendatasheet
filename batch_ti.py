#!/usr/bin/env python3
"""Batch process TI hot-swap/eFuse/ideal-diode datasheets using pipeline_v2."""
import json
import os
import sys
import time
import shutil
import traceback
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))
from pipeline_v2 import process_single_pdf

PDF_DIR = Path(__file__).parent / "data" / "pdfs" / "ti"
OUTPUT_DIR = Path(__file__).parent / "data" / "extracted_v2"

# PDFs to process (one per unique datasheet)
PDFS_TO_PROCESS = [
    # Hot-Swap Controllers
    "tps2480_ds.pdf",   # TPS2480/TPS2481
    "tps2410_ds.pdf",   # TPS2410/TPS2411
    "tps2412_ds.pdf",   # TPS2412/TPS2413
    "tps2420_ds.pdf",
    "lm5067_ds.pdf",
    "lm5068_ds.pdf",
    # eFuse
    "tps2595_ds.pdf",
    "tps2590_ds.pdf",
    "tps25940_ds.pdf",
    "tps2660_ds.pdf",
    "tps2661_ds.pdf",
    "tps2662_ds.pdf",
    "tps2663_ds.pdf",
    "tps1663_ds.pdf",
    "tps1h100-q1_ds.pdf",
    # Ideal Diode / Power MUX
    "lm66100_ds.pdf",
    "lm66200_ds.pdf",
    "tps2113_ds.pdf",
    "tps2113a_ds.pdf",
    "tps2114_ds.pdf",   # TPS2114/TPS2115
    "lm5051_ds.pdf",
]

# Duplicate PDFs: source -> copy targets
DUPLICATES = {
    "tps2480_ds.json": ["tps2481_ds.json"],
    "tps2410_ds.json": ["tps2411_ds.json"],
    "tps2412_ds.json": ["tps2413_ds.json"],
    "tps2114_ds.json": ["tps2115_ds.json"],
}

# Already extracted (skip)
SKIP = {
    "lm5060_ds.pdf", "lm5064_ds.pdf", "lm5069_ds.pdf",
    "lm74610q1_ds.pdf", "tps2490_ds.pdf", "tps2596_ds.pdf",
}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    results = []
    errors = []
    
    for i, pdf_name in enumerate(PDFS_TO_PROCESS):
        if pdf_name in SKIP:
            print(f"\n⏭ Skipping (already done): {pdf_name}")
            continue
            
        out_name = pdf_name.replace(".pdf", ".json")
        out_path = OUTPUT_DIR / out_name
        
        if out_path.exists() and out_path.stat().st_size > 100:
            print(f"\n⏭ Skipping (output exists): {pdf_name}")
            results.append(pdf_name)
            continue
        
        pdf_path = PDF_DIR / pdf_name
        if not pdf_path.exists():
            print(f"\n❌ PDF not found: {pdf_name}")
            errors.append((pdf_name, "File not found"))
            continue
        
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(PDFS_TO_PROCESS)}] Processing: {pdf_name}")
        print(f"{'='*60}")
        
        try:
            result = process_single_pdf(str(pdf_path))
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            results.append(pdf_name)
            print(f"✅ Saved: {out_name}")
        except Exception as e:
            print(f"❌ Error processing {pdf_name}: {e}")
            traceback.print_exc()
            errors.append((pdf_name, str(e)))
        
        # Rate limit: wait between API calls
        if i < len(PDFS_TO_PROCESS) - 1:
            wait = 6
            print(f"⏳ Waiting {wait}s for rate limit...")
            time.sleep(wait)
    
    # Copy duplicates
    print(f"\n{'='*60}")
    print("Copying duplicate datasheets...")
    for source, targets in DUPLICATES.items():
        src_path = OUTPUT_DIR / source
        if src_path.exists():
            for target in targets:
                tgt_path = OUTPUT_DIR / target
                shutil.copy2(src_path, tgt_path)
                print(f"  📋 {source} → {target}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE")
    print(f"{'='*60}")
    print(f"Processed: {len(results)}")
    print(f"Errors: {len(errors)}")
    if errors:
        print("Failed PDFs:")
        for name, err in errors:
            print(f"  ❌ {name}: {err}")
    
    return errors


if __name__ == "__main__":
    errors = main()
    sys.exit(1 if errors else 0)
