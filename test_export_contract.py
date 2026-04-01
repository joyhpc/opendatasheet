import copy
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent
PINOUT_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "pinout"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from export_for_sch_review import export_fpga, export_normal_ic, main as export_for_sch_review_main
from export_selection_profile import main as export_selection_profile_main
from export_selection_profile import build_selection_card
from export_design_bundle import _collect_constraints, _pick_preferred_package
from normal_ic_contract import build_normal_ic_record, normal_ic_record_to_export


def _load_pinout(name: str) -> dict:
    return json.loads((PINOUT_DIR / name).read_text())


def test_export_normal_ic_emits_v2_with_canonical_domains_and_flat_compat():
    data = {
        "extraction": {
            "component": {
                "mpn": "TEST123",
                "manufacturer": "TestSemi",
                "category": "Buck",
                "description": "Test converter",
            },
            "absolute_maximum_ratings": [
                {
                    "parameter": "Input voltage",
                    "symbol": "VIN",
                    "min": None,
                    "max": 42.0,
                    "unit": "V",
                    "conditions": None,
                }
            ],
            "electrical_characteristics": [
                {
                    "parameter": "Quiescent current",
                    "symbol": "IQ",
                    "min": None,
                    "typ": 1.2,
                    "max": 2.0,
                    "unit": "mA",
                    "conditions": "enabled",
                }
            ],
        },
        "pin_index": {
            "packages": {
                "SOT-23-5": {
                    "1": {
                        "name": "VIN",
                        "direction": "POWER_IN",
                        "signal_type": "POWER",
                        "description": "Input supply",
                        "unused_treatment": None,
                    }
                }
            }
        },
        "design_extraction": {
            "design_page_candidates": [
                {"page_num": 4, "heading": "Typical Application", "kind": "application"}
            ],
            "recommended_external_components": [
                {"component": "input_capacitor", "value": "10uF"}
            ],
            "design_equation_hints": [],
            "layout_hints": [],
            "supply_recommendations": [],
            "topology_hints": [],
        },
    }

    exported = export_normal_ic(data)

    assert exported["_schema"] == "device-knowledge/2.0"
    assert exported["domains"]["pin"]["packages"]["SOT-23-5"]["pins"]["1"]["name"] == "VIN"
    assert exported["domains"]["electrical"]["absolute_maximum_ratings"]["VIN"]["max"] == 42.0
    assert exported["domains"]["electrical"]["electrical_parameters"]["IQ"]["typ"] == 1.2
    assert "thermal" not in exported["domains"]
    assert exported["thermal"] == {}
    assert exported["domains"]["design_context"]["design_pages"]["pages"][0]["page"] == 4
    assert exported["packages"]["SOT-23-5"]["pins"]["1"]["name"] == "VIN"


