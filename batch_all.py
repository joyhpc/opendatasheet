#!/usr/bin/env python3
"""Batch process ALL company IC datasheets using pipeline_v2.

Processes PDFs from data/pdfs/all/, skips already-processed files,
outputs to data/extracted_v2/.

Usage:
    python3 batch_all.py              # process all new PDFs
    python3 batch_all.py --limit 10   # process first 10 new PDFs
    python3 batch_all.py --dry-run    # list what would be processed
"""
import json
import os
import sys
import time
import traceback
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline_v2 import process_single_pdf

PDF_DIR = Path(__file__).parent / "data" / "pdfs" / "all"
OUTPUT_DIR = Path(__file__).parent / "data" / "extracted_v2"
ALREADY_DONE_DIR = Path(__file__).parent / "data" / "raw" / "datasheet_PDF"

# Rate limiting for Gemini API
DELAY_BETWEEN_PDFS = 3  # seconds


def get_output_name(pdf_name: str) -> str:
    """Generate output JSON filename from PDF name."""
    stem = Path(pdf_name).stem
    return f"{stem}.json"


def is_already_processed(pdf_name: str) -> bool:
    """Check if this PDF has already been processed."""
    out_name = get_output_name(pdf_name)
    out_path = OUTPUT_DIR / out_name
    if out_path.exists() and out_path.stat().st_size > 100:
        return True
    return False


def collect_new_pdfs() -> list[Path]:
    """Collect all PDFs that haven't been processed yet."""
    all_pdfs = sorted(
        f for f in PDF_DIR.iterdir()
        if f.suffix.lower() == '.pdf'
    )
    new_pdfs = []
    for pdf in all_pdfs:
        if not is_already_processed(pdf.name):
            new_pdfs.append(pdf)
    return new_pdfs


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='Max PDFs to process (0=all)')
    parser.add_argument('--dry-run', action='store_true', help='List files without processing')
    parser.add_argument('--category', type=str, default='', help='Filter by category prefix (e.g. 0130-01)')
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    new_pdfs = collect_new_pdfs()

    if args.category:
        new_pdfs = [p for p in new_pdfs if p.name.startswith(args.category)]

    if args.limit > 0:
        new_pdfs = new_pdfs[:args.limit]

    print(f"=" * 60)
    print(f"OpenDatasheet Batch Processor — Full Company IC Library")
    print(f"=" * 60)
    print(f"PDF source: {PDF_DIR}")
    print(f"Output dir: {OUTPUT_DIR}")
    print(f"Total new PDFs to process: {len(new_pdfs)}")
    if args.category:
        print(f"Category filter: {args.category}")
    print()

    if args.dry_run:
        for i, pdf in enumerate(new_pdfs):
            size_kb = pdf.stat().st_size / 1024
            print(f"  [{i+1:3d}] {pdf.name} ({size_kb:.0f} KB)")
        print(f"\nTotal: {len(new_pdfs)} PDFs")
        return

    # Process
    success = 0
    failed = 0
    failed_list = []
    total_params = 0
    start_time = time.time()

    for i, pdf_path in enumerate(new_pdfs):
        out_name = get_output_name(pdf_path.name)
        out_path = OUTPUT_DIR / out_name

        print(f"\n[{i+1}/{len(new_pdfs)}] {pdf_path.name}")

        try:
            result = process_single_pdf(str(pdf_path), verbose=True)

            ext = result.get("extraction", {})
            if isinstance(ext, dict) and "error" not in ext:
                n_params = (len(ext.get("absolute_maximum_ratings", [])) +
                           len(ext.get("electrical_characteristics", [])))
                total_params += n_params
                print(f"  ✓ {n_params} params extracted")
                success += 1
            else:
                err = ext.get("error", "unknown") if isinstance(ext, dict) else "bad extraction"
                print(f"  ✗ Extraction error: {err}")
                failed += 1
                failed_list.append((pdf_path.name, str(err)[:100]))

            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"  ✗ EXCEPTION: {e}")
            traceback.print_exc()
            failed += 1
            failed_list.append((pdf_path.name, str(e)[:100]))

        # Rate limit
        if i < len(new_pdfs) - 1:
            time.sleep(DELAY_BETWEEN_PDFS)

    elapsed = time.time() - start_time

    # Summary
    print(f"\n{'=' * 60}")
    print(f"BATCH COMPLETE")
    print(f"{'=' * 60}")
    print(f"Processed: {success + failed} / {len(new_pdfs)}")
    print(f"Success:   {success}")
    print(f"Failed:    {failed}")
    print(f"Total params: {total_params}")
    print(f"Time: {elapsed/60:.1f} minutes ({elapsed/(success+failed):.1f}s avg)")

    if failed_list:
        print(f"\nFailed files:")
        for name, err in failed_list:
            print(f"  ✗ {name}: {err}")

    # Write batch summary
    summary_path = OUTPUT_DIR / "_batch_all_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
            "total_processed": success + failed,
            "success": success,
            "failed": failed,
            "total_params": total_params,
            "elapsed_minutes": round(elapsed / 60, 1),
            "failed_files": failed_list,
        }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
