#!/usr/bin/env python3
"""Lightweight repository environment doctor."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_PYTHON = (3, 11)

RUNTIME_DEPS = {
    "fitz": "PyMuPDF",
    "httpx": "httpx",
    "google.genai": "google-genai",
    "jsonschema": "jsonschema",
    "openpyxl": "openpyxl",
}

DEV_DEPS = {
    "pytest": "pytest",
}

REQUIRED_PATHS = {
    "README": ROOT / "README.md",
    "Guide": ROOT / "GUIDE.md",
    "Schema": ROOT / "schemas" / "sch-review-device.schema.json",
    "Export Dir": ROOT / "data" / "sch_review_export",
    "Checks Script": ROOT / "scripts" / "run_checks.sh",
}


def status(label: str, ok: bool, detail: str) -> bool:
    icon = "OK" if ok else "FAIL"
    print(f"[{icon}] {label}: {detail}")
    return ok



def check_python() -> bool:
    current = sys.version_info[:3]
    need = ".".join(map(str, MIN_PYTHON))
    have = ".".join(map(str, current))
    return status("Python", current >= MIN_PYTHON, f"have {have}, need >= {need}")



def check_imports(include_dev: bool) -> bool:
    all_ok = True
    deps = dict(RUNTIME_DEPS)
    if include_dev:
        deps.update(DEV_DEPS)
    for module_name, package_name in deps.items():
        try:
            importlib.import_module(module_name)
            ok = True
            detail = f"imported {module_name}"
        except Exception as exc:
            ok = False
            detail = f"missing {package_name} ({exc.__class__.__name__})"
        all_ok = status(f"Dependency {package_name}", ok, detail) and all_ok
    return all_ok



def check_paths() -> bool:
    all_ok = True
    for label, path in REQUIRED_PATHS.items():
        ok = path.exists()
        kind = "exists" if ok else "missing"
        all_ok = status(label, ok, f"{path.relative_to(ROOT)} {kind}") and all_ok
    return all_ok



def check_gemini(strict_env: bool) -> bool:
    present = bool(os.environ.get("GEMINI_API_KEY"))
    if present:
        return status("GEMINI_API_KEY", True, "set")
    if strict_env:
        return status("GEMINI_API_KEY", False, "missing")
    return status("GEMINI_API_KEY", True, "missing (warning only for non-extraction workflows)")



def main() -> int:
    parser = argparse.ArgumentParser(description="Repository environment doctor")
    parser.add_argument("--dev", action="store_true", help="also check dev-only dependencies like pytest")
    parser.add_argument("--strict-env", action="store_true", help="fail if GEMINI_API_KEY is unset")
    args = parser.parse_args()

    checks = [
        check_python(),
        check_imports(include_dev=args.dev),
        check_paths(),
        check_gemini(strict_env=args.strict_env),
    ]

    ok = all(checks)
    print("\nSummary: " + ("healthy" if ok else "needs attention"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