def test_export_normal_ic_backfills_logical_pins_and_emits_mipi_capability_blocks():
    data = {
        "domains": {
            "electrical": {
                "component": {
                    "mpn": "CXD4984ER-W",
                    "manufacturer": "Sony",
                    "category": "Other",
                    "description": "GVIF3 deserializer with dual MIPI CSI-2 output.",
                },
                "absolute_maximum_ratings": [],
                "electrical_characteristics": [],
            },
            "pin": {
                "logical_pins": [
                    {
                        "name": "SCL0",
                        "direction": "BIDIRECTIONAL",
                        "signal_type": "DIGITAL",
                        "description": "I2C clock input / output for Aux interface and register access",
                        "packages": {"VQFN-64": [18]},
                        "unused_treatment": None,
                    },
                    {
                        "name": "SDA0",
                        "direction": "BIDIRECTIONAL",
                        "signal_type": "DIGITAL",
                        "description": "I2C data input / output for Aux interface and register access",
                        "packages": {"VQFN-64": [19]},
                        "unused_treatment": None,
                    },
                    {
                        "name": "CE",
                        "direction": "INPUT",
                        "signal_type": "DIGITAL",
                        "description": "System reset input",
                        "packages": {"VQFN-64": [26]},
                        "unused_treatment": None,
                    },
                    {
                        "name": "I2CADR",
                        "direction": "INPUT",
                        "signal_type": "DIGITAL",
                        "description": "I2C address selection input",
                        "packages": {"VQFN-64": [32]},
                        "unused_treatment": None,
                    },
                ]
            },
            "protocol": {
                "interfaces": [
                    {
                        "protocol_type": "MIPI",
                        "role": None,
                        "instance_name": "CSI2_TX_DPHY",
                        "i2c_config": None,
                        "spi_config": None,
                        "uart_config": None,
                        "signals": [
                            {"name": "D04CP", "direction": "output", "description": "Port 0 clock lane output"},
                            {"name": "D14CP", "direction": "output", "description": "Port 1 clock lane output"},
                        ],
                        "timing_constraints": [
                            {
                                "parameter": "MIPI D-PHY output data rate",
                                "symbol": "DR_MIPI",
                                "min": 260,
                                "typ": None,
                                "max": 4500,
                                "unit": "Mbps",
                                "conditions": "Per lane",
                            }
                        ],
                        "command_set": [],
                        "notes": "Two CSI-2 ports, each with 4 data lanes and 1 clock lane.",
                        "mipi_config": {
                            "transport": "CSI-2",
                            "direction": "TX",
                            "phy_type": "D-PHY",
                            "port_count": 2,
                            "data_lanes_per_port": 4,
                            "clock_lanes_per_port": 1,
                            "min_rate_mbps_per_lane": 260,
                            "max_rate_mbps_per_lane": 4500,
                            "phy_version": "2.1",
                            "protocol_version": "2.1",
                            "source_pages": [24, 41, 42],
                        },
                    },
                    {
                        "protocol_type": "MIPI",
                        "role": None,
                        "instance_name": "CSI2_TX_CPHY",
                        "i2c_config": None,
                        "spi_config": None,
                        "uart_config": None,
                        "signals": [
                            {"name": "D040P", "direction": "output", "description": "Shared Port 0 high-speed output"},
                            {"name": "D140P", "direction": "output", "description": "Shared Port 1 high-speed output"},
                        ],
                        "timing_constraints": [
                            {
                                "parameter": "MIPI C-PHY symbol rate",
                                "symbol": None,
                                "min": 300,
                                "typ": None,
                                "max": 4500,
                                "unit": "Msps",
                                "conditions": "Per trio lane",
                            }
                        ],
                        "command_set": [],
                        "notes": "Two CSI-2 ports, each configurable as 3 C-PHY trios.",
                        "mipi_config": {
                            "transport": "CSI-2",
                            "direction": "TX",
                            "phy_type": "C-PHY",
                            "port_count": 2,
                            "trios_per_port": 3,
                            "min_symbol_rate_msps": 300,
                            "max_symbol_rate_msps": 4500,
                            "phy_version": "1.2",
                            "protocol_version": "2.1",
                            "source_pages": [46, 47, 49, 54],
                        },
                    },
                    {
                        "protocol_type": "I2C",
                        "role": "both",
                        "instance_name": "I2C0",
                        "i2c_config": {
                            "slave_address_hex": None,
                            "address_configurable": True,
                            "address_pins": ["I2CADR"],
                            "address_bits": 7,
                            "max_clock_hz": 1000000,
                            "supports_clock_stretching": None,
                            "supports_repeated_start": None,
                        },
                        "spi_config": None,
                        "uart_config": None,
                        "signals": [
                            {"name": "SCL0", "direction": "bidirectional", "description": "I2C clock"},
                            {"name": "SDA0", "direction": "bidirectional", "description": "I2C data"},
                            {"name": "I2CADR", "direction": "input", "description": "Address select"},
                        ],
                        "timing_constraints": [
                            {
                                "parameter": "I2C clock frequency",
                                "symbol": "fSCL",
                                "min": 0,
                                "typ": None,
                                "max": 1000000,
                                "unit": "Hz",
                                "conditions": "Standard/Fast/Fast-mode Plus",
                            }
                        ],
                        "command_set": [],
                        "notes": "Aux interface and register access.",
                    },
                ],
                "protocol_summary": {
                    "total_interfaces": 3,
                    "has_i2c": True,
                    "has_spi": False,
                    "has_uart": False,
                    "primary_interface": "MIPI",
                },
            },
        }
    }

    exported = export_normal_ic(data)

    assert exported["packages"]["VQFN-64"]["pins"]["18"]["name"] == "SCL0"
    assert exported["packages"]["VQFN-64"]["pins"]["26"]["name"] == "CE"
    assert exported["domains"]["protocol"]["protocol_summary"]["has_i2c"] is True
    assert exported["capability_blocks"]["mipi_phy"]["phy_types"] == ["C-PHY", "D-PHY"]
    assert exported["capability_blocks"]["mipi_phy"]["dphy"]["max_data_lanes"] == 4
    assert exported["capability_blocks"]["mipi_phy"]["dphy"]["max_rate_gbps_per_lane"] == 4.5
    assert exported["capability_blocks"]["mipi_phy"]["cphy"]["max_trios"] == 3
    assert exported["capability_blocks"]["mipi_phy"]["cphy"]["max_symbol_rate_gsps"] == 4.5
    assert exported["constraint_blocks"]["mipi_phy"]["review_required"] is True
    assert exported["constraint_blocks"]["mipi_phy"]["phy_types"] == ["C-PHY", "D-PHY"]


