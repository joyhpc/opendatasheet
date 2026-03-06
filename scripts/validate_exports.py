#!/usr/bin/env python3
"""Validate sch-review export JSON files against the device schema.

Usage:
    python validate_exports.py                          # validate all
    python validate_exports.py data/sch_review_export/AMS1117.json  # validate one
    python validate_exports.py --summary                # counts only

Notes:
    Current export target is sch-review-device/1.1.
    Legacy checked-in artifacts using sch-review-device/1.0 remain valid during migration.
"""

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("ERROR: pip install jsonschema  (requires jsonschema>=4.18)")
    sys.exit(1)

SCHEMA_PATH = Path(__file__).parent.parent / "schemas/sch-review-device.schema.json"
DEFAULT_EXPORT_DIR = Path(__file__).parent.parent / "data/sch_review_export"


def load_schema():
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def load_json(path: Path) -> dict:
    with open(path) as f:
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


def main():
    args = sys.argv[1:]
    summary_only = "--summary" in args
    args = [a for a in args if a != "--summary"]

    validator = load_schema()

    if args:
        files = [Path(a) for a in args]
    else:
        files = sorted(DEFAULT_EXPORT_DIR.glob("*.json"))
        files = [f for f in files if f.name != "_manifest.json"]

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
        errors = validate_data(validator, data)
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
        print("All files valid ✓")


if __name__ == "__main__":
    main()
