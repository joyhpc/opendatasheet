#!/usr/bin/env python3
"""Build a canonical manifest for raw source documents under data/raw.

The manifest is an inventory for reproducibility rather than extracted content.
It tells us which original PDF/XLSX/CSV source file is stored where, what kind
of document it is, whether it is canonical or duplicate, and how to verify the
file by hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

RAW_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv"}
DEFAULT_RAW_ROOT = Path(__file__).parent.parent / "data" / "raw"
DEFAULT_OUTPUT = DEFAULT_RAW_ROOT / "_source_manifest.json"
POLICY_VERSION = "1.0"

VENDOR_HINTS = [
    ("anlogic", "Anlogic"),
    ("安路", "Anlogic"),
    ("gowin", "Gowin"),
    ("xilinx", "AMD/Xilinx"),
    ("amd", "AMD/Xilinx"),
    ("lattice", "Lattice"),
    ("altera", "Intel/Altera"),
    ("intel", "Intel/Altera"),
    ("microchip", "Microchip"),
    ("ti", "TI"),
    ("texas instruments", "TI"),
    ("analog devices", "ADI"),
    ("adi", "ADI"),
    ("maxim", "Maxim"),
    ("renesas", "Renesas"),
    ("st", "ST"),
    ("onsemi", "onsemi"),
    ("nxp", "NXP"),
    ("infineon", "Infineon"),
]

FAMILY_PATTERNS = [
    r"(PH1A)",
    r"(PH1A\d+(?:[A-Z]{3}\d+)?)",
    r"(A5E[A-Z]\d{3}[AB])",
    r"(A5D\d{3})",
    r"(Agilex\s*5)",
    r"(GW5\w+-\d+)",
    r"(GW5\w+)",
    r"(GW2A-\d+)",
    r"(GW1NR?-?(?:\d+(?:P\d+)?[A-Z]?|1S|9C)?)",
    r"(Arora[_ ]?V(?:[_ ]?\d*K)?)",
    r"(XC[A-Z0-9-]+)",
    r"(XCF\w+)",
    r"(LIFCL-[A-Z0-9-]+)",
    r"(ECP5U?-\d+)",
    r"(Cyclone\s+[A-Za-z0-9]+)",
    r"(Artix\s+[A-Za-z0-9+-]+)",
    r"(Kintex\s+[A-Za-z0-9+-]+)",
    r"(Versal\s+[A-Za-z0-9+-]+)",
    r"(MAX\s*10)",
]

DOC_TYPE_RULES = [
    ("package_guide", ("封装与管脚", "package and pin", "package_pin", "package guide", "封装信息")),
    ("pinout", ("pinout", "器件pinout", "管脚手册", "pin list")),
    ("marketing_summary", ("overview", "device overview", "product overview", "selector guide", "选型手册")),
    ("design_guide", ("原理图指导", "design guide", "layout guide", "layout guideline", "schematic guide", "硬件设计指南")),
    ("reference", ("reference design", "devboard", "evaluation module", "evm", "evb", "开发板", "dk_start", "使用指南", "使用说明")),
    ("app_note", ("application note", "appnote", "app note", "用户手册", "技术报告", "技术说明")),
    ("datasheet", ("datasheet", "数据手册")),
]


def _iter_source_files(raw_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in raw_root.rglob("*"):
        if not path.is_file():
            continue
        if path.name == DEFAULT_OUTPUT.name:
            continue
        if path.suffix.lower() not in RAW_EXTENSIONS:
            continue
        files.append(path)
    return sorted(files)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _storage_tier(relative_path: Path) -> str:
    parts = relative_path.parts[:-1]
    if any(part == "_duplicates" for part in parts):
        return "duplicate"
    if any(part == "_staging" for part in parts):
        return "staging"
    if any(part == "_archive" for part in parts):
        return "archive"
    return "canonical"


def _source_group(relative_path: Path) -> str:
    return relative_path.parts[0] if relative_path.parts else "unknown"


def _classify_doc_type(path: Path, relative_path: Path) -> str:
    haystack = f"{path.stem} {' '.join(relative_path.parts)}".lower()
    for doc_type, tokens in DOC_TYPE_RULES:
        if any(token in haystack for token in tokens):
            return doc_type
    if path.suffix.lower() in {".xlsx", ".xls"} and re.search(r"\bA5E[A-Z]\d{3}[AB]\b", path.stem, flags=re.IGNORECASE):
        return "pinout"
    if path.stem.lower().startswith("ds"):
        return "datasheet"
    if relative_path.parts and relative_path.parts[0] == "datasheet_PDF":
        return "datasheet"
    return "unknown"


def _vendor_hint(path: Path, relative_path: Path) -> str | None:
    haystack = re.sub(r"[^a-z0-9]+", " ", f"{path.stem} {' '.join(relative_path.parts)}".lower())
    for token, vendor in VENDOR_HINTS:
        normalized_token = re.sub(r"[^a-z0-9]+", " ", token.lower()).strip()
        if re.search(rf"(?<![a-z0-9]){re.escape(normalized_token)}(?![a-z0-9])", haystack):
            return vendor
    return None


def _family_hint(path: Path) -> str | None:
    stem = path.stem
    for pattern in FAMILY_PATTERNS:
        match = re.search(pattern, stem, flags=re.IGNORECASE)
        if match:
            token = match.group(1).replace("_", " ")
            upper = token.upper()
            if upper.startswith(("GW", "XC", "LIFCL", "ECP5", "A5E", "A5D")):
                return upper
            if upper.replace(" ", "") == "AGILEX5":
                return "Agilex 5"
            return token
    return None


def _material_hint(path: Path, doc_type: str, family_hint: str | None) -> str:
    stem = path.stem
    if family_hint:
        return family_hint
    if doc_type == "datasheet":
        cleaned = re.sub(r"^[0-9]{4}-[0-9]{2}-[0-9]{5}_", "", stem)
        return cleaned
    return stem


def build_manifest(raw_root: Path) -> dict:
    entries = []
    tier_counts: Counter[str] = Counter()
    doc_type_counts: Counter[str] = Counter()
    group_counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()

    for path in _iter_source_files(raw_root):
        rel = path.relative_to(raw_root)
        tier = _storage_tier(rel)
        group = _source_group(rel)
        doc_type = _classify_doc_type(path, rel)
        vendor = _vendor_hint(path, rel)
        family = _family_hint(path)
        fmt = path.suffix.lower().lstrip(".")
        material = _material_hint(path, doc_type, family)

        entry = {
            "path": str(rel).replace("\\", "/"),
            "filename": path.name,
            "format": fmt,
            "doc_type": doc_type,
            "storage_tier": tier,
            "source_group": group,
            "vendor_hint": vendor,
            "family_hint": family,
            "material_hint": material,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        entries.append(entry)
        tier_counts[tier] += 1
        doc_type_counts[doc_type] += 1
        group_counts[group] += 1
        format_counts[fmt] += 1

    entries.sort(key=lambda item: (item["source_group"], item["storage_tier"], item["doc_type"], item["path"]))
    return {
        "policy_version": POLICY_VERSION,
        "root": str(raw_root.relative_to(raw_root.parent.parent)).replace("\\", "/") if raw_root.name == "raw" else str(raw_root),
        "entry_count": len(entries),
        "summary": {
            "by_storage_tier": dict(sorted(tier_counts.items())),
            "by_doc_type": dict(sorted(doc_type_counts.items())),
            "by_source_group": dict(sorted(group_counts.items())),
            "by_format": dict(sorted(format_counts.items())),
        },
        "entries": entries,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Fail if the on-disk manifest differs from a freshly generated one")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_manifest(args.raw_root)
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not args.output.exists():
            print(f"missing manifest: {args.output}")
            return 1
        current = args.output.read_text(encoding="utf-8")
        if current != rendered:
            print(f"stale manifest: {args.output}")
            return 1
        print("raw_source_manifest=ok")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output} ({manifest['entry_count']} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
