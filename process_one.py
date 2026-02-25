#!/usr/bin/env python3
"""Process a single TI datasheet PDF using pipeline_v2."""
import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline_v2 import process_single_pdf

PDF_DIR = Path(__file__).parent / "data" / "pdfs" / "ti"
OUTPUT_DIR = Path(__file__).parent / "data" / "extracted_v2"

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 process_one.py <pdf_name>")
        sys.exit(1)
    
    pdf_name = sys.argv[1]
    pdf_path = PDF_DIR / pdf_name
    out_name = pdf_name.replace(".pdf", ".json")
    out_path = OUTPUT_DIR / out_name
    
    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        sys.exit(1)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        result = process_single_pdf(str(pdf_path))
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        ext = result.get("extraction", {})
        if isinstance(ext, dict) and "error" not in ext:
            print(f"✅ {pdf_name}: AMR={len(ext.get('absolute_maximum_ratings', []))} EC={len(ext.get('electrical_characteristics', []))} Pins={len(ext.get('pin_definitions', []))}")
        else:
            print(f"⚠️ {pdf_name}: extraction had error")
            sys.exit(2)
    except Exception as e:
        print(f"❌ {pdf_name}: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
