#!/usr/bin/env python3
"""Check local relative links inside Markdown files.

- Scans repository Markdown files by default
- Ignores http(s), mailto, and other URL-like schemes
- Treats `#anchor` links as local-to-file and therefore valid
- For `path#anchor`, only checks that `path` exists
- Skips fenced code blocks to avoid false positives from examples
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKDOWN_GLOB = "*.md"
FENCE_RE = re.compile(r"^(```|~~~)")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def iter_markdown_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob(MARKDOWN_GLOB)):
        if any(part in {".git", ".venv", "node_modules"} for part in path.parts):
            continue
        if path.is_file():
            yield path


def strip_optional_title(raw_target: str) -> str:
    target = raw_target.strip()
    if not target:
        return target
    if target.startswith("<") and target.endswith(">"):
        return target[1:-1].strip()
    return target.split()[0]


def is_external(target: str) -> bool:
    return bool(SCHEME_RE.match(target)) or target.startswith("//")


def should_skip(target: str) -> bool:
    return not target or is_external(target)


def normalize_target(target: str) -> tuple[str, str]:
    if "#" in target:
        path_part, fragment = target.split("#", 1)
        return path_part.strip(), fragment.strip()
    return target.strip(), ""


def collect_links(markdown_path: Path) -> list[tuple[int, str]]:
    links: list[tuple[int, str]] = []
    in_fence = False
    for lineno, line in enumerate(markdown_path.read_text(encoding="utf-8").splitlines(), start=1):
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in LINK_RE.finditer(line):
            links.append((lineno, strip_optional_title(match.group(1))))
    return links


def check_markdown_file(markdown_path: Path) -> list[str]:
    errors: list[str] = []
    for lineno, target in collect_links(markdown_path):
        if should_skip(target):
            continue
        path_part, _fragment = normalize_target(target)
        if not path_part:
            continue
        resolved = (markdown_path.parent / path_part).resolve()
        if not resolved.exists():
            rel_source = markdown_path.resolve().relative_to(REPO_ROOT)
            errors.append(f"{rel_source}:{lineno} -> missing target: {target}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local relative links in Markdown files")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional Markdown files or directories to scan (defaults to repository root)",
    )
    args = parser.parse_args()

    scan_roots = [REPO_ROOT] if not args.paths else [Path(p).resolve() for p in args.paths]
    markdown_files: list[Path] = []
    for root in scan_roots:
        if root.is_file() and root.suffix.lower() == ".md":
            markdown_files.append(root)
        elif root.is_dir():
            markdown_files.extend(iter_markdown_files(root))
        else:
            print(f"WARN: skipping unsupported path {root}")

    seen: set[Path] = set()
    unique_files = []
    for path in markdown_files:
        if path not in seen:
            unique_files.append(path)
            seen.add(path)

    all_errors: list[str] = []
    for markdown_file in unique_files:
        all_errors.extend(check_markdown_file(markdown_file))

    if all_errors:
        print("Markdown link check failed:\n")
        for err in all_errors:
            print(f"- {err}")
        print(f"\nChecked {len(unique_files)} Markdown files, found {len(all_errors)} broken local link(s).")
        return 1

    print(f"Markdown link check passed: {len(unique_files)} Markdown files, 0 broken local links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
