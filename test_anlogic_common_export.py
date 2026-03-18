import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from export_for_sch_review import export_fpga


PINOUT_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "pinout"
PACKAGE_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "anlogic_ph1a"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_common_export_uses_real_anlogic_pinout_data():
    pinout = _load(PINOUT_DIR / "ph1a90seg325_pinout.json")

    exported = export_fpga(
        {"extraction": {"component": {"manufacturer": "Anlogic", "description": "PH1A"}}},
        pinout,
    )

    assert exported["device_identity"]["vendor"] == "Anlogic"
    assert exported["device_identity"]["family"] == "SALPHOENIX 1A"
    assert exported["device_identity"]["base_device"] == "PH1A90"
    assert len(exported["pins"]) == 324
    assert exported["pins"][0]["pin"] == "A1"
    assert "synthetic" not in exported["pins"][0].get("attrs", {})
    assert exported["banks"]["31"]["bank"] == "31"
    assert exported["banks"]["31"]["io_pins"] > 0
    assert exported["constraint_blocks"]["refclk_requirements"].get("package_level_only") is not True
    assert exported["constraint_blocks"]["refclk_requirements"]["refclk_pairs"][0]["pair_name"] == "REFCLK_82"
    assert exported["constraint_blocks"]["source_consistency_review"]["review_required"] is True
    assert exported["source_conflicts"]


def test_common_export_supports_package_level_anlogic_records():
    package_record = _load(PACKAGE_DIR / "ph1a90seg325.json")

    exported = export_fpga(
        {"extraction": {"component": {"manufacturer": "Anlogic", "description": "PH1A"}}},
        package_record,
    )

    assert exported["device_identity"]["vendor"] == "Anlogic"
    assert exported["device_identity"]["base_device"] == "PH1A90"
    assert len(exported["pins"]) == 4
    assert exported["pins"][0]["attrs"]["synthetic"] is True
    assert exported["constraint_blocks"]["refclk_requirements"]["package_level_only"] is True
    assert exported["constraint_blocks"]["memory_interface_review"]["required"] is True
    assert exported["constraint_blocks"]["pcie_review"]["present"] is None
    assert exported["constraint_blocks"]["source_consistency_review"]["review_required"] is True
    assert exported["package_summary"]["user_io_count"] == 180
