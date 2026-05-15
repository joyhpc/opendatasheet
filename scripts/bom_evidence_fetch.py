#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download and lightly parse web evidence for BOM key materials.

This is deliberately evidence-first. It saves the source document/page, records
hashes and HTTP metadata, then extracts a small amount of text so later loops can
validate whether a file is a datasheet, app note, product page, or only a weak
fallback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


DEFAULT_TIMEOUT = 30
USER_AGENT = "opendatasheet-bom-evidence-fetch/1.0"


@dataclass(frozen=True)
class EvidenceTarget:
    mpn: str
    url: str
    source: str = ""
    status: str = ""
    note: str = ""
    relation: str = "seed"


def _sanitize(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._+-]+", "_", value.strip())
    return cleaned.strip("_") or "unknown"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extension_from_response(url: str, content_type: str) -> str:
    parsed_ext = Path(urlparse(url).path).suffix.lower()
    if "pdf" in content_type:
        return ".pdf"
    if "html" in content_type:
        return ".html"
    if "text/plain" in content_type:
        return ".txt"
    if parsed_ext in {".pdf", ".html", ".htm", ".txt"}:
        return parsed_ext
    return parsed_ext or ".bin"


def _doc_kind(path: Path, content_type: str, extracted_text: str) -> str:
    haystack = f"{path.name} {content_type} {extracted_text[:3000]}".lower()
    if "application note" in haystack or "app note" in haystack or re.search(r"\ban[-_ ]?\d+", haystack):
        return "app_note"
    if "user guide" in haystack or "user manual" in haystack or "reference manual" in haystack:
        return "user_guide"
    if "datasheet" in haystack or "data sheet" in haystack or path.suffix.lower() == ".pdf":
        return "datasheet"
    if "product" in haystack and path.suffix.lower() in {".html", ".htm"}:
        return "product_page"
    return "unknown"


def _extract_html_text(path: Path) -> tuple[str, list[str]]:
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    links = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()
        label = re.sub(r"\s+", " ", anchor.get_text(" ")).strip()
        if href:
            links.append(f"{label} {href}".strip())
    return text[:12000], links


def _extract_pdf_text(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""

    pages = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages[:3]:
                pages.append(page.extract_text() or "")
    except Exception:
        return ""
    return re.sub(r"\s+", " ", "\n".join(pages)).strip()[:12000]


def _extract_text(path: Path) -> tuple[str, list[str]]:
    if path.suffix.lower() in {".html", ".htm"}:
        return _extract_html_text(path)
    if path.suffix.lower() == ".pdf":
        return _extract_pdf_text(path), []
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:12000], []
    except Exception:
        return "", []


def _looks_like_doc_link(value: str) -> bool:
    lower = value.lower()
    return (
        ".pdf" in lower
        or "datasheet" in lower
        or "data sheet" in lower
        or "application note" in lower
        or "app note" in lower
        or "user guide" in lower
        or "reference manual" in lower
    )


def discover_document_links(base_url: str, links: list[str]) -> list[str]:
    urls = []
    for link in links:
        if not _looks_like_doc_link(link):
            continue
        match = re.search(r"(https?://\S+|/[^\s]+)", link)
        if not match:
            continue
        href = match.group(1).rstrip(").,;\"'")
        urls.append(urljoin(base_url, href))

    deduped = []
    seen = set()
    for url in urls:
        if url not in seen:
            deduped.append(url)
            seen.add(url)
    return deduped[:5]


def load_targets(seed_path: Path) -> list[EvidenceTarget]:
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    targets = []
    for item in payload.get("evidence", []):
        if not item.get("mpn") or not item.get("url"):
            continue
        targets.append(
            EvidenceTarget(
                mpn=item["mpn"],
                url=item["url"],
                source=item.get("source", ""),
                status=item.get("status", ""),
                note=item.get("note", ""),
            )
        )
    return targets


def download_target(session: requests.Session, target: EvidenceTarget, output_dir: Path, index: int) -> dict:
    material_dir = output_dir / _sanitize(target.mpn)
    material_dir.mkdir(parents=True, exist_ok=True)

    response = session.get(target.url, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
    content_type = response.headers.get("content-type", "").split(";")[0].lower()
    ext = _extension_from_response(str(response.url), content_type)
    filename = f"{index:03d}_{target.relation}_{_sanitize(target.source or 'source')}{ext}"
    path = material_dir / filename
    path.write_bytes(response.content)

    extracted_text, links = _extract_text(path)
    discovered_links = discover_document_links(str(response.url), links) if path.suffix.lower() in {".html", ".htm"} else []
    entry = {
        "mpn": target.mpn,
        "relation": target.relation,
        "source": target.source,
        "seed_status": target.status,
        "note": target.note,
        "url": target.url,
        "final_url": str(response.url),
        "http_status": response.status_code,
        "content_type": content_type,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "doc_kind": _doc_kind(path, content_type, extracted_text),
        "text_preview": extracted_text[:800],
        "discovered_document_links": discovered_links,
    }
    return entry


def fetch_evidence(seed_path: Path, output_dir: Path, *, download_discovered: bool = True) -> dict:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    entries = []
    queue = load_targets(seed_path)
    seen_urls = {target.url for target in queue}
    index = 1

    while queue:
        target = queue.pop(0)
        try:
            entry = download_target(session, target, output_dir, index)
            entries.append(entry)
            index += 1
        except Exception as exc:
            entries.append(
                {
                    "mpn": target.mpn,
                    "relation": target.relation,
                    "source": target.source,
                    "seed_status": target.status,
                    "note": target.note,
                    "url": target.url,
                    "error": f"{type(exc).__name__}: {exc}",
                    "doc_kind": "download_failed",
                }
            )
            continue

        if download_discovered:
            for url in entry.get("discovered_document_links", []):
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                queue.append(
                    EvidenceTarget(
                        mpn=target.mpn,
                        url=url,
                        source="discovered_document",
                        status=target.status,
                        note=f"Discovered from {target.url}",
                        relation="discovered",
                    )
                )

    summary = {
        "target_count": len(load_targets(seed_path)),
        "download_count": sum(1 for entry in entries if "path" in entry),
        "failure_count": sum(1 for entry in entries if entry.get("doc_kind") == "download_failed"),
        "by_doc_kind": {},
    }
    for entry in entries:
        kind = entry.get("doc_kind", "unknown")
        summary["by_doc_kind"][kind] = summary["by_doc_kind"].get(kind, 0) + 1

    return {
        "_schema": "bom-evidence-download-manifest/1.0",
        "seed_path": str(seed_path),
        "output_dir": str(output_dir),
        "summary": summary,
        "entries": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed", type=Path, help="Evidence seed JSON")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for downloaded evidence files")
    parser.add_argument("--manifest", type=Path, required=True, help="Manifest JSON path")
    parser.add_argument("--no-discover", action="store_true", help="Do not download PDF/doc links discovered in HTML pages")
    args = parser.parse_args(argv)

    manifest = fetch_evidence(args.seed, args.output_dir, download_discovered=not args.no_discover)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
    return 0 if manifest["summary"]["download_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
