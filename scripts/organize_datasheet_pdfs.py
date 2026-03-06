#!/usr/bin/env python3
"""Organize raw datasheet PDFs into one canonical file per material+doc kind.

Rules:
- Prefer one canonical file for each `(material, doc_kind)` pair.
- Preserve the chosen canonical PDF in `data/raw/datasheet_PDF/` root.
- Move non-canonical duplicates into `data/raw/datasheet_PDF/_duplicates/<material>/`.
- Emit `_canonical_index.json` so downstream tooling can inspect the result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import fitz

DEFAULT_RAW_DIR = Path(__file__).parent.parent / "data" / "raw" / "datasheet_PDF"
DEFAULT_EXTRACTED_DIR = Path(__file__).parent.parent / "data" / "extracted_v2"
INDEX_NAME = "_canonical_index.json"
DUPLICATES_DIRNAME = "_duplicates"
DOC_KIND_ORDER = {
    "datasheet": 0,
    "design_guide": 1,
    "app_note": 2,
    "package": 3,
    "reference": 4,
    "unknown": 9,
}


@dataclass(frozen=True)
class PdfCandidate:
    path: Path
    material: str
    doc_kind: str
    score: int
    reason: str


def _sanitize(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._+-]+", "_", value.strip())
    return cleaned.strip("_") or "unknown"


def _iter_pdf_files(raw_dir: Path) -> list[Path]:
    files = []
    for path in raw_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue
        rel_parts = path.relative_to(raw_dir).parts
        if any(part.startswith("_") for part in rel_parts[:-1]):
            continue
        files.append(path)
    return sorted(files)


def _load_first_page_text(path: Path) -> str:
    try:
        doc = fitz.open(path)
        text = doc[0].get_text() if len(doc) else ""
        doc.close()
        return text
    except Exception:
        return ""


def classify_doc_kind(path: Path) -> str:
    name = path.name.lower()
    if any(token in name for token in ("design guide", "design_guide", "layout guide", "layout_guide")):
        return "design_guide"
    if any(token in name for token in ("application note", "appnote", "app_note", "an-")):
        return "app_note"
    if any(token in name for token in ("package", "outline", "land pattern", "mechanical")):
        return "package"
    if any(token in name for token in ("reference", "refdes", "eval", "evm", "devboard")):
        return "reference"

    text = _load_first_page_text(path)[:2000].lower()
    if any(token in text for token in ("design guide", "layout guidelines", "layout guide")):
        return "design_guide"
    if "application note" in text:
        return "app_note"
    if any(token in text for token in ("package information", "mechanical data", "land pattern")):
        return "package"
    if any(token in text for token in ("evaluation module", "reference design", "development board")):
        return "reference"
    return "datasheet"


def build_extracted_indexes(extracted_dir: Path) -> tuple[dict[str, str], dict[str, set[str]], dict[str, set[str]]]:
    pdf_to_mpn: dict[str, str] = {}
    tail_to_mpn: dict[str, set[str]] = defaultdict(set)
    mpn_to_pdf_names: dict[str, set[str]] = defaultdict(set)
    for path in sorted(extracted_dir.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        pdf_name = data.get("pdf_name")
        mpn = data.get("extraction", {}).get("component", {}).get("mpn")
        if not pdf_name or not mpn:
            continue
        sanitized_mpn = _sanitize(mpn)
        pdf_to_mpn[pdf_name] = sanitized_mpn
        mpn_to_pdf_names[sanitized_mpn].add(pdf_name)
        tail = re.sub(r"^[0-9]{4}-[0-9]{2}-[0-9]{5}_", "", Path(pdf_name).stem)
        tail_to_mpn[_sanitize(tail)].add(sanitized_mpn)
    return pdf_to_mpn, tail_to_mpn, mpn_to_pdf_names


def identify_material(path: Path, pdf_to_mpn: dict[str, str], tail_to_mpn: dict[str, set[str]]) -> tuple[str, str]:
    if path.name in pdf_to_mpn:
        return pdf_to_mpn[path.name], "exact_pdf_name"

    stem = path.stem
    stripped = re.sub(r"^[0-9]{4}-[0-9]{2}-[0-9]{5}_", "", stem)
    stripped_key = _sanitize(stripped)
    if stripped_key in tail_to_mpn and len(tail_to_mpn[stripped_key]) == 1:
        return next(iter(tail_to_mpn[stripped_key])), "inventory_tail"

    return stripped_key, "filename_fallback"


def score_candidate(path: Path, raw_dir: Path, material: str, match_reason: str, exact_names: set[str]) -> int:
    rel = path.relative_to(raw_dir)
    score = 0
    if match_reason == "exact_pdf_name":
        score += 1000
    elif match_reason == "inventory_tail":
        score += 500
    else:
        score += 100
    if len(rel.parts) == 1:
        score += 100
    else:
        score += max(0, 50 - 10 * (len(rel.parts) - 1))
    if path.name in exact_names:
        score += 200
    if re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{5}_", path.name):
        score += 25
    score += min(path.stat().st_size // 100000, 50)
    return score


def collect_candidates(raw_dir: Path, extracted_dir: Path) -> tuple[dict[tuple[str, str], list[PdfCandidate]], dict]:
    pdf_to_mpn, tail_to_mpn, mpn_to_pdf_names = build_extracted_indexes(extracted_dir)
    grouped: dict[tuple[str, str], list[PdfCandidate]] = defaultdict(list)
    debug = {
        "pdf_to_mpn_count": len(pdf_to_mpn),
        "tail_to_mpn_count": len(tail_to_mpn),
    }
    for path in _iter_pdf_files(raw_dir):
        material, reason = identify_material(path, pdf_to_mpn, tail_to_mpn)
        doc_kind = classify_doc_kind(path)
        score = score_candidate(path, raw_dir, material, reason, mpn_to_pdf_names.get(material, set()))
        grouped[(material, doc_kind)].append(PdfCandidate(path=path, material=material, doc_kind=doc_kind, score=score, reason=reason))
    return grouped, debug


def _candidate_sort_key(candidate: PdfCandidate) -> tuple[int, int, str]:
    return (-candidate.score, DOC_KIND_ORDER.get(candidate.doc_kind, 99), candidate.path.name)


def choose_canonical(grouped: dict[tuple[str, str], list[PdfCandidate]]) -> dict[tuple[str, str], dict]:
    plan = {}
    for key, candidates in grouped.items():
        ordered = sorted(candidates, key=_candidate_sort_key)
        plan[key] = {
            "canonical": ordered[0],
            "duplicates": ordered[1:],
        }
    return plan


def _unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    idx = 2
    while True:
        candidate = path.with_name(f"{stem}__{idx}{suffix}")
        if not candidate.exists():
            return candidate
        idx += 1


def _file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _move_file(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dst.resolve():
        return dst
    final_dst = _unique_destination(dst)
    shutil.move(str(src), str(final_dst))
    return final_dst


def apply_plan(raw_dir: Path, plan: dict[tuple[str, str], dict]) -> dict:
    duplicates_root = raw_dir / DUPLICATES_DIRNAME
    results = {
        "canonical": {},
        "duplicates": defaultdict(list),
        "discarded_identical": defaultdict(list),
    }
    for (material, doc_kind), entry in sorted(plan.items()):
        canonical: PdfCandidate = entry["canonical"]
        duplicates: list[PdfCandidate] = entry["duplicates"]

        target_name = canonical.path.name
        if canonical.path.parent != raw_dir:
            target_name = canonical.path.name if doc_kind == "datasheet" else f"{material}__{doc_kind}.pdf"
        canonical_target = raw_dir / target_name
        canonical_final = _move_file(canonical.path, canonical_target)
        canonical_md5 = _file_md5(canonical_final)
        results["canonical"].setdefault(material, {})[doc_kind] = {
            "path": str(canonical_final.relative_to(raw_dir)),
            "source_reason": canonical.reason,
            "score": canonical.score,
            "md5": canonical_md5,
        }

        for duplicate in duplicates:
            duplicate_md5 = _file_md5(duplicate.path)
            if duplicate_md5 == canonical_md5:
                duplicate.path.unlink()
                results["discarded_identical"][material].append(
                    {
                        "doc_kind": doc_kind,
                        "path": str(duplicate.path.relative_to(raw_dir)),
                        "source_reason": duplicate.reason,
                        "score": duplicate.score,
                        "md5": duplicate_md5,
                    }
                )
                continue

            dup_target = duplicates_root / material / duplicate.path.name
            final_dup = _move_file(duplicate.path, dup_target)
            results["duplicates"][material].append(
                {
                    "doc_kind": doc_kind,
                    "path": str(final_dup.relative_to(raw_dir)),
                    "source_reason": duplicate.reason,
                    "score": duplicate.score,
                    "md5": _file_md5(final_dup),
                }
            )
    results["duplicates"] = dict(results["duplicates"])
    results["discarded_identical"] = dict(results["discarded_identical"])
    return results


def _cleanup_empty_dirs(root: Path) -> None:
    for path in sorted((item for item in root.rglob('*') if item.is_dir()), key=lambda item: len(item.parts), reverse=True):
        if path == root:
            continue
        try:
            path.rmdir()
        except OSError:
            pass


def prune_duplicate_archive(raw_dir: Path, applied_results: dict) -> dict:
    duplicates_root = raw_dir / DUPLICATES_DIRNAME
    if not duplicates_root.exists():
        return {}

    canonical_md5 = {
        material: {entry['md5'] for entry in kinds.values()}
        for material, kinds in applied_results.get('canonical', {}).items()
    }
    pruned = defaultdict(list)
    for path in sorted(item for item in duplicates_root.rglob('*') if item.is_file() and item.suffix.lower() == '.pdf'):
        material = path.parent.name
        if material not in canonical_md5:
            continue
        md5 = _file_md5(path)
        if md5 in canonical_md5[material]:
            rel = str(path.relative_to(raw_dir))
            path.unlink()
            pruned[material].append(rel)

    for material_dir in sorted((item for item in duplicates_root.iterdir() if item.is_dir()), key=lambda item: item.name):
        seen_md5 = {}
        for path in sorted(item for item in material_dir.iterdir() if item.is_file() and item.suffix.lower() == '.pdf'):
            md5 = _file_md5(path)
            if md5 in seen_md5:
                rel = str(path.relative_to(raw_dir))
                path.unlink()
                pruned[material_dir.name].append(rel)
                continue
            seen_md5[md5] = path

    _cleanup_empty_dirs(duplicates_root)
    return dict(pruned)


def summarize_plan(raw_dir: Path, plan: dict[tuple[str, str], dict]) -> dict:
    summary = {
        "total_groups": len(plan),
        "groups_with_duplicates": 0,
        "materials_with_duplicates": [],
    }
    materials = set()
    for (material, _doc_kind), entry in plan.items():
        if entry["duplicates"]:
            summary["groups_with_duplicates"] += 1
            materials.add(material)
    summary["materials_with_duplicates"] = sorted(materials)
    return summary


def write_index(raw_dir: Path, index_payload: dict) -> Path:
    index_path = raw_dir / INDEX_NAME
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index_path


def run(raw_dir: Path, extracted_dir: Path, apply: bool) -> tuple[dict, Path]:
    grouped, debug = collect_candidates(raw_dir, extracted_dir)
    plan = choose_canonical(grouped)
    summary = summarize_plan(raw_dir, plan)
    payload = {
        "raw_dir": str(raw_dir),
        "extracted_dir": str(extracted_dir),
        "summary": summary,
        "debug": debug,
        "plan": {
            f"{material}::{doc_kind}": {
                "canonical": str(entry["canonical"].path.relative_to(raw_dir)),
                "duplicates": [str(item.path.relative_to(raw_dir)) for item in entry["duplicates"]],
            }
            for (material, doc_kind), entry in sorted(plan.items())
        },
    }
    if apply:
        payload["applied"] = apply_plan(raw_dir, plan)
        payload["pruned_archive_identical"] = prune_duplicate_archive(raw_dir, payload["applied"])
    index_path = write_index(raw_dir, payload)
    return payload, index_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--extracted-dir", type=Path, default=DEFAULT_EXTRACTED_DIR)
    parser.add_argument("--apply", action="store_true", help="Move files into canonical + duplicates layout.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload, index_path = run(args.raw_dir, args.extracted_dir, apply=args.apply)
    summary = payload["summary"]
    print(f"index={index_path}")
    print(f"total_groups={summary['total_groups']}")
    print(f"groups_with_duplicates={summary['groups_with_duplicates']}")
    if summary["materials_with_duplicates"]:
        print("materials_with_duplicates=" + ",".join(summary["materials_with_duplicates"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
