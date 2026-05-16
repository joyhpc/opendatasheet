#!/usr/bin/env python3
"""Prototype export-freshness check.

Regenerates the sch-review export into a temporary directory and compares it
against the checked-in ``data/sch_review_export/``. Reports drift without ever
touching the real data — the checked-in files are read-only here.

This is a prototype intended to later become a CI gate that fails when the
checked-in exports no longer match what the exporter produces.

Exit codes:
    0  checked-in exports are in sync with the exporter
    1  drift detected (changed / missing / removed device files)
    2  setup error (live export dir missing)

Usage:
    python scripts/check_exports_fresh.py
"""
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_for_sch_review as exporter

LIVE_EXPORT_DIR = REPO_ROOT / "data" / "sch_review_export"


def _device_files(directory: Path) -> dict[str, str]:
    """Map device-file name -> content for non-underscore JSON files."""
    out: dict[str, str] = {}
    for path in sorted(Path(directory).glob("*.json")):
        if path.name.startswith("_"):
            continue
        out[path.name] = path.read_text(encoding="utf-8")
    return out


def compare(live_dir: Path, fresh_dir: Path) -> dict:
    """Compare two export directories. Pure function — no side effects."""
    live = _device_files(live_dir)
    fresh = _device_files(fresh_dir)
    live_names, fresh_names = set(live), set(fresh)
    return {
        "missing": sorted(fresh_names - live_names),   # produced now, not checked in
        "removed": sorted(live_names - fresh_names),   # checked in, not produced now
        "changed": sorted(n for n in live_names & fresh_names if live[n] != fresh[n]),
        "total_live": len(live),
        "total_fresh": len(fresh),
    }


def regenerate_into(tmp_dir: Path) -> None:
    """Run the exporter into tmp_dir using the checked-in inputs only."""
    old_argv = sys.argv[:]
    sys.argv = [
        "export_for_sch_review.py",
        str(exporter.DEFAULT_EXTRACTED_DIR),
        str(exporter.DEFAULT_FPGA_PINOUT_DIR),
        str(tmp_dir),
    ]
    try:
        exporter.main()
    except SystemExit:
        # main() exits non-zero when some device failed to export; the
        # freshness comparison below still runs on whatever was produced.
        pass
    finally:
        sys.argv = old_argv


def main() -> int:
    if not LIVE_EXPORT_DIR.is_dir():
        print(f"ERROR: {LIVE_EXPORT_DIR} not found", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        regenerate_into(Path(tmp))
        diff = compare(LIVE_EXPORT_DIR, Path(tmp))

    print(f"\nchecked-in: {diff['total_live']} device files | "
          f"regenerated: {diff['total_fresh']} device files")

    drift = diff["missing"] or diff["removed"] or diff["changed"]
    if not drift:
        print("OK: checked-in exports are in sync with the exporter.")
        return 0

    print("DRIFT: checked-in exports differ from a fresh regeneration.")
    for label in ("changed", "missing", "removed"):
        names = diff[label]
        if names:
            preview = ", ".join(names[:10])
            more = "" if len(names) <= 10 else f" (+{len(names) - 10} more)"
            print(f"  {label} ({len(names)}): {preview}{more}")
    print("To refresh: python scripts/export_for_sch_review.py   (then review the diff)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
