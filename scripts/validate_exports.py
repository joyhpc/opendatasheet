#!/usr/bin/env python3
"""Validate sch-review export JSON files against the device schema.

Usage:
    python validate_exports.py                          # validate all
    python validate_exports.py data/sch_review_export/AMS1117.json  # validate one
    python validate_exports.py --summary                # counts only

Notes:
    Current export target is sch-review-device/1.1.
    Also supports device-knowledge/2.0 with domain sub-schemas.
    Legacy checked-in artifacts using sch-review-device/1.0 remain valid during migration.
"""

import json
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
except ImportError:
    print("ERROR: pip install jsonschema  (requires jsonschema>=4.18)")
    sys.exit(1)

SCHEMA_DIR = Path(__file__).parent.parent / "schemas"
SCHEMA_PATH = SCHEMA_DIR / "sch-review-device.schema.json"
DEFAULT_EXPORT_DIR = Path(__file__).parent.parent / "data/sch_review_export"


def _schema_store() -> dict[str, dict]:
    """Build a local schema registry for offline validation."""
    store = {}
    for schema_path in sorted(SCHEMA_DIR.rglob("*.json")):
        with open(schema_path) as f:
            schema = json.load(f)

        relative_path = schema_path.relative_to(SCHEMA_DIR).as_posix()
        file_uri = schema_path.resolve().as_uri()

        store[file_uri] = schema
        store[f"https://opendatasheet.dev/schemas/{relative_path}"] = schema
        store[f"https://opendatasheet.dev/schemas/sch-review-device/{relative_path}"] = schema
        for depth in range(1, 6):
            prefix = "domains/" * depth
            store[f"https://opendatasheet.dev/schemas/sch-review-device/{prefix}{relative_path}"] = schema

        schema_id = schema.get("$id")
        if isinstance(schema_id, str) and schema_id:
            store[schema_id] = schema
    return store


def _schema_resources() -> list[tuple[str, Resource]]:
    """Build a referencing registry resource list for offline validation."""
    resources = []
    for uri, schema in _schema_store().items():
        resources.append((uri, Resource.from_contents(schema)))
    return resources


def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    Draft202012Validator.check_schema(schema)

    # Keep validation fully offline even when schema $id values are remote URLs.
    registry = Registry().with_resources(_schema_resources())
    return Draft202012Validator(schema, registry=registry)


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_data(validator, data: dict) -> list[str]:
    """Return list of error messages (empty = valid)."""
    errors = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"  [{loc}] {err.message}")
    return errors


def validate_file(validator, path: Path) -> list[str]:
    return validate_data(validator, load_json(path))


