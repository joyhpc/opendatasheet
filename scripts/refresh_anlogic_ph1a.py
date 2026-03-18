#!/usr/bin/env python3
"""Refresh the full Anlogic PH1A package-capability pipeline."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable or "python3"

PARSE_SCRIPT = REPO_ROOT / "scripts" / "parse_anlogic_ph1a.py"
PINOUT_PARSE_SCRIPT = REPO_ROOT / "scripts" / "parse_anlogic_ph1a_pinout.py"
EXPORT_SCRIPT = REPO_ROOT / "scripts" / "export_anlogic_ph1a_sch_review.py"
VALIDATE_SCRIPT = REPO_ROOT / "scripts" / "validate_exports.py"
EXPORT_DIR = REPO_ROOT / "data" / "sch_review_export"

EXPECTED_EXPORTS = [
    "PH1A400SFG900.json",
    "PH1A400SFG676.json",
    "PH1A180SFG676.json",
    "PH1A90SBG484.json",
    "PH1A90SEG324.json",
    "PH1A90SEG325.json",
    "PH1A60GEG324.json",
]


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    _run([PYTHON, str(PARSE_SCRIPT)])
    _run([PYTHON, str(PINOUT_PARSE_SCRIPT)])
    _run([PYTHON, str(EXPORT_SCRIPT)])
    _run([PYTHON, str(VALIDATE_SCRIPT), *[str(EXPORT_DIR / name) for name in EXPECTED_EXPORTS]])
    print("Anlogic PH1A refresh complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
