from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "fpga" / "intel_agilex5"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build_raw_source_manifest import build_manifest
from export_for_sch_review import export_fpga
from parse_intel_pinout import parse_intel_xlsx


def _package(results: list[dict], package: str) -> dict:
    return next(item for item in results if item["package"] == package)


def test_parse_intel_agilex5_a5ec013b_packages():
    results = parse_intel_xlsx(RAW_DIR / "a5ec013b.xlsx")
    packages = {item["package"] for item in results}

    assert packages == {"B23A", "B32A", "M16A"}

    b23a = _package(results, "B23A")
    assert b23a["_vendor"] == "Intel/Altera"
    assert b23a["_family"] == "Agilex 5"
    assert b23a["device"] == "A5EC013B"
    assert b23a["source_document_id"] == "819287"
    assert b23a["source_version"] == "2025-06-13"
    assert b23a["source_status"] == "Final"
    assert b23a["summary"]["by_function"]["IO"] > 0
    assert b23a["summary"]["by_function"]["CONFIG"] >= 10
    assert any(pin["name"] == "REFCLK_GTSL1A_CH1p" for pin in b23a["pins"])
    assert any(pair["type"] == "SERDES_REFCLK" for pair in b23a["diff_pairs"])


def test_parse_intel_agilex5_a5ed052a_exposes_hps_io():
    results = parse_intel_xlsx(RAW_DIR / "a5ed052a.xlsx")
    b23a = _package(results, "B23A")

    assert b23a["device"] == "A5ED052A"
    assert b23a["source_version"] == "2025-06-06"
    assert b23a["summary"]["by_function"]["HPS_IO"] == 144
    assert b23a["ordering_variant"]["device_role"] == "FPGA SoC"
    assert b23a["banks"]["HPS"]["hps_io_pins"] == 48
    assert b23a["banks"]["3A_B"]["hps_io_pins"] == 48
    assert b23a["banks"]["3A_T"]["hps_io_pins"] == 48


def test_export_fpga_merges_intel_agilex5_overlay():
    results = parse_intel_xlsx(RAW_DIR / "a5ed013b.xlsx")
    b23a = _package(results, "B23A")

    exported = export_fpga({"extraction": {"component": {}}}, b23a)

    assert exported["manufacturer"] == "Intel/Altera"
    assert exported["device_role"] == "FPGA SoC"
    assert exported["device_identity"]["family"] == "Agilex 5"
    assert exported["device_identity"]["base_device"] == "A5E013B"
    assert exported["device_identity"]["package"] == "B23A"
    assert exported["ordering_variant"]["variant_code"] == "D"
    assert exported["source_traceability"]["package_pinout"]["source_document_id"] == "819288"
    assert exported["source_traceability"]["device_capability"]["source"] == "agilex5_device_overview_762191_2024_09_06"
    assert exported["capability_blocks"]["device_role"]["device_role"] == "FPGA SoC"
    assert exported["capability_blocks"]["fabric_resources"]["logic_elements"] == 138060
    assert exported["capability_blocks"]["memory_interface"]["supported_standards"] == ["DDR4", "LPDDR4", "LPDDR5"]
    assert exported["capability_blocks"]["high_speed_serial"]["max_rate_gbps"] == 17.16
    assert exported["capability_blocks"]["high_speed_serial"]["pcie4_x4_instance_count"] == 1
    assert exported["capability_blocks"]["hard_processor"]["mode"] == "quad"


def test_build_raw_source_manifest_detects_agilex5_family(tmp_path):
    raw_root = tmp_path / "raw"
    (raw_root / "fpga" / "intel").mkdir(parents=True)
    source = raw_root / "fpga" / "intel" / "a5ed013b.xlsx"
    source.write_bytes(b"xlsx")

    manifest = build_manifest(raw_root)
    entry = manifest["entries"][0]

    assert entry["vendor_hint"] == "Intel/Altera"
    assert entry["family_hint"] == "A5ED013B"
