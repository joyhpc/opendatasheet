#!/usr/bin/env python3
"""Validate sch-review export JSON files against the device schema.

Usage:
    python validate_exports.py                          # validate all
    python validate_exports.py data/sch_review_export/AMS1117.json  # validate one
    python validate_exports.py --summary                # counts only
"""

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator, ValidationError
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


def validate_file(validator, path: Path) -> list[str]:
    """Return list of error messages (empty = valid)."""
    with open(path) as f:
        data = json.load(f)
    errors = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"  [{loc}] {err.message}")
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
        # skip manifest
        files = [f for f in files if f.name != "_manifest.json"]

    total = 0
    passed = 0
    failed = 0
    fail_details = {}

    for f in files:
        total += 1
        errors = validate_file(validator, f)
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
    if failed:
        print(f"Failed files: {', '.join(fail_details.keys())}")
        sys.exit(1)
    else:
        print("All files valid ✓")


if __name__ == "__main__":
    main()
