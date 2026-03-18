#!/usr/bin/env python3
"""Export Anlogic PH1A records to sch-review FPGA JSON via the common exporter."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from build_fpga_catalog import build_catalog
from export_for_sch_review import export_fpga

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "pinout"
OUTPUT_DIR = REPO_ROOT / "data" / "sch_review_export"
CATALOG_PATH = OUTPUT_DIR / "_fpga_catalog.json"


def _dc_stub(record: dict) -> dict:
    device_identity = record.get("device_identity", {}) if isinstance(record.get("device_identity"), dict) else {}
    description = device_identity.get("series") or record.get("_series") or record.get("_family") or "PH1A"
    return {
        "extraction": {
            "component": {
                "manufacturer": "Anlogic",
                "description": description,
            }
        }
    }


def _is_anlogic_ph1a(record: dict) -> bool:
    if record.get("_vendor") != "Anlogic":
        return False
    return str(record.get("device", "")).startswith("PH1A")


def _export_record(record: dict) -> dict:
    if not _is_anlogic_ph1a(record):
        raise ValueError("record is not an Anlogic PH1A FPGA pinout export")
    return export_fpga(copy.deepcopy(_dc_stub(record)), copy.deepcopy(record))


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for path in sorted(INPUT_DIR.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if not _is_anlogic_ph1a(record):
            continue
        result = _export_record(record)
        out_path = OUTPUT_DIR / f"{result['mpn']}.json"
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written += 1

    catalog = build_catalog(OUTPUT_DIR)
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {written} Anlogic FPGA sch-review exports")
    print(f"updated {CATALOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
