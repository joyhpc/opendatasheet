import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


def test_cxd4984_extracted_file_contains_protocol_domain():
    path = REPO_ROOT / "data" / "extracted_v2" / "CXD4984ER-W.json"
    with path.open(encoding="utf-8") as f:
        extracted = json.load(f)

    assert extracted["domains"]["protocol"]["protocol_summary"]["primary_interface"] == "MIPI"
    assert extracted["domains"]["protocol"]["protocol_summary"]["has_i2c"] is True
    assert extracted["domains"]["pin"]["pin_index"]["packages"]["VQFN-64"]["18"]["name"] == "SCL0"


def test_cxd4984_export_file_contains_protocol_domain_and_mipi_blocks():
    path = REPO_ROOT / "data" / "sch_review_export" / "CXD4984ER-W.json"
    with path.open(encoding="utf-8") as f:
        exported = json.load(f)

    assert exported["domains"]["protocol"]["protocol_summary"]["primary_interface"] == "MIPI"
    assert exported["capability_blocks"]["mipi_phy"]["dphy"]["max_rate_gbps_per_lane"] == 4.5
    assert exported["capability_blocks"]["mipi_phy"]["cphy"]["max_symbol_rate_gsps"] == 4.5
    assert exported["constraint_blocks"]["mipi_phy"]["phy_types"] == ["C-PHY", "D-PHY"]
