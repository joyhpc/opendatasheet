import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build_fpga_catalog import build_catalog
from export_anlogic_ph1a_sch_review import _export_record
from export_for_sch_review import export_fpga


ANLOGIC_EXTRACT_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "anlogic_ph1a"
ANLOGIC_PINOUT_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "pinout"
SCH_EXPORT_DIR = REPO_ROOT / "data" / "sch_review_export"


def _load_extract(name: str) -> dict:
    return json.loads((ANLOGIC_EXTRACT_DIR / name).read_text(encoding="utf-8"))


def _load_export(name: str) -> dict:
    return json.loads((SCH_EXPORT_DIR / name).read_text(encoding="utf-8"))


def _load_pinout(name: str) -> dict:
    return json.loads((ANLOGIC_PINOUT_DIR / name).read_text(encoding="utf-8"))


def test_anlogic_family_extract_has_expected_summary_and_conflicts():
    family = _load_extract("family.json")

    assert family["summary"]["device_count"] == 7
    assert family["summary"]["pcie_capable_packages"] == [
        "PH1A90SBG484",
        "PH1A90SEG324",
        "PH1A180SFG676",
        "PH1A400SFG676",
        "PH1A400SFG900",
    ]
    assert family["summary"]["locale_conflict_devices"] == [
        "PH1A90SBG484",
        "PH1A90SEG324",
        "PH1A90SEG325",
    ]


def test_anlogic_package_extract_preserves_package_level_rules():
    seg325 = _load_extract("ph1a90seg325.json")
    sfg900 = _load_extract("ph1a400sfg900.json")
    geg324 = _load_extract("ph1a60geg324.json")

    assert seg325["capability_blocks"]["pcie"]["present"] is None
    assert seg325["source_conflicts"]
    assert len(seg325["capability_blocks"]["configuration_modes"]["supported_modes"]) == 4
    assert seg325["capability_blocks"]["configuration_modes"]["initialization_flow"]["steps"][0]["delay_cycles"] == 16384
    assert seg325["capability_blocks"]["clock_distribution"]["global_clock_lines"] == 32
    assert seg325["capability_blocks"]["pll_resources"]["package_pll_blocks"] == 12
    assert seg325["capability_blocks"]["pll_resources"]["zero_delay_buffer_constraints"]["m_equals_n_required"] is True
    assert seg325["capability_blocks"]["clock_distribution"]["right_half_serdes_clock_regions"] == 2
    assert seg325["capability_blocks"]["io_sso"]["evidence_level"] == "package_alias_inference"
    assert seg325["capability_blocks"]["io_sso"]["limit_tables"]["HRIO"]["3.3V"]["drive_strength_mA"]["16"]["fast"] == 4
    assert seg325["capability_blocks"]["serdes_reference_clocking"]["external_differential_termination_ohms"] == 100
    assert seg325["capability_blocks"]["serdes_power_integrity"]["rail_recommendations"]["VPHYVCCA"]["max_ripple_mV"] == 30
    assert sfg900["package_io_banks"]["hp_banks"] == [31, 32, 33]
    assert sfg900["capability_blocks"]["io_sso"]["bank_pair_budgets"]["31"]["vccio_gnd_pairs"] == 18
    assert sfg900["capability_blocks"]["high_speed_serial"]["package_rate_ceiling_gbps"] == 12.5
    assert geg324["capability_blocks"]["serdes_reference_clocking"]["present"] is False
    assert geg324["capability_blocks"]["serdes_power_integrity"]["present"] is False


def test_anlogic_sch_review_export_uses_real_pinout_and_refclk_pairs():
    exported = _export_record(_load_pinout("ph1a400sfg900_pinout.json"))

    assert exported["device_identity"]["vendor"] == "Anlogic"
    assert exported["banks"]["31"]["bank_type"] == "HPIO"
    assert exported["pins"]
    assert exported["pins"][0]["pin"] == "AB6"
    assert "synthetic" not in exported["pins"][0].get("attrs", {})
    assert exported["constraint_blocks"]["configuration_boot"]["class"] == "boot_configuration"
    assert exported["constraint_blocks"]["refclk_requirements"].get("package_level_only") is not True
    assert exported["constraint_blocks"]["refclk_requirements"]["refclk_pairs"][0]["pair_name"] == "REFCLK_80"
    assert exported["constraint_blocks"]["refclk_requirements"]["refclk_pair_count"] == 8
    assert exported["capability_blocks"]["configuration_modes"]["source"] == "UG905"
    assert exported["capability_blocks"]["clock_distribution"]["source"] == "UG912"
    assert exported["capability_blocks"]["pll_resources"]["source"] == "UG906"
    assert exported["capability_blocks"]["io_sso"]["source"] == "TR901"
    assert exported["capability_blocks"]["serdes_reference_clocking"]["source"] == "UG907"
    assert exported["capability_blocks"]["serdes_power_integrity"]["source"] == "UG907"


def test_anlogic_standalone_export_delegates_to_common_export():
    pinout = _load_pinout("ph1a90seg325_pinout.json")

    standalone = _export_record(pinout)
    common = export_fpga(
        {"extraction": {"component": {"manufacturer": "Anlogic", "description": "PH1A"}}},
        pinout,
    )

    assert standalone == common


def test_anlogic_export_files_validate_catalog_presence():
    exported = _load_export("PH1A90SEG325.json")
    catalog = build_catalog(SCH_EXPORT_DIR)

    assert exported["_type"] == "fpga"
    assert exported["constraint_blocks"]["source_consistency_review"]["review_required"] is True
    assert exported["pins"][0]["pin"] == "A1"
    assert exported["constraint_blocks"]["refclk_requirements"].get("package_level_only") is not True
    anlogic_tree = catalog["tree"]["Anlogic"]["families"]["SALPHOENIX 1A"]["series"]["PH1A"]["base_devices"]
    assert "PH1A90" in anlogic_tree
    assert anlogic_tree["PH1A90"]["devices"]["PH1A90SEG325"]["packages"]["SEG325"]["file"] == "PH1A90SEG325.json"
