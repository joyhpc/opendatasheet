import json
from pathlib import Path

from scripts.export_debugtool_interface import (
    DEFAULT_EXPORT_DIR,
    DEFAULT_POOL_DIR,
    INTERFACE_SCHEMA,
    POOL_SCHEMA,
    build_debugtool_interface,
    build_knowledge_pool,
)


REPO_ROOT = Path(__file__).resolve().parent
INTERFACE_PATH = REPO_ROOT / "data" / "debugtool_interface" / "intel_agilex5.json"


def _device(interface: dict, profile_id: str) -> dict:
    return next(
        device
        for device in interface["devices"]
        if device.get("debugtool_profile_id") == profile_id or device.get("profile_id") == profile_id
    )


def test_intel_agilex5_debugtool_interface_exposes_evidence_apis():
    interface = build_debugtool_interface(DEFAULT_EXPORT_DIR)
    device = _device(interface, "intel_agilex5:A5ED013B_B23A")

    assert interface["_schema"] == INTERFACE_SCHEMA
    assert interface["source_exports"]["device_count"] == 10
    assert device["selectors"]["has_hps"] is True
    assert device["selectors"]["has_gts_transceiver"] is True
    assert device["selectors"]["has_mipi_dphy"] is True
    assert device["selectors"]["has_external_memory_interface"] is True

    assert set(device["pin_groups"]["configuration"]["jtag"]) == {"TCK", "TDI", "TDO", "TMS"}
    assert device["pin_groups"]["configuration"]["jtag"]["TCK"]["ball"] == "BJ58"
    assert device["pin_groups"]["configuration"]["status"]["nCONFIG"]["ball"] == "BU32"
    assert device["pin_groups"]["configuration"]["status"]["nSTATUS"]["ball"] == "BV32"
    assert device["pin_groups"]["configuration"]["missing_generic_status_signals"] == ["CONF_DONE", "INIT_DONE"]

    jtag_api = device["evidence_apis"]["fpga_jtag_configuration"]
    assert "LM-FPGA-JTAG-CONFIG" in jtag_api["debugtool_link_models"]
    assert "SIG-QUARTUS-CABLE-SEEN-SCAN-CHAIN-FAIL" in jtag_api["debugtool_signatures"]
    assert any(item["id"] == "fpga_end_jtag_waveforms" for item in jtag_api["required_evidence"])

    assert "hps_hard_processor_debug" in device["evidence_apis"]
    assert "hps_uart" in device["evidence_apis"]["hps_hard_processor_debug"]["device_facts"]["hps_pin_groups"]
    assert device["evidence_apis"]["mipi_dphy_debug"]["device_facts"]["mipi_dphy_interface_count"] == 14
    assert device["evidence_apis"]["external_memory_interface"]["device_facts"]["dqs_pin_summary"]["dqs_related_pin_count"] > 0
    assert device["evidence_apis"]["gts_transceiver_link"]["device_facts"]["refclk_pair_count"] == 2


def test_non_soc_agilex5_debugtool_profile_omits_hps_api():
    interface = build_debugtool_interface(DEFAULT_EXPORT_DIR)
    device = _device(interface, "intel_agilex5:A5EC013B_B23A")

    assert device["selectors"]["has_hps"] is False
    assert "hps_hard_processor_debug" not in device["evidence_apis"]
    assert "fpga_jtag_configuration" in device["evidence_apis"]
    assert "mipi_dphy_debug" in device["evidence_apis"]


def test_checked_in_intel_agilex5_debugtool_interface_is_current():
    with INTERFACE_PATH.open(encoding="utf-8") as fp:
        checked_in = json.load(fp)

    assert checked_in == build_debugtool_interface(DEFAULT_EXPORT_DIR)