def test_export_fpga_emits_v2_with_pin_domain_and_flat_compat():
    pinout = copy.deepcopy(_load_pinout("intel_agilex5_a5ec013b_b23a.json"))

    exported = export_fpga({"extraction": {"component": {}}}, pinout)

    assert exported["_schema"] == "device-knowledge/2.0"
    assert exported["domains"]["pin"]["pins"][0]["pin"] == exported["pins"][0]["pin"]
    assert exported["domains"]["pin"]["lookup"]["by_pin"] == exported["lookup"]["by_pin"]
    assert exported["domains"]["pin"]["diff_pairs"][0]["p_pin"] == exported["diff_pairs"][0]["p_pin"]


def test_export_fpga_gowin_overlay_still_emits_refclk_constraints():
    pinout = copy.deepcopy(_load_pinout("gowin_gw5at-60_ug225.json"))

    exported = export_fpga({"extraction": {"component": {}}}, pinout)

    refclk = exported["constraint_blocks"].get("refclk_requirements")
    assert exported["_schema"] == "device-knowledge/2.0"
    assert refclk is not None
    assert refclk["refclk_pair_count"] >= 1
    assert refclk.get("protocol_refclk_profiles")


def test_normal_ic_contract_record_is_internal_canonical_source():
    record = build_normal_ic_record(
        mpn="TEST123",
        manufacturer="TestSemi",
        category="Buck",
        description="Test converter",
        packages={"SOT-23-5": {"pin_count": 5, "pins": {"1": {"name": "VIN"}}}},
        abs_max={"VIN": {"parameter": "Input voltage", "max": 42.0, "unit": "V", "conditions": None}},
        elec_params={"IQ": {"parameter": "Quiescent current", "typ": 1.2, "unit": "mA", "conditions": "enabled"}},
        drc_hints={"vin_abs_max": {"value": 42.0, "unit": "V"}},
        thermal={},
        design_context={
            "design_page_candidates": [{"page_num": 4, "heading": "Typical Application", "kind": "application"}],
            "component_value_hints": [{"values": ["10uF"], "source_page": 4, "snippet": "Use 10uF input capacitor"}],
            "design_range_hints": [{"name": "VIN", "min": 4.5, "max": 36.0, "unit": "V", "source_page": 4, "snippet": "VIN range"}],
            "configuration_mappings": [{"pin": "MODE", "resistor_divider": {"top_resistor_kohm": 100, "bottom_resistor_kohm": 10}}],
            "design_recommendations": [{"topic": "feedback_divider", "recommended_r_lower_kohm": 10}],
        },
        register_data={},
        timing_data={},
        power_seq_data={},
        parametric_data={},
        protocol_data={},
        package_data={},
    )

    exported = normal_ic_record_to_export(record)

    assert record.schema_version == "device-knowledge/2.0"
    assert record.domains["design_context"]["design_pages"]["pages"][0]["page"] == 4
    assert record.domains["design_context"]["component_value_hints"][0]["values"] == ["10uF"]
    assert record.domains["design_context"]["design_range_hints"][0]["name"] == "VIN"
    assert record.domains["design_context"]["configuration_mappings"][0]["pin"] == "MODE"
    assert record.domains["design_context"]["design_recommendations"][0]["topic"] == "feedback_divider"
    assert exported["_schema"] == record.schema_version
    assert exported["domains"]["pin"]["packages"]["SOT-23-5"]["pins"]["1"]["name"] == "VIN"


