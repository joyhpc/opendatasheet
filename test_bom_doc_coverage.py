from pathlib import Path

from scripts.bom_doc_coverage import build_doc_coverage


def test_doc_coverage_matches_aliases_and_local_sources(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    key_report = {
        "source": {"path": "bom.BOM"},
        "key_materials": [
            {
                "line_number": 1,
                "mpn": "TPS56637RPAR",
                "manufacturer": "TI",
                "risk_tags": ["power"],
            },
            {
                "line_number": 2,
                "mpn": "A5EC052A B32A",
                "manufacturer": "Intel",
                "risk_tags": ["integrated_circuit"],
            },
        ],
    }
    entries = [
        {
            "mpn": "TPS56637",
            "seed_status": "official_found",
            "doc_kind": "datasheet",
            "path": str(tmp_path / "tps56637.pdf"),
            "text_preview": "TPS56637 data sheet",
        }
    ]
    (tmp_path / "tps56637.pdf").write_bytes(b"%PDF")

    repo_root = tmp_path / "repo"
    local = repo_root / "data" / "sch_review_export" / "A5EC052A_B32A.json"
    local.parent.mkdir(parents=True)
    local.write_text("{}", encoding="utf-8")

    def fake_load(_paths):
        return entries

    import scripts.bom_doc_coverage as module

    original = module.load_manifest_entries
    try:
        module.load_manifest_entries = fake_load
        coverage = build_doc_coverage(key_report, [manifest], repo_root)
    finally:
        module.load_manifest_entries = original

    statuses = {row["mpn"]: row["coverage_status"] for row in coverage["coverage"]}

    assert statuses["TPS56637RPAR"] == "official_datasheet_downloaded"
    assert statuses["A5EC052A B32A"] == "local_source_backed"


def test_doc_coverage_does_not_downgrade_exact_memory_variant(tmp_path):
    key_report = {
        "source": {"path": "bom.BOM"},
        "key_materials": [
            {
                "line_number": 210,
                "mpn": "K3KL8L80QM-MGCT",
                "manufacturer": "Samsung",
                "risk_tags": ["integrated_circuit"],
            },
            {
                "line_number": 221,
                "mpn": "W25Q256JWEIQ",
                "manufacturer": "Winbond",
                "risk_tags": ["integrated_circuit"],
            },
        ],
    }
    entries = [
        {
            "mpn": "K3KL8L80QM-MFCT",
            "seed_status": "official_found",
            "doc_kind": "product_page",
            "path": str(tmp_path / "k3kl8l80qm-mfct.html"),
            "text_preview": "K3KL8L80QM-MFCT product page",
        },
        {
            "mpn": "W25Q256JW",
            "seed_status": "official_found",
            "doc_kind": "datasheet",
            "path": str(tmp_path / "w25q256jw.pdf"),
            "text_preview": "W25Q256JW data sheet",
        },
    ]

    def fake_load(_paths):
        return entries

    import scripts.bom_doc_coverage as module

    original = module.load_manifest_entries
    try:
        module.load_manifest_entries = fake_load
        coverage = build_doc_coverage(key_report, [tmp_path / "manifest.json"], tmp_path)
    finally:
        module.load_manifest_entries = original

    statuses = {row["mpn"]: row["coverage_status"] for row in coverage["coverage"]}

    assert statuses["K3KL8L80QM-MGCT"] == "missing"
    assert statuses["W25Q256JWEIQ"] == "official_datasheet_downloaded"


def test_doc_coverage_tracks_local_design_and_private_component_notes(tmp_path):
    key_report = {
        "source": {"path": "bom.BOM"},
        "key_materials": [
            {
                "line_number": 210,
                "mpn": "K3KL8L80QM-MGCT",
                "manufacturer": "Samsung",
                "risk_tags": ["integrated_circuit"],
            },
            {
                "line_number": 220,
                "mpn": "PC800",
                "manufacturer": "DO3THINK",
                "risk_tags": ["integrated_circuit"],
            },
        ],
    }
    entries = [
        {
            "mpn": "K3KL8L80QM-MGCT",
            "seed_status": "local_design_evidence",
            "doc_kind": "local_design_evidence",
            "path": str(tmp_path / "k3.json"),
            "text_preview": "K3 exact local Allegro primitive",
        },
        {
            "mpn": "PC800",
            "seed_status": "private_vendor_declared",
            "doc_kind": "private_component_note",
            "path": str(tmp_path / "private.json"),
            "text_preview": "PC800 private registration I2C EEPROM",
        },
    ]

    def fake_load(_paths):
        return entries

    import scripts.bom_doc_coverage as module

    original = module.load_manifest_entries
    try:
        module.load_manifest_entries = fake_load
        coverage = build_doc_coverage(key_report, [tmp_path / "manifest.json"], tmp_path)
    finally:
        module.load_manifest_entries = original

    rows = {row["mpn"]: row for row in coverage["coverage"]}

    assert rows["K3KL8L80QM-MGCT"]["coverage_status"] == "local_design_evidence"
    assert rows["K3KL8L80QM-MGCT"]["local_design_evidence_count"] == 1
    assert rows["PC800"]["coverage_status"] == "private_component_declared"
    assert rows["PC800"]["private_note_count"] == 1