def test_intel_agilex5_knowledge_pool_splits_reusable_artifacts():
    pool = build_knowledge_pool(DEFAULT_EXPORT_DIR)

    assert pool["device_profiles.json"]["_schema"] == f"{POOL_SCHEMA}/device-profiles"
    assert pool["pin_signal_map.json"]["_schema"] == f"{POOL_SCHEMA}/pin-signal-map"
    assert pool["electrical_constraints.json"]["_schema"] == f"{POOL_SCHEMA}/electrical-constraints"
    assert pool["diagnostic_evidence_profiles.json"]["_schema"] == f"{POOL_SCHEMA}/diagnostic-evidence-profiles"
    assert pool["debug_readiness_matrix.json"]["_schema"] == f"{POOL_SCHEMA}/debug-readiness-matrix"

    profile = _device(pool["device_profiles.json"], "fpga.intel_agilex5.A5ED013B_B23A")
    pins = _device(pool["pin_signal_map.json"], "fpga.intel_agilex5.A5ED013B_B23A")
    electrical = _device(pool["electrical_constraints.json"], "fpga.intel_agilex5.A5ED013B_B23A")
    diagnostic = _device(pool["diagnostic_evidence_profiles.json"], "fpga.intel_agilex5.A5ED013B_B23A")

    assert profile["selectors"]["has_hps"] is True
    assert pins["pin_groups"]["configuration"]["jtag"]["TDO"]["ball"] == "BN55"
    assert electrical["supply_specs"]["VCCPT"]["typ"] == 1.8
    assert "agilex5_configuration_clock" in electrical["drc_rules"]
    jtag_api = diagnostic["evidence_apis"]["fpga_jtag_configuration"]
    assert "debugtool" in jtag_api["application_bindings"]
    assert "debugtool_link_models" not in jtag_api
    assert "LM-FPGA-JTAG-CONFIG" in jtag_api["application_bindings"]["debugtool"]["link_models"]


def test_intel_agilex5_debug_readiness_matrix_defines_coverage_boundary():
    matrix = build_knowledge_pool(DEFAULT_EXPORT_DIR)["debug_readiness_matrix.json"]

    assert matrix["readiness_summary"]["decision"] == "sufficient_for_debugtool_first_pass_and_evidence_planning"
    assert "final_root_cause_closure" in matrix["readiness_summary"]["does_not_satisfy_without_external_evidence"]

    requirements = {item["id"]: item for item in matrix["requirements"]}
    assert set(requirements) == {
        "fpga_jtag_configuration",
        "configuration_boot",
        "power_rail_integrity",
        "gts_transceiver_link",
        "mipi_dphy_debug",
        "external_memory_interface",
        "nios_soft_core_debug",
        "hps_hard_processor_debug",
    }
    assert requirements["fpga_jtag_configuration"]["coverage_level"] == "covered_for_first_pass"
    assert requirements["fpga_jtag_configuration"]["meets_debug_need"] is True
    assert "FPGA-end TCK/TMS/TDI/TDO waveforms" in requirements["fpga_jtag_configuration"]["external_required"]
    assert requirements["mipi_dphy_debug"]["coverage_level"] == "partial_project_binding_required"
    assert "selected MIPI IP lane count/order/polarity" in requirements["mipi_dphy_debug"]["external_required"]
    assert requirements["hps_hard_processor_debug"]["coverage_level"] == "partial_project_binding_required"


def test_checked_in_intel_agilex5_knowledge_pool_is_current():
    pool = build_knowledge_pool(DEFAULT_EXPORT_DIR)

    for filename, expected in pool.items():
        path = DEFAULT_POOL_DIR / filename
        assert path.exists(), filename
        if isinstance(expected, str):
            assert path.read_text(encoding="utf-8") == expected
        else:
            with path.open(encoding="utf-8") as fp:
                assert json.load(fp) == expected

    profile_yaml = (DEFAULT_POOL_DIR / "application_profiles.yaml").read_text(encoding="utf-8")
    assert "schematic_review:" in profile_yaml
    assert "debugtool:" in profile_yaml
    assert "- debug_readiness_matrix.json" in profile_yaml
    assert "diagnostic_evidence_profiles.json" in profile_yaml
