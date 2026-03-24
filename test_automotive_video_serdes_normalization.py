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
        assert payload["capability_blocks"]["serial_video_bridge"]["system_path"] == "camera_module_to_domain_controller"
        assert payload["constraint_blocks"]["serial_video_bridge"]["system_path"] == "camera_module_to_domain_controller"
        assert payload["constraint_blocks"]["serial_video_bridge"]["review_required"] is True

    assert cxd["capability_blocks"]["serial_video_bridge"]["link_families"] == ["GVIF3"]
    assert max96718["capability_blocks"]["serial_video_bridge"]["link_families"] == ["GMSL2", "GMSL1"]


def test_hsmt_serializer_and_deserializer_are_normalized_as_distinct_roles():
    ns6012 = _load_json(REPO_ROOT / "data" / "sch_review_export" / "NS6012.json")
    ns6603 = _load_json(REPO_ROOT / "data" / "sch_review_export" / "NS6603.json")

    serializer = ns6012["capability_blocks"]["serial_video_bridge"]
    assert serializer["device_role"] == "serializer"
    assert serializer["system_path"] == "camera_module_to_domain_controller"
    assert serializer["link_families"] == ["HSMT"]
    assert serializer["link_direction"] == "video_in_to_serial_out"
    assert serializer["video_input"]["protocol"] == "MIPI CSI-2"
    assert serializer["video_input"]["phy_types"] == ["D-PHY"]
    assert ns6012["capability_blocks"]["mipi_phy"]["directions"] == ["RX"]

    deserializer = ns6603["capability_blocks"]["serial_video_bridge"]
    assert deserializer["device_role"] == "deserializer"
    assert deserializer["system_path"] == "camera_module_to_domain_controller"
    assert deserializer["link_families"] == ["HSMT"]
    assert deserializer["link_direction"] == "serial_in_to_video_out"
    assert deserializer["video_output"]["protocol"] == "MIPI CSI-2"
    assert deserializer["video_output"]["phy_types"] == ["D-PHY", "C-PHY"]
    assert ns6603["capability_blocks"]["mipi_phy"]["directions"] == ["TX"]


def test_automotive_video_serdes_selection_profiles_expose_normalized_tags():
    cxd = _load_json(REPO_ROOT / "data" / "selection_profile" / "CXD4984ER-W.json")
    max96718 = _load_json(REPO_ROOT / "data" / "selection_profile" / "MAX96718A.json")

    for payload in (cxd, max96718):
        assert payload["category"] == "Automotive Video SerDes"
        assert "function:automotive_video_serdes" in payload["features"]
        assert "role:deserializer" in payload["features"]
        assert "system_path:camera_module_to_domain_controller" in payload["features"]

    assert "link_family:gvif3" in cxd["features"]
    assert "link_family:gmsl2" in max96718["features"]


def test_hsmt_selection_profiles_expose_serializer_and_deserializer_tags():
    ns6012 = _load_json(REPO_ROOT / "data" / "selection_profile" / "NS6012.json")
    ns6603 = _load_json(REPO_ROOT / "data" / "selection_profile" / "NS6603.json")

    assert "role:serializer" in ns6012["features"]
    assert "system_path:camera_module_to_domain_controller" in ns6012["features"]
    assert "link_family:hsmt" in ns6012["features"]
    assert "video_input:mipi_csi-2" in ns6012["features"]

    assert "role:deserializer" in ns6603["features"]
    assert "system_path:camera_module_to_domain_controller" in ns6603["features"]
    assert "link_family:hsmt" in ns6603["features"]
    assert "video_output:mipi_csi-2" in ns6603["features"]


def test_automotive_video_serdes_extracted_payloads_are_recategorized():
    cxd = _load_json(REPO_ROOT / "data" / "extracted_v2" / "CXD4984ER-W.json")
    max96718 = _load_json(REPO_ROOT / "data" / "extracted_v2" / "MAX96718.json")

    assert cxd["extraction"]["component"]["category"] == "Automotive Video SerDes"
    assert max96718["extraction"]["component"]["category"] == "Automotive Video SerDes"
    assert max96718["domains"]["protocol"]["protocol_summary"]["primary_interface"] == "MIPI"


def test_hsmt_extracted_payloads_are_recategorized_and_protocol_enriched():
    ns6012 = _load_json(REPO_ROOT / "data" / "extracted_v2" / "NS6012.json")
    ns6603 = _load_json(REPO_ROOT / "data" / "extracted_v2" / "NS6603.json")

    assert ns6012["extraction"]["component"]["category"] == "Automotive Video SerDes"
    assert ns6012["domains"]["protocol"]["protocol_summary"]["has_i2c"] is True
    assert ns6012["domains"]["protocol"]["protocol_summary"]["has_spi"] is True
    assert ns6603["extraction"]["component"]["category"] == "Automotive Video SerDes"
    assert ns6603["domains"]["protocol"]["protocol_summary"]["has_uart"] is True


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
        assert entry["serial_video_bridge"]["system_path"] == "camera_module_to_domain_controller"


def test_automotive_video_serdes_registry_includes_source_backed_hsmt_profiles():
    registry = _load_json(REPO_ROOT / "data" / "normalization" / "automotive_video_serdes_profiles.json")

    ns6012 = registry["devices"]["NS6012"]
    assert ns6012["status"] == "active"
    assert ns6012["serial_video_bridge"]["device_role"] == "serializer"
    assert ns6012["serial_video_bridge"]["link_families"] == ["HSMT"]

    ns6603 = registry["devices"]["NS6603"]
    assert ns6603["status"] == "active"
    assert ns6603["category"] == "Automotive Video SerDes"
    assert ns6603["serial_video_bridge"]["device_role"] == "deserializer"
    assert ns6603["serial_video_bridge"]["link_families"] == ["HSMT"]
    assert ns6603["serial_video_bridge"]["source_basis"] == "primary_pdf_manual_profile"
