import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "fpga" / "intel_agilex5"
EXPORT_DIR = REPO_ROOT / "data" / "sch_review_export"
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
    assert exported["supply_specs"]["VCCIO_SDM"]["typ"] == 1.8
    assert exported["supply_specs"]["VCC_HSSI_5S"]["typ"] == 0.78
    assert exported["absolute_maximum_ratings"]["abs_VCCIO_HVIO_3V3"]["max"] == 3.74
    assert exported["io_standard_specs"]["hsio_lvcmos_1v2"]["vccio_typ"] == 1.2

    constraints = exported["constraint_blocks"]
    assert set(constraints["configuration_boot"]["jtag_signals"]) == {"TCK", "TDI", "TDO", "TMS"}
    assert constraints["configuration_boot"]["external_configuration_clock"]["allowed_frequencies_mhz"] == [25, 100, 125]
    assert constraints["power_integrity"]["ramp_requirements"]["strictly_monotonic"] is True
    assert constraints["power_integrity"]["smartvid"]["pmbus_regulator_required"] is True
    assert constraints["io_bank_voltage_selection"]["bank_voltage_options"]["HSIO"]["supported_v"] == [1.0, 1.05, 1.1, 1.2, 1.3]
    assert constraints["gts_transceiver_power_integrity"]["rails"]["VCCEHT_GTS[L1,R4][A,B,C]"]["hf_noise_limit_mVpp_above_1MHz"] == 30
    assert constraints["hps_power_integrity"]["io_rails"] == ["VCCIO_HPS"]
    assert "refclk_requirements" in constraints
    assert "agilex5_configuration_clock" in exported["drc_rules"]
    assert exported["source_traceability"]["device_datasheet"]["source_document_id"] == "813918"


def test_checked_in_intel_agilex5_export_exposes_datasheet_backed_review_blocks():
    with open(EXPORT_DIR / "A5ED013B_B23A.json", encoding="utf-8") as fp:
        exported = json.load(fp)

    assert exported["supply_specs"]["VCCPT"]["typ"] == 1.8
    assert exported["absolute_maximum_ratings"]["abs_TJ"]["max"] == 125
    assert exported["io_standard_specs"]["hvio_lvcmos_lvttl_3v3"]["vccio_max"] == 3.399
    assert exported["constraint_blocks"]["configuration_boot"]["por_delay_ms"]["AS fast mode"]["max"] == 7.6
    assert exported["constraint_blocks"]["pin_connection_guidelines_review"]["review_required"] is True


def test_build_raw_source_manifest_detects_agilex5_family(tmp_path):
    raw_root = tmp_path / "raw"
    (raw_root / "fpga" / "intel").mkdir(parents=True)
    source = raw_root / "fpga" / "intel" / "a5ed013b.xlsx"
    source.write_bytes(b"xlsx")

    manifest = build_manifest(raw_root)
    entry = manifest["entries"][0]

    assert entry["vendor_hint"] == "Intel/Altera"
    assert entry["family_hint"] == "A5ED013B"
