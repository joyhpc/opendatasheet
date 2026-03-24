import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


def _load_json(path: Path) -> dict:
    with path.open() as fp:
        return json.load(fp)


def test_automotive_video_serdes_exports_share_common_category_and_capability_block():
    cxd = _load_json(REPO_ROOT / "data" / "sch_review_export" / "CXD4984ER-W.json")
    max96718 = _load_json(REPO_ROOT / "data" / "sch_review_export" / "MAX96718A.json")

    for payload in (cxd, max96718):
        assert payload["category"] == "Automotive Video SerDes"
        assert payload["capability_blocks"]["serial_video_bridge"]["device_role"] == "deserializer"
        assert payload["capability_blocks"]["serial_video_bridge"]["application_domain"] == "automotive_camera"
        assert payload["constraint_blocks"]["serial_video_bridge"]["review_required"] is True

    assert cxd["capability_blocks"]["serial_video_bridge"]["link_families"] == ["GVIF3"]
    assert max96718["capability_blocks"]["serial_video_bridge"]["link_families"] == ["GMSL2", "GMSL1"]


def test_automotive_video_serdes_selection_profiles_expose_normalized_tags():
    cxd = _load_json(REPO_ROOT / "data" / "selection_profile" / "CXD4984ER-W.json")
    max96718 = _load_json(REPO_ROOT / "data" / "selection_profile" / "MAX96718A.json")

    for payload in (cxd, max96718):
        assert payload["category"] == "Automotive Video SerDes"
        assert "function:automotive_video_serdes" in payload["features"]
        assert "role:deserializer" in payload["features"]

    assert "link_family:gvif3" in cxd["features"]
    assert "link_family:gmsl2" in max96718["features"]


def test_automotive_video_serdes_extracted_payloads_are_recategorized():
    cxd = _load_json(REPO_ROOT / "data" / "extracted_v2" / "CXD4984ER-W.json")
    max96718 = _load_json(REPO_ROOT / "data" / "extracted_v2" / "MAX96718.json")

    assert cxd["extraction"]["component"]["category"] == "Automotive Video SerDes"
    assert max96718["extraction"]["component"]["category"] == "Automotive Video SerDes"
    assert max96718["domains"]["protocol"]["protocol_summary"]["primary_interface"] == "MIPI"


def test_automotive_video_serdes_registry_tracks_pending_ds90ub_family_members():
    registry = _load_json(REPO_ROOT / "data" / "normalization" / "automotive_video_serdes_profiles.json")

    for mpn in (
        "DS90UB934TRGZRQ1",
        "DS90UB954TRGZRQ1",
        "DS90UB960WRTDRQ1",
        "DS90UB962WRTDTQ1",
        "DS90UB9702-Q1",
    ):
        entry = registry["devices"][mpn]
        assert entry["status"] == "pending_source_reintake"
        assert entry["category"] == "Automotive Video SerDes"
        assert entry["serial_video_bridge"]["device_role"] == "deserializer"
