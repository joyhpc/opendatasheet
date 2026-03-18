import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from parse_anlogic_ph1a_pinout import _parse_workbook


RAW_PINLIST_DIR = REPO_ROOT / "data" / "raw" / "fpga" / "anlogic_ph1a" / "pinlist"
PACKAGE_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "anlogic_ph1a"


def _overlay(name: str) -> dict:
    return json.loads((PACKAGE_DIR / name).read_text(encoding="utf-8"))


def _manifest_entry(device: str) -> dict:
    manifest = json.loads((RAW_PINLIST_DIR / "_download_manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["entries"]:
        if entry["device"] == device:
            return entry
    raise KeyError(device)


def _parse(device: str, overlay_file: str, workbook_file: str) -> dict:
    return _parse_workbook(RAW_PINLIST_DIR / workbook_file, _overlay(overlay_file), _manifest_entry(device))


def test_anlogic_pinout_parser_extracts_real_pins_diff_pairs_and_trace_delay():
    parsed = _parse("PH1A90SEG325", "ph1a90seg325.json", "PH1A90SEG325_PINLIST.xlsx")

    assert parsed["_vendor"] == "Anlogic"
    assert parsed["total_pins"] == 324
    assert parsed["pins"][0]["pin"] == "A1"
    assert parsed["summary"]["by_function"]["SERDES_REFCLK"] == 4
    assert parsed["summary"]["diff_pairs"]["SERDES_REFCLK"] == 2
    assert any(pair["pair_name"] == "REFCLK_82" for pair in parsed["diff_pairs"])
    assert any(conflict["field"] == "package_pin_count" for conflict in parsed["source_conflicts"])

    programn = next(pin for pin in parsed["pins"] if pin["name"] == "PROGRAMN_0")
    assert abs(programn["attrs"]["min_trace_delay_ps"] - 95.9933) < 0.001
    assert abs(programn["attrs"]["max_trace_delay_ps"] - 96.8401) < 0.001


def test_anlogic_pinout_parser_keeps_package_overlay_rules_and_conflicts():
    parsed = _parse("PH1A400SFG676", "ph1a400sfg676.json", "PH1A400SFG676_PINLIST.xlsx")

    assert parsed["capability_blocks"]["pcie"]["phy_banks"] == [82, 83]
    assert parsed["capability_blocks"]["clock_distribution"]["right_half_serdes_clock_regions"] == 4
    assert parsed["capability_blocks"]["io_sso"]["bank_pair_budgets"]["31"]["vccio_gnd_pairs"] == 18
    assert parsed["package_io_banks"]["hp_banks"] == [31, 32, 33]
    assert any(conflict["field"] == "package_pinlist_download_url" for conflict in parsed["source_conflicts"])
    assert parsed["source_traceability"]["package_pinout"]["source_download_id"] == 1012


def test_anlogic_pinout_parser_detects_mipi_and_serdes_resources_per_package():
    mipi_pkg = _parse("PH1A180SFG676", "ph1a180sfg676.json", "PH1A180SFG676_PINLIST.xlsx")
    non_mipi_pkg = _parse("PH1A400SFG900", "ph1a400sfg900.json", "PH1A400SFG900_PINLIST.xlsx")

    assert mipi_pkg["summary"]["by_function"]["MIPI"] > 0
    assert "MIPI" not in non_mipi_pkg["summary"]["by_function"]
    assert non_mipi_pkg["summary"]["by_function"]["SERDES_RX"] == 32
    assert non_mipi_pkg["summary"]["by_function"]["SERDES_TX"] == 32
    assert non_mipi_pkg["summary"]["diff_pairs"]["SERDES_RX"] == 16
    assert non_mipi_pkg["summary"]["diff_pairs"]["SERDES_TX"] == 16