def semantic_checks(data: dict) -> list[str]:
    errors = []
    if data.get("_type") == "fpga":
        summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
        by_function = summary.get("by_function", {}) if isinstance(summary, dict) else {}
        capability_blocks = data.get("capability_blocks", {}) or {}
        constraint_blocks = data.get("constraint_blocks", {}) or {}
        has_mipi = by_function.get("MIPI", 0) > 0
        has_hs = any(
            pair.get("type") in ("SERDES_RX", "SERDES_TX", "SERDES_REFCLK", "GT_RX", "GT_TX", "GT_REFCLK", "REFCLK")
            for pair in data.get("diff_pairs", [])
        )
        has_refclk = any(pair.get("type") in ("SERDES_REFCLK", "GT_REFCLK", "REFCLK") for pair in data.get("diff_pairs", []))
        if (has_mipi or has_hs) and not capability_blocks:
            errors.append("  [capability_blocks] missing capability_blocks for FPGA with high-speed interface pins")
        if has_mipi and "mipi_phy" not in capability_blocks:
            errors.append("  [capability_blocks.mipi_phy] missing mipi_phy capability block")
        if has_hs and "high_speed_serial" not in capability_blocks:
            errors.append("  [capability_blocks.high_speed_serial] missing high_speed_serial capability block")
        if has_refclk and "refclk_requirements" not in constraint_blocks:
            errors.append("  [constraint_blocks.refclk_requirements] missing refclk_requirements constraint block")
        if "refclk_requirements" in constraint_blocks and not constraint_blocks.get("refclk_requirements", {}).get("refclk_pairs"):
            errors.append("  [constraint_blocks.refclk_requirements.refclk_pairs] missing concrete refclk pair details")
        refclk_req = constraint_blocks.get("refclk_requirements", {}) or {}
        if has_refclk and has_hs and not refclk_req.get("lane_group_mappings"):
            errors.append("  [constraint_blocks.refclk_requirements.lane_group_mappings] missing refclk-to-lane group mapping details")
        hs_protocols = [p for p in (capability_blocks.get("high_speed_serial", {}) or {}).get("supported_protocols", []) if p != "custom"]
        refclk_profiles = refclk_req.get("protocol_refclk_profiles", {})
        if hs_protocols and not refclk_profiles:
            errors.append("  [constraint_blocks.refclk_requirements.protocol_refclk_profiles] missing source-backed protocol refclk profiles")
        if hs_protocols:
            for group in refclk_req.get("lane_group_mappings", []) or []:
                if not group.get("candidate_protocols"):
                    errors.append("  [constraint_blocks.refclk_requirements.lane_group_mappings.candidate_protocols] missing protocol candidates for lane group")
                    break
                if not group.get("bundle_tags") or not group.get("use_case_tags"):
                    errors.append("  [constraint_blocks.refclk_requirements.lane_group_mappings.bundle_tags] missing bundle/use-case tags for lane group")
                    break
            for pair in refclk_req.get("refclk_pairs", []) or []:
                if pair.get("mapped_lane_groups") and not pair.get("candidate_protocols"):
                    errors.append("  [constraint_blocks.refclk_requirements.refclk_pairs.candidate_protocols] missing protocol candidates for refclk pair")
                    break
                if pair.get("mapped_lane_groups") and (not pair.get("bundle_tags") or not pair.get("use_case_tags")):
                    errors.append("  [constraint_blocks.refclk_requirements.refclk_pairs.bundle_tags] missing bundle/use-case tags for refclk pair")
                    break
    if data.get("_type") == "normal_ic":
        capability_blocks = data.get("capability_blocks", {}) or {}
        constraint_blocks = data.get("constraint_blocks", {}) or {}
        if str(data.get("mpn", "")).upper().startswith(("STM32", "GD32", "N32", "LPC", "PIC")):
            packages = data.get("packages", {})
            pin_names = []
            for package in packages.values():
                for pin in package.get("pins", {}).values():
                    pin_names.append((pin.get("name") or "").upper())
            has_debug = any(any(token in name for token in ("SWDIO", "SWCLK", "JTMS", "JTCK", "JTDI", "JTDO")) for name in pin_names)
            has_boot = any("BOOT" in name for name in pin_names)
            has_clock = any(any(token in name for token in ("OSC_IN", "OSC_OUT", "OSC32", "HSE", "LSE", "PH0", "PH1", "PC14", "PC15")) for name in pin_names)
            if (has_debug or has_boot or has_clock) and not capability_blocks:
                errors.append("  [capability_blocks] missing capability_blocks for MCU-like device with debug/boot/clock pins")
            if has_debug and "debug_access" not in capability_blocks:
                errors.append("  [capability_blocks.debug_access] missing debug_access capability block")
            if has_boot and "boot_configuration" not in capability_blocks:
                errors.append("  [capability_blocks.boot_configuration] missing boot_configuration capability block")
            if has_clock and "clocking" not in capability_blocks:
                errors.append("  [capability_blocks.clocking] missing clocking capability block")
            if has_debug and "debug_access" not in constraint_blocks:
                errors.append("  [constraint_blocks.debug_access] missing debug_access constraint block")
            for block_name in ("usb_interface", "ethernet_interface", "can_interface", "serial_memory_interface", "storage_interface"):
                if block_name in capability_blocks and block_name not in constraint_blocks:
                    errors.append(f"  [constraint_blocks.{block_name}] missing {block_name} constraint block")
    return errors


def main():
    args = sys.argv[1:]
    summary_only = "--summary" in args
    args = [a for a in args if a != "--summary"]

    validator = load_schema()

    if args:
        files = [Path(a) for a in args]
    else:
        files = sorted(DEFAULT_EXPORT_DIR.glob("*.json"))
        files = [f for f in files if not f.name.startswith("_")]

    total = 0
    passed = 0
    failed = 0
    fail_details = {}
    schema_versions = {}

    for f in files:
        total += 1
        data = load_json(f)
        schema_ver = data.get("_schema", "<missing>")
        schema_versions[schema_ver] = schema_versions.get(schema_ver, 0) + 1
        errors = validate_data(validator, data) + semantic_checks(data)
        if errors:
            failed += 1
            fail_details[f.name] = errors
            if not summary_only:
                print(f"FAIL  {f.name}  ({len(errors)} errors)")
                for e in errors[:10]:
                    print(e)
                if len(errors) > 10:
                    print(f"  ... and {len(errors) - 10} more")
                print()
        else:
            passed += 1
            if not summary_only:
                print(f"OK    {f.name}")

    print(f"\n{'='*50}")
    print(f"Total: {total}  |  Passed: {passed}  |  Failed: {failed}")
    print("Schema versions: " + ", ".join(f"{k}={v}" for k, v in sorted(schema_versions.items())))
    if failed:
        print(f"Failed files: {', '.join(fail_details.keys())}")
        sys.exit(1)
    else:
        print("All files valid")


if __name__ == "__main__":
    main()
