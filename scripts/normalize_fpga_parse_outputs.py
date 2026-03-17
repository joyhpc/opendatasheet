#!/usr/bin/env python3
"""Normalize existing FPGA parse outputs onto the converged parse schema."""

from __future__ import annotations

import json
from pathlib import Path

from normalize_fpga_parse import normalize_fpga_parse_result

DEFAULT_INPUT_DIR = Path(__file__).parent.parent / "data" / "extracted_v2" / "fpga" / "pinout"


def main() -> int:
    input_dir = DEFAULT_INPUT_DIR
    count = 0
    for path in sorted(input_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        normalized = normalize_fpga_parse_result(data)
        path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        count += 1
    print(f"normalized {count} FPGA parse outputs in {input_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
