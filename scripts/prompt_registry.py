#!/usr/bin/env python3
"""Prompt registry smoke gate for model-backed extractors."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


PROMPT_ID_PREFIX = "opendatasheet."
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class PromptRegistryEntry:
    prompt_id: str
    prompt_version: str
    owner_module: str
    prompt_attr: str
    prompt_sha256: str
    prompt_length: int


PROMPT_SPECS = (
    ("extractors.electrical", "PROMPT_ID", "PROMPT_VERSION", "VISION_PROMPT"),
    ("extractors.pin", "PIN_PROMPT_ID", "PIN_PROMPT_VERSION", "PIN_EXTRACTION_PROMPT"),
    ("extractors.pin", "FPGA_PIN_PROMPT_ID", "FPGA_PIN_PROMPT_VERSION", "FPGA_PIN_EXTRACTION_PROMPT"),
    ("extractors.package", "PROMPT_ID", "PROMPT_VERSION", "PACKAGE_EXTRACTION_PROMPT"),
    ("extractors.register", "PROMPT_ID", "PROMPT_VERSION", "REGISTER_EXTRACTION_PROMPT"),
    ("extractors.timing", "PROMPT_ID", "PROMPT_VERSION", "TIMING_EXTRACTION_PROMPT"),
    ("extractors.power_sequence", "PROMPT_ID", "PROMPT_VERSION", "POWER_SEQUENCE_EXTRACTION_PROMPT"),
    ("extractors.protocol", "PROMPT_ID", "PROMPT_VERSION", "PROTOCOL_EXTRACTION_PROMPT"),
    ("extractors.design_guide", "PROMPT_ID", "PROMPT_VERSION", "DESIGN_GUIDE_EXTRACTION_PROMPT"),
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iter_prompt_registry() -> list[PromptRegistryEntry]:
    entries = []
    for module_name, id_attr, version_attr, prompt_attr in PROMPT_SPECS:
        module = importlib.import_module(module_name)
        prompt_id = getattr(module, id_attr)
        prompt_version = getattr(module, version_attr)
        prompt = getattr(module, prompt_attr)
        entries.append(
            PromptRegistryEntry(
                prompt_id=prompt_id,
                prompt_version=prompt_version,
                owner_module=module_name,
                prompt_attr=prompt_attr,
                prompt_sha256=_sha256_text(prompt),
                prompt_length=len(prompt),
            )
        )
    return entries


def validate_prompt_registry(entries: list[PromptRegistryEntry] | None = None) -> list[str]:
    entries = entries or iter_prompt_registry()
    errors = []
    seen_ids = set()

    for entry in entries:
        if not entry.prompt_id.startswith(PROMPT_ID_PREFIX):
            errors.append(f"{entry.owner_module}.{entry.prompt_attr}: prompt_id must start with {PROMPT_ID_PREFIX}")
        if entry.prompt_id in seen_ids:
            errors.append(f"{entry.prompt_id}: duplicate prompt_id")
        seen_ids.add(entry.prompt_id)
        if not SEMVER_RE.match(entry.prompt_version):
            errors.append(f"{entry.prompt_id}: prompt_version must be semver-like")
        if entry.prompt_length < 100:
            errors.append(f"{entry.prompt_id}: prompt is unexpectedly short")
        if not re.fullmatch(r"[0-9a-f]{64}", entry.prompt_sha256):
            errors.append(f"{entry.prompt_id}: prompt_sha256 is invalid")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print registry entries as JSON")
    args = parser.parse_args()

    entries = iter_prompt_registry()
    errors = validate_prompt_registry(entries)
    if args.json:
        print(json.dumps([asdict(entry) for entry in entries], indent=2, ensure_ascii=False))
    else:
        print(f"registered_prompts={len(entries)}")
        for entry in entries:
            print(
                f"- {entry.prompt_id} v{entry.prompt_version} "
                f"{entry.owner_module}.{entry.prompt_attr} sha256={entry.prompt_sha256[:12]}"
            )

    if errors:
        print("prompt_registry_errors", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
