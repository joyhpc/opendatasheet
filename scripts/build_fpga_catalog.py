#!/usr/bin/env python3
"""Build a tree-style catalog of FPGA exports for navigation and coverage review."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_EXPORT_DIR = Path(__file__).parent.parent / "data" / "sch_review_export"
DEFAULT_OUTPUT = DEFAULT_EXPORT_DIR / "_fpga_catalog.json"
SCHEMA_VERSION = "1.0"


def _sorted_dict(value):
    if isinstance(value, dict):
        return {key: _sorted_dict(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sorted_dict(item) for item in value]
    return value


def build_catalog(export_dir: Path) -> dict:
    tree: dict[str, dict] = {}
    vendor_set: set[str] = set()
    family_set: set[tuple[str, str]] = set()
    series_set: set[tuple[str, str, str]] = set()
    base_device_set: set[tuple[str, str, str, str]] = set()
    device_set: set[tuple[str, str, str, str, str]] = set()
    package_count = 0

    for path in sorted(export_dir.glob("*.json")):
        if path.name in {"_manifest.json", "_fpga_catalog.json"}:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("_type") != "fpga":
            continue

        ident = data.get("device_identity") or {}
        vendor = ident.get("vendor") or data.get("manufacturer") or "Unknown"
        family = ident.get("family") or "Unknown"
        series = ident.get("series") or family
        base_device = ident.get("base_device") or data.get("mpn") or "Unknown"
        device = ident.get("device") or data.get("mpn") or "Unknown"
        package = ident.get("package") or data.get("package") or "Unknown"

        vendor_set.add(vendor)
        family_set.add((vendor, family))
        series_set.add((vendor, family, series))
        base_device_set.add((vendor, family, series, base_device))
        device_set.add((vendor, family, series, base_device, device))
        package_count += 1

        vendor_node = tree.setdefault(vendor, {"families": {}})
        family_node = vendor_node["families"].setdefault(family, {"series": {}})
        series_node = family_node["series"].setdefault(series, {"base_devices": {}})
        base_node = series_node["base_devices"].setdefault(base_device, {"devices": {}})
        device_node = base_node["devices"].setdefault(device, {"packages": {}})
        device_node["packages"][package] = {
            "file": path.name,
            "device_role": data.get("device_role"),
            "has_hps": bool((data.get("capability_blocks") or {}).get("hard_processor")),
            "has_serdes": bool((data.get("capability_blocks") or {}).get("high_speed_serial")),
        }

    catalog = {
        "_schema_version": SCHEMA_VERSION,
        "_type": "fpga_catalog",
        "summary": {
            "vendor_count": len(vendor_set),
            "family_count": len(family_set),
            "series_count": len(series_set),
            "base_device_count": len(base_device_set),
            "device_count": len(device_set),
            "package_count": package_count,
        },
        "tree": _sorted_dict(tree),
    }
    return catalog


def main() -> int:
    export_dir = DEFAULT_EXPORT_DIR
    catalog = build_catalog(export_dir)
    DEFAULT_OUTPUT.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {DEFAULT_OUTPUT} ({catalog['summary']['device_count']} devices, {catalog['summary']['package_count']} packages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
