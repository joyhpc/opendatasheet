#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build document coverage for high-risk BOM key materials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ACTIVE_RISK_TAGS = {
    "programmable_logic",
    "mcu_processor",
    "memory",
    "high_speed_interface",
    "power",
    "integrated_circuit",
}


ALIASES = {
    "A5EC052A B32A": ("A5EC052A_B32A", "A5EC052AB32A"),
    "DS25BR101TSDE": ("DS25BR101TSDE/NOPB", "DS25BR101"),
    "LM3880-1AE": ("LM3880MF-1AE/NOPB", "LM3880"),
    "TPS56637RPAR": ("TPS56637",),
    "TC7PCI3212MT": ("TC7PCI3212",),
    "RT6365GSP": ("RT6365",),
    "K3KL8L80QM-MGCT": ("K3KL8L80QM-MGCT",),
    "W25Q256JWEIQ": ("W25Q256JW", "W25Q256"),
}


def norm(value: str | None) -> str:
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def alias_keys(mpn: str) -> set[str]:
    keys = {norm(mpn)}
    for alias in ALIASES.get(mpn, ()):
        keys.add(norm(alias))
    for suffix in ("NOPB", "TR", "RPAR", "RNNR", "DSQR", "DRVR", "PDQNR", "RHLT", "GSP"):
        for key in list(keys):
            if key.endswith(suffix):
                keys.add(key[: -len(suffix)])
    return {key for key in keys if key}


def load_manifest_entries(paths: list[Path]) -> list[dict]:
    entries = []
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries.extend(payload.get("entries", []))
    return entries


def related_docs(mpn: str, entries_by_mpn: dict[str, list[dict]]) -> list[dict]:
    keys = alias_keys(mpn)
    docs = []
    for candidate_mpn, entries in entries_by_mpn.items():
        candidate_keys = alias_keys(candidate_mpn)
        if keys & candidate_keys:
            docs.extend(entries)
    return docs


def local_sources(mpn: str, repo_root: Path) -> list[str]:
    candidates = []
    normalized = norm(mpn)
    for path in [repo_root / "data" / "sch_review_export", repo_root / "data" / "extracted_v2", repo_root / "data" / "selection_profile"]:
        if not path.exists():
            continue
        for file in path.rglob("*.json"):
            if normalized and normalized in norm(file.stem):
                candidates.append(str(file))

    if "A5EC052AB32A" in normalized or ("A5EC052A" in normalized and "B32A" in normalized):
        for rel in (
            "data/raw/fpga/intel_agilex5/a5ec052a.xlsx",
            "data/extracted_v2/fpga/pinout/intel_agilex5_a5ec052a_b32a.json",
            "data/sch_review_export/A5EC052A_B32A.json",
        ):
            path = repo_root / rel
            if path.exists():
                candidates.append(str(path))
    return sorted(set(candidates))


def build_doc_coverage(key_report: dict, manifest_paths: list[Path], repo_root: Path) -> dict:
    entries = load_manifest_entries(manifest_paths)
    entries_by_mpn: dict[str, list[dict]] = {}
    for entry in entries:
        entries_by_mpn.setdefault(entry.get("mpn", ""), []).append(entry)

    coverage = []
    for item in key_report.get("key_materials", []):
        risk_tags = set(item.get("risk_tags", []))
        if not (risk_tags & ACTIVE_RISK_TAGS):
            continue

        docs = related_docs(item.get("mpn", ""), entries_by_mpn)
        downloaded = [doc for doc in docs if "path" in doc]
        datasheets = [doc for doc in downloaded if doc.get("doc_kind") == "datasheet"]
        app_notes = [doc for doc in downloaded if doc.get("doc_kind") == "app_note"]
        product_pages = [doc for doc in downloaded if doc.get("doc_kind") == "product_page"]
        local_design = [doc for doc in downloaded if doc.get("doc_kind") == "local_design_evidence"]
        private_notes = [doc for doc in downloaded if doc.get("doc_kind") == "private_component_note"]
        official = [doc for doc in downloaded if doc.get("seed_status") == "official_found"]
        fallback = [doc for doc in downloaded if doc.get("seed_status") == "fallback_only"]
        local = local_sources(item.get("mpn", ""), repo_root)

        if datasheets and official:
            status = "official_datasheet_downloaded"
        elif datasheets and fallback:
            status = "fallback_datasheet_downloaded"
        elif product_pages and official:
            status = "official_product_page_downloaded"
        elif local_design:
            status = "local_design_evidence"
        elif private_notes:
            status = "private_component_declared"
        elif local:
            status = "local_source_backed"
        else:
            status = "missing"

        coverage.append(
            {
                "line_number": item.get("line_number"),
                "mpn": item.get("mpn", ""),
                "manufacturer": item.get("manufacturer", ""),
                "risk_tags": item.get("risk_tags", []),
                "coverage_status": status,
                "downloaded_doc_count": len(downloaded),
                "datasheet_doc_count": len(datasheets),
                "app_note_count": len(app_notes),
                "official_doc_count": len(official),
                "fallback_doc_count": len(fallback),
                "local_source_count": len(local),
                "local_design_evidence_count": len(local_design),
                "private_note_count": len(private_notes),
                "datasheet_paths": [doc.get("path") for doc in datasheets[:4]],
                "app_note_paths": [doc.get("path") for doc in app_notes[:4]],
                "local_design_paths": [doc.get("path") for doc in local_design[:4]],
                "private_note_paths": [doc.get("path") for doc in private_notes[:4]],
                "local_sources": local[:5],
                "doc_titles": [
                    (doc.get("text_preview") or "").split("  ")[0][:180]
                    for doc in (datasheets + app_notes + local_design + private_notes)[:4]
                ],
            }
        )

    summary: dict[str, int] = {}
    for row in coverage:
        status = row["coverage_status"]
        summary[status] = summary.get(status, 0) + 1

    return {
        "_schema": "bom-device-doc-coverage/1.1",
        "source_report": key_report.get("source", {}).get("path", ""),
        "manifests": [str(path) for path in manifest_paths],
        "summary": summary,
        "active_key_material_count": len(coverage),
        "coverage": coverage,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("key_report", type=Path)
    parser.add_argument("--manifest", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)

    key_report = json.loads(args.key_report.read_text(encoding="utf-8"))
    coverage = build_doc_coverage(key_report, args.manifest, args.repo_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"active_key_material_count": coverage["active_key_material_count"], "summary": coverage["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