def test_export_normal_ic_applies_tps56c215_design_context_override():
    data = {
        "extraction": {
            "component": {
                "mpn": "TPS56C215",
                "manufacturer": "Texas Instruments",
                "category": "Buck",
                "description": "12A synchronous buck",
            },
            "absolute_maximum_ratings": [],
            "electrical_characteristics": [],
        },
        "pin_index": {"packages": {}},
    }

    exported = export_normal_ic(data)
    design_context = exported["domains"]["design_context"]

    assert len(design_context["configuration_mappings"]) == 12
    assert design_context["configuration_mappings"][0]["pin"] == "MODE"
    assert design_context["configuration_mappings"][0]["behavior"]["switching_frequency_khz"] == 400
    assert design_context["design_recommendations"][1]["topic"] == "recommended_component_values"
    assert design_context["design_recommendations"][2]["recommended_r_lower_kohm"] == 10


def test_export_normal_ic_auto_extracts_buck_design_context_from_local_pdf():
    extracted = json.loads((REPO_ROOT / "data" / "extracted_v2" / "0130-01-00003_TPS62040DRC.json").read_text())

    exported = export_normal_ic(extracted)
    design_context = exported["domains"]["design_context"]

    assert design_context["design_pages"]["total_pages"] >= 1
    assert design_context["recommended_external_components"]
    assert design_context["component_value_hints"]


def test_export_normal_ic_auto_extracts_chinese_buck_design_context_from_local_pdf():
    extracted = json.loads((REPO_ROOT / "data" / "extracted_v2" / "0130-01-00059_TPS564247DRLR.json").read_text())

    exported = export_normal_ic(extracted)
    design_context = exported["domains"]["design_context"]

    assert design_context["design_pages"]["total_pages"] >= 1
    assert design_context["component_value_hints"]


def test_selection_profile_reads_domains_without_flat_fields():
    device = {
        "_schema": "device-knowledge/2.0",
        "_type": "normal_ic",
        "mpn": "TEST123",
        "manufacturer": "TestSemi",
        "category": "Buck",
        "description": "Test converter",
        "domains": {
            "pin": {
                "packages": {
                    "SOT-23-5": {
                        "pin_count": 5,
                        "pins": {"1": {"name": "VIN"}},
                    }
                }
            },
            "electrical": {
                "absolute_maximum_ratings": {
                    "VIN": {"parameter": "Input voltage", "max": 42.0, "unit": "V", "conditions": None}
                },
                "electrical_parameters": {
                    "IQ": {"parameter": "Quiescent current", "typ": 1.2, "unit": "mA", "conditions": "enabled"}
                },
                "drc_hints": {
                    "vin_abs_max": {"value": 42.0, "unit": "V"},
                },
            },
            "thermal": {
                "theta_ja": {"typ": 48.0, "unit": "C/W", "source": "electrical_characteristics"}
            },
            "register": {
                "interfaces": [{"bus": "I2C"}]
            },
        },
    }

    card = build_selection_card(device)

    assert card is not None
    assert card["packages"] == ["SOT-23-5"]
    assert card["pin_count"] == 5
    assert card["key_specs"]["input_voltage_abs_max"]["max"] == 42.0
    assert "register_interface" in card["features"]


def test_selection_profile_ignores_tps56c215_ldo_current_limit_for_output_current():
    device = {
        "_schema": "device-knowledge/2.0",
        "_type": "normal_ic",
        "mpn": "TPS56C215",
        "manufacturer": "Texas Instruments",
        "category": "Buck",
        "description": "12A synchronous buck",
        "domains": {
            "pin": {"packages": {"VQFN-18": {"pin_count": 18, "pins": {}}}},
            "electrical": {
                "absolute_maximum_ratings": {
                    "IOUT": {"parameter": "Output Current", "max": 14.0, "unit": "A", "conditions": None}
                },
                "electrical_parameters": {
                    "ILIM5": {"parameter": "LDO Output Current limit", "min": 100, "typ": 150, "max": 200, "unit": "mA"},
                },
                "drc_hints": {},
            },
        },
    }

    card = build_selection_card(device)

    assert card["operating_conditions"]["iout_max"] == 14.0
    assert card["key_specs"]["output_current"]["max"] == 14.0


