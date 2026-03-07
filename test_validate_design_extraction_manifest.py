import json
from pathlib import Path

from scripts.build_raw_source_manifest import build_manifest
from scripts.validate_design_extraction import validate_raw_source_manifest


def test_validate_raw_source_manifest_accepts_existing_manifest(tmp_path):
    raw_root = tmp_path / "raw"
    (raw_root / "datasheet_PDF").mkdir(parents=True)
    (raw_root / "datasheet_PDF" / "0130-01-00037_TPS62148RGXR.pdf").write_bytes(b"pdf-a")

    manifest_path = raw_root / "_source_manifest.json"
    manifest_path.write_text(json.dumps(build_manifest(raw_root), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    assert not validate_raw_source_manifest(raw_root)
    assert not validate_raw_source_manifest(raw_root, strict=True)


def test_validate_raw_source_manifest_reports_missing_or_stale_manifest(tmp_path):
    raw_root = tmp_path / "raw"
    (raw_root / "datasheet_PDF").mkdir(parents=True)
    pdf = raw_root / "datasheet_PDF" / "0130-01-00037_TPS62148RGXR.pdf"
    pdf.write_bytes(b"pdf-a")

    missing = validate_raw_source_manifest(raw_root)
    assert missing and "missing" in missing[0]

    manifest_path = raw_root / "_source_manifest.json"
    manifest_path.write_text(json.dumps(build_manifest(raw_root), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    pdf.write_bytes(b"pdf-b")

    assert not validate_raw_source_manifest(raw_root, strict=False)
    stale = validate_raw_source_manifest(raw_root, strict=True)
    assert stale and "stale" in stale[0]
