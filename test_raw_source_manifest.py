import json
from pathlib import Path

from scripts.build_raw_source_manifest import build_manifest


def test_build_raw_source_manifest_classifies_tiers_and_doc_types(tmp_path):
    raw_root = tmp_path / "raw"
    (raw_root / "datasheet_PDF").mkdir(parents=True)
    (raw_root / "datasheet_PDF" / "_duplicates" / "TPS62147").mkdir(parents=True)
    (raw_root / "fpga" / "gowin").mkdir(parents=True)
    (raw_root / "_staging").mkdir(parents=True)

    (raw_root / "datasheet_PDF" / "0130-01-00037_TPS62148RGXR.pdf").write_bytes(b"pdf-a")
    (raw_root / "datasheet_PDF" / "_duplicates" / "TPS62147" / "old_TPS62148RGXR.pdf").write_bytes(b"pdf-b")
    (raw_root / "fpga" / "gowin" / "UG1110-1.0.4_GW5AR-25器件Pinout手册.xlsx").write_bytes(b"xlsx-a")
    (raw_root / "_staging" / "UG9999-0.1_GW2A-18器件Pinout手册.xlsx").write_bytes(b"xlsx-b")

    manifest = build_manifest(raw_root)
    entries = {item["path"]: item for item in manifest["entries"]}

    assert manifest["entry_count"] == 4
    assert manifest["summary"]["by_storage_tier"] == {"canonical": 2, "duplicate": 1, "staging": 1}

    assert entries["datasheet_PDF/0130-01-00037_TPS62148RGXR.pdf"]["doc_type"] == "datasheet"
    assert entries["datasheet_PDF/0130-01-00037_TPS62148RGXR.pdf"]["storage_tier"] == "canonical"
    assert entries["datasheet_PDF/_duplicates/TPS62147/old_TPS62148RGXR.pdf"]["storage_tier"] == "duplicate"
    assert entries["fpga/gowin/UG1110-1.0.4_GW5AR-25器件Pinout手册.xlsx"]["doc_type"] == "pinout"
    assert entries["fpga/gowin/UG1110-1.0.4_GW5AR-25器件Pinout手册.xlsx"]["family_hint"] == "GW5AR-25"
    assert entries["_staging/UG9999-0.1_GW2A-18器件Pinout手册.xlsx"]["storage_tier"] == "staging"
    assert entries["_staging/UG9999-0.1_GW2A-18器件Pinout手册.xlsx"]["family_hint"] == "GW2A-18"


def test_build_raw_source_manifest_is_json_stable(tmp_path):
    raw_root = tmp_path / "raw"
    (raw_root / "fpga").mkdir(parents=True)
    source = raw_root / "fpga" / "UG983-1.2.8_GW5AT系列FPGA产品封装与管脚手册.pdf"
    source.write_bytes(b"package-guide")

    manifest = build_manifest(raw_root)
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False)

    assert '"policy_version": "1.0"' in rendered
    assert '"doc_type": "package_guide"' in rendered
    assert '"format": "pdf"' in rendered