def test_design_bundle_helpers_can_use_domains_backfilled_normal_ic_view():
    device = {
        "_schema": "device-knowledge/2.0",
        "_type": "normal_ic",
        "mpn": "TEST123",
        "manufacturer": "TestSemi",
        "category": "Buck",
        "description": "Test converter",
        "domains": {
            "pin": {
                "packages": {
                    "SOT-23-5": {
                        "pin_count": 5,
                        "pins": {"1": {"name": "VIN"}, "2": {"name": "GND"}},
                    }
                }
            },
            "electrical": {
                "absolute_maximum_ratings": {
                    "VIN": {"parameter": "Input voltage", "max": 42.0, "unit": "V", "conditions": None}
                },
                "electrical_parameters": {
                    "VIN": {"parameter": "Input voltage range", "min": 4.5, "max": 36.0, "unit": "V", "conditions": None}
                },
                "drc_hints": {
                    "vin_abs_max": {"value": 42.0, "unit": "V"},
                },
            },
        },
    }

    preferred_package = _pick_preferred_package(device)
    constraints = _collect_constraints(device)

    assert preferred_package == "SOT-23-5"
    assert constraints["vin_abs_max"]["max"] == 42.0


def test_export_for_sch_review_main_removes_stale_device_exports(tmp_path):
    extracted_dir = tmp_path / "extracted_v2"
    fpga_pinout_dir = extracted_dir / "fpga" / "pinout"
    output_dir = tmp_path / "sch_review_export"
    extracted_dir.mkdir(parents=True)
    fpga_pinout_dir.mkdir(parents=True)
    output_dir.mkdir()

    input_payload = {
        "extraction": {
            "component": {
                "mpn": "TEST123",
                "manufacturer": "TestSemi",
                "category": "Buck",
                "description": "Test converter",
            },
            "absolute_maximum_ratings": [],
            "electrical_characteristics": [],
        },
        "pin_index": {"packages": {}},
    }
    (extracted_dir / "test123.json").write_text(json.dumps(input_payload), encoding="utf-8")
    stale_path = output_dir / "STALE_DEVICE.json"
    stale_path.write_text('{"_schema":"sch-review-device/1.1"}\n', encoding="utf-8")

    old_argv = sys.argv[:]
    try:
        sys.argv = [
            "export_for_sch_review.py",
            str(extracted_dir),
            str(fpga_pinout_dir),
            str(output_dir),
        ]
        export_for_sch_review_main()
    finally:
        sys.argv = old_argv

    assert not stale_path.exists()
    assert (output_dir / "TEST123.json").exists()


def test_export_selection_profile_main_removes_stale_profiles(tmp_path):
    export_dir = tmp_path / "sch_review_export"
    output_dir = tmp_path / "selection_profile"
    export_dir.mkdir()
    output_dir.mkdir()

    exported = export_normal_ic(
        {
            "extraction": {
                "component": {
                    "mpn": "TEST123",
                    "manufacturer": "TestSemi",
                    "category": "LDO",
                    "description": "Test regulator",
                },
                "absolute_maximum_ratings": [],
                "electrical_characteristics": [],
            },
            "pin_index": {"packages": {}},
        }
    )
    (export_dir / "TEST123.json").write_text(json.dumps(exported), encoding="utf-8")
    stale_path = output_dir / "STALE_DEVICE.json"
    stale_path.write_text('{"_schema":"selection-profile/1.0"}\n', encoding="utf-8")

    old_argv = sys.argv[:]
    try:
        sys.argv = [
            "export_selection_profile.py",
            "--export-dir",
            str(export_dir),
            "--output-dir",
            str(output_dir),
        ]
        export_selection_profile_main()
    finally:
        sys.argv = old_argv

    assert not stale_path.exists()
    assert (output_dir / "TEST123.json").exists()
    assert (output_dir / "_index.json").exists()
