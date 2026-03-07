import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


def test_normal_ic_bundle_export(tmp_path):
    output_dir = tmp_path / "bundles"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "TPS62147",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "generated" in result.stdout

    bundle_dir = output_dir / "TPS62147"
    design_intent = json.loads((bundle_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    module_template = json.loads((bundle_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    quickstart = (bundle_dir / "L2_quickstart.md").read_text(encoding="utf-8")

    control_names = {item["name"] for item in design_intent["pin_groups"]["control_inputs"]}
    roles = {item["role"] for item in design_intent["external_components"]}

    assert "EN" in control_names
    assert {"input_decoupling", "output_capacitor", "inductor"}.issubset(roles)
    assert any(block.get("role") == "feedback_divider" for block in module_template["blocks"])
    assert design_intent["datasheet_design_context"]["source_record"] == "0130-01-00037_TPS62148RGXR.json"
    assert design_intent["datasheet_design_context"]["design_page_candidates"]
    assert design_intent["constraints"]["current_limit"]["source_key"] == "ILIMH"
    assert design_intent["constraints"]["vout_range"]["source_kind"] == "datasheet_range_hint"
    assert design_intent["constraints"]["vout_range"]["max"] == 12.0
    assert "First-pass checklist" in quickstart
    assert "Datasheet design pages" in quickstart
    assert "Datasheet operating windows" in quickstart
    assert "Typical application values" in quickstart


def test_fpga_bundle_export(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "GW5AT-60_UG225",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    bundle_dir = output_dir / "GW5AT-60_UG225"
    design_intent = json.loads((bundle_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    module_template = json.loads((bundle_dir / "L3_module_template.json").read_text(encoding="utf-8"))

    assert design_intent["device_ref"]["type"] == "fpga"
    assert "power_rails" in design_intent
    assert any(item["role"] == "configuration_header" for item in design_intent["external_components"])
    assert any(net["name"] == "JTAG" for net in module_template["nets"])
    assert {item["source_path"] for item in design_intent.get("reference_design_assets", [])} == {
        "data/sch_review_export/reference/gowin_gw5at60_devboard_ref.md",
        "data/sch_review_export/reference/gowin_gw5at_design_guide.md",
    }


def test_fpga_bundle_export_keeps_package_specific_bundle_dirs(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "GW5AT-60_UG225",
            "--device",
            "GW5AT-60_UG324S",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    ug225_manifest = json.loads((output_dir / "GW5AT-60_UG225" / "bundle_manifest.json").read_text(encoding="utf-8"))
    ug324s_manifest = json.loads((output_dir / "GW5AT-60_UG324S" / "bundle_manifest.json").read_text(encoding="utf-8"))

    assert ug225_manifest["source_export"] == "GW5AT-60_UG225.json"
    assert ug324s_manifest["source_export"] == "GW5AT-60_UG324S.json"
    assert ug225_manifest["reference_files"] == ug324s_manifest["reference_files"]


def test_ldo_constraints_include_capacitor_windows(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "LP5907",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    bundle_dir = output_dir / "LP5907"
    design_intent = json.loads((bundle_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    quickstart = (bundle_dir / "L2_quickstart.md").read_text(encoding="utf-8")

    assert design_intent["constraints"]["output_capacitance"]["source_key"] == "COUT"
    assert design_intent["constraints"]["output_cap_esr"]["source_key"] == "ESR"
    assert design_intent["constraints"]["iout_max"]["source_key"] == "ILOAD"
    assert "output_capacitance" in quickstart
    assert "Typical application values" in quickstart


def test_switch_bundle_export_includes_schematic_hints(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "TPS2662x",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    bundle_dir = output_dir / "TPS2662x"
    design_intent = json.loads((bundle_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    quickstart = (bundle_dir / "L2_quickstart.md").read_text(encoding="utf-8")

    roles = {item["role"] for item in design_intent["external_components"]}

    assert {"current_limit_resistor", "dvdt_capacitor", "uvlo_divider", "ovp_divider"}.issubset(roles)
    assert "AUTO_CURRENT_LIMIT_RESISTOR" in quickstart
    assert "AUTO_DVDT_CAPACITOR" in quickstart


def test_analog_switch_bundle_export_includes_switch_templates(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "ADG706/ADG707",
            "--device",
            "ADG714/ADG715",
            "--device",
            "ADG728/ADG729",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    adg706_dir = output_dir / "ADG706_ADG707"
    adg706_intent = json.loads((adg706_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    adg706_template = json.loads((adg706_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    adg706_quickstart = (adg706_dir / "L2_quickstart.md").read_text(encoding="utf-8")
    adg706_roles = {item["role"] for item in adg706_intent["external_components"]}

    assert {"supply_decoupling", "address_source_or_straps", "enable_bias", "analog_channel_breakout"}.issubset(adg706_roles)
    assert "input_capacitor" not in adg706_roles
    assert adg706_template["default_switch_template"] == "addressable_analog_mux"
    assert "addressable_analog_mux" in {item["name"] for item in adg706_template.get("switch_templates", [])}
    assert "Analog switch implementation notes" in adg706_quickstart
    assert "Start here:" in adg706_quickstart

    adg714_dir = output_dir / "ADG714_ADG715"
    adg714_intent = json.loads((adg714_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    adg714_template = json.loads((adg714_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    adg714_roles = {item["role"] for item in adg714_intent["external_components"]}

    assert {"supply_decoupling", "reset_bias", "control_header_or_mcu", "switch_bank_breakout"}.issubset(adg714_roles)
    assert adg714_template["default_switch_template"] == "serial_switch_bank"
    assert "serial_switch_bank" in {item["name"] for item in adg714_template.get("switch_templates", [])}

    adg728_dir = output_dir / "ADG728_ADG729"
    adg728_intent = json.loads((adg728_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    adg728_template = json.loads((adg728_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    adg728_quickstart = (adg728_dir / "L2_quickstart.md").read_text(encoding="utf-8")
    adg728_roles = {item["role"] for item in adg728_intent["external_components"]}
    adg728_nets = {item["name"] for item in adg728_intent["starter_nets"]}

    assert {"supply_decoupling", "i2c_pullups", "address_source_or_straps", "reset_bias", "analog_channel_breakout"}.issubset(adg728_roles)
    assert {"I2C_SCL", "I2C_SDA", "ADDR_BUS", "RESET_N", "MUX_COM", "MUX_CH"}.issubset(adg728_nets)
    assert adg728_template["default_switch_template"] == "i2c_switch_matrix"
    assert "i2c_switch_matrix" in {item["name"] for item in adg728_template.get("switch_templates", [])}
    assert "Control modes: `parallel_address` `i2c`" in adg728_quickstart


def test_opamp_bundle_export_includes_analog_constraints(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "AD8571/AD8572/AD8574",
            "--device",
            "LM358",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    ad8571_dir = output_dir / "AD8571_AD8572_AD8574"
    ad8571_intent = json.loads((ad8571_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    ad8571_quickstart = (ad8571_dir / "L2_quickstart.md").read_text(encoding="utf-8")
    ad8571_starter_nets = {item["name"] for item in ad8571_intent["starter_nets"]}

    assert ad8571_intent["constraints"]["vin_abs_max"]["source_key"] == "Vs"
    assert ad8571_intent["constraints"]["gain_bandwidth"]["source_key"] == "GBP"
    assert ad8571_intent["constraints"]["slew_rate"]["source_key"] == "SR"
    assert ad8571_intent["constraints"]["supply_current"]["source_key"] == "Isy"
    assert {"V+", "GND", "VIN_SIG", "VOUT_ANA", "VREF"}.issubset(ad8571_starter_nets)
    assert "AUTO_SNUBBER_CAPACITOR" in ad8571_quickstart
    assert "OpAmp implementation notes" in ad8571_quickstart
    assert "Preferred package anchors" in ad8571_quickstart

    lm358_dir = output_dir / "LM358"
    lm358_intent = json.loads((lm358_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    lm358_quickstart = (lm358_dir / "L2_quickstart.md").read_text(encoding="utf-8")

    assert lm358_intent["constraints"]["common_mode_range"]["source_key"] == "VICR"
    assert lm358_intent["constraints"]["supply_current"]["source_key"] == "ICC"
    assert "AUTO_FILTER_NETWORK" in lm358_quickstart


def test_opamp_bundle_export_includes_topology_candidates(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "LM358",
            "--device",
            "AD8571/AD8572/AD8574",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    lm358_template = json.loads((output_dir / "LM358" / "L3_module_template.json").read_text(encoding="utf-8"))
    lm358_quickstart = (output_dir / "LM358" / "L2_quickstart.md").read_text(encoding="utf-8")
    lm358_context = lm358_template["opamp_device_context"]
    lm358_default_template = next(item for item in lm358_template["opamp_templates"] if item["name"] == "active_filter")
    lm358_topologies = {item["name"] for item in lm358_template.get("topology_candidates", [])}
    lm358_templates = {item["name"] for item in lm358_template.get("opamp_templates", [])}
    lm358_block_refs = {item["ref"] for item in lm358_template.get("blocks", [])}

    assert {"active_filter", "buffer_stage"}.issubset(lm358_topologies)
    assert {"non_inverting_gain_stage", "inverting_gain_stage", "active_filter", "buffer_stage"}.issubset(lm358_templates)
    assert lm358_template["default_opamp_template"] == "active_filter"
    assert {"XFILT1", "XBUF1", "RFILT", "CFILT"}.issubset(lm358_block_refs)
    assert lm358_context["channel_count"] == 2
    assert lm358_context["channel_units"][0]["package_bindings"] == {"OUT": "1", "IN-": "2", "IN+": "3"}
    assert lm358_context["shared_power_pins"]["negative"][0]["pin"] == "4"
    assert lm358_context["shared_power_pins"]["positive"][0]["pin"] == "8"
    assert lm358_context["supply_style"] == "single_supply"
    assert {item["symbol_unit"] for item in lm358_context["channel_units"]} == {"U1A", "U1B"}
    assert lm358_default_template["default_refdes_map"]["RFILT1"] == "RFILT1"
    assert lm358_default_template["sheet_instances"][0]["opamp_unit"] == "U1A"
    assert any(item["opamp_unit"] == "U1B" and item["package_bindings"] == {"IN+": "5", "IN-": "6", "OUT": "7"} for item in lm358_default_template["sheet_instances"][1:])
    assert any(item["symbol_pin"] == "U1A.OUT" and item["package_pin"] == "1" for item in lm358_default_template["pin_bindings"])
    assert any(item["symbol_pin"] == "U1A.PWR+" and item["package_pin"] == "8" and item["shared_across_units"] for item in lm358_default_template["pin_bindings"])
    assert any(item["net"] == "VREF" and item["role"] == "bias_reference" for item in lm358_default_template["net_bindings"])
    assert "Suggested topologies" in lm358_quickstart
    assert "L3 Templates" in lm358_quickstart
    assert "Start here:" in lm358_quickstart

    ad8571_template = json.loads((output_dir / "AD8571_AD8572_AD8574" / "L3_module_template.json").read_text(encoding="utf-8"))
    ad8571_quickstart = (output_dir / "AD8571_AD8572_AD8574" / "L2_quickstart.md").read_text(encoding="utf-8")
    ad8571_context = ad8571_template["opamp_device_context"]
    ad8571_default_template = next(item for item in ad8571_template["opamp_templates"] if item["name"] == "capacitive_load_driver")
    ad8571_topologies = {item["name"] for item in ad8571_template.get("topology_candidates", [])}
    ad8571_templates = {item["name"] for item in ad8571_template.get("opamp_templates", [])}
    ad8571_block_refs = {item["ref"] for item in ad8571_template.get("blocks", [])}

    assert {"capacitive_load_driver", "strain_gage_frontend", "thermocouple_frontend"}.issubset(ad8571_topologies)
    assert {"non_inverting_gain_stage", "inverting_gain_stage", "capacitive_load_driver", "strain_gage_frontend", "thermocouple_frontend", "current_sense_frontend"}.issubset(ad8571_templates)
    assert ad8571_template["default_opamp_template"] == "capacitive_load_driver"
    assert {"RSNUB", "CSNUB", "XBRIDGE1", "XTC1", "XCJ1"}.issubset(ad8571_block_refs)
    assert ad8571_context["channel_count"] == 1
    assert ad8571_context["channel_units"][0]["package_bindings"] == {"IN-": "2", "IN+": "3", "OUT": "6"}
    assert ad8571_context["shared_power_pins"]["negative"][0]["pin"] == "4"
    assert ad8571_context["shared_power_pins"]["positive"][0]["pin"] == "7"
    assert ad8571_context["primary_signal_unit"] == "U1A"
    assert ad8571_context["supply_style"] == "single_supply"
    assert ad8571_default_template["power_strategy"]["reference_net"] == "VREF"
    assert any(item["symbol_pin"] == "U1A.OUT" and item["package_pin"] == "6" for item in ad8571_default_template["pin_bindings"])
    assert ad8571_default_template["sheet_instances"] == [
        {
            "instance_name": "primary_signal_path",
            "sheet_name": "A1_cap_load_driver",
            "opamp_unit": "U1A",
            "status": "default",
            "package_bindings": {"IN-": "2", "IN+": "3", "OUT": "6"},
        }
    ]
    assert "Suggested topologies" in ad8571_quickstart
    assert "L3 Templates" in ad8571_quickstart
    assert "Start here:" in ad8571_quickstart


def test_opamp_bundle_export_generalizes_to_other_families(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "SGM8554",
            "--device",
            "ADA4522-1/ADA4522-2/ADA4522-4",
            "--device",
            "LMV321, LMV358, LMV324",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    sgm8554_template = json.loads((output_dir / "SGM8554" / "L3_module_template.json").read_text(encoding="utf-8"))
    sgm8554_context = sgm8554_template["opamp_device_context"]
    assert sgm8554_context["channel_count"] == 4
    assert {item["symbol_unit"] for item in sgm8554_context["channel_units"]} == {"U1A", "U1B", "U1C", "U1D"}
    assert sgm8554_context["shared_power_pins"]["positive"][0]["pin"] == "4"
    assert sgm8554_context["shared_power_pins"]["negative"][0]["pin"] == "11"

    ada4522_template = json.loads((output_dir / "ADA4522-1_ADA4522-2_ADA4522-4" / "L3_module_template.json").read_text(encoding="utf-8"))
    ada4522_context = ada4522_template["opamp_device_context"]
    assert ada4522_context["shared_power_pins"]["positive"][0]["name"] == "V+"
    assert ada4522_context["shared_power_pins"]["positive"][0]["pin"] == "7"
    assert any(item["package_name"].startswith("14-lead") and item["channel_count"] == 4 for item in ada4522_context["package_variants"])

    lmv_template = json.loads((output_dir / "LMV321_LMV358_LMV324" / "L3_module_template.json").read_text(encoding="utf-8"))
    lmv_quickstart = (output_dir / "LMV321_LMV358_LMV324" / "L2_quickstart.md").read_text(encoding="utf-8")
    lmv_context = lmv_template["opamp_device_context"]
    assert lmv_context["shared_power_pins"]["negative"][0]["pin"] == "2"
    assert any(item["package_name"] == "SO14/TSSOP14" and item["channel_count"] == 4 for item in lmv_context["package_variants"])
    assert "Alternate package variants" in lmv_quickstart


def test_decoder_bundle_export_builds_schematic_scaffold(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "TP2860",
            "--device",
            "MAX96718A",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    tp2860_dir = output_dir / "TP2860"
    tp2860_intent = json.loads((tp2860_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    tp2860_template = json.loads((tp2860_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    tp2860_quickstart = (tp2860_dir / "L2_quickstart.md").read_text(encoding="utf-8")
    tp2860_roles = {item["role"] for item in tp2860_intent["external_components"]}
    tp2860_nets = {item["name"] for item in tp2860_intent["starter_nets"]}

    assert tp2860_intent["decoder_device_context"]["preferred_package"] == "40L QFN"
    assert {"AVDD33", "AVDD12", "DVDD", "VDD_IO", "GND", "VIDEO_IN", "CSI2_TX", "REFCLK"}.issubset(tp2860_nets)
    assert {"rail_decoupling", "ac_coupling_capacitors", "clock_source_or_crystal", "csi_breakout"}.issubset(tp2860_roles)
    assert tp2860_template["default_decoder_template"] == "analog_video_decoder_to_csi"
    assert {item["name"] for item in tp2860_template["decoder_templates"]} == {"analog_video_decoder_to_csi"}
    assert "Decoder implementation notes" in tp2860_quickstart
    assert "Suggested interfaces" in tp2860_quickstart

    max_dir = output_dir / "MAX96718A"
    max_intent = json.loads((max_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    max_template = json.loads((max_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    max_quickstart = (max_dir / "L2_quickstart.md").read_text(encoding="utf-8")
    max_context = max_intent["decoder_device_context"]
    max_roles = {item["role"] for item in max_intent["external_components"]}

    assert len(max_context["serial_links"]) >= 4
    assert len(max_context["mipi_outputs"]) >= 2
    assert max_template["default_decoder_template"] == "serial_deserializer_to_csi"
    assert {item["name"] for item in max_template["decoder_templates"]} == {"serial_deserializer_to_csi"}
    assert {"rail_decoupling", "clock_source_or_crystal", "i2c_pullups", "configuration_straps", "reset_bias", "csi_breakout", "link_connector"}.issubset(max_roles)
    assert "Decoder implementation notes" in max_quickstart
    assert "Start here:" in max_quickstart


def test_ds90ub_bundle_export_supports_raw_pdf_and_parallel_outputs(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "DS90UB934TRGZRQ1",
            "--device",
            "DS90UB954TRGZRQ1",
            "--device",
            "DS90UB962WRTDTQ1",
            "--device",
            "DS90UB960WRTDRQ1",
            "--device",
            "DS90UB9702-Q1",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    ds934_dir = output_dir / "DS90UB934TRGZRQ1"
    ds934_intent = json.loads((ds934_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    ds934_template = json.loads((ds934_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    ds934_roles = {item["role"] for item in ds934_intent["external_components"]}
    ds934_nets = {item["name"] for item in ds934_intent["starter_nets"]}
    assert ds934_intent["datasheet_design_context"]["source_mode"] == "raw_pdf_scan"
    assert ds934_template["default_decoder_template"] == "serial_deserializer_to_parallel"
    assert {item["name"] for item in ds934_template["decoder_templates"]} == {"serial_deserializer_to_parallel"}
    assert {"SER_LINK", "PIX_OUT", "REFCLK"}.issubset(ds934_nets)
    assert {"pixel_breakout", "link_connector", "clock_source_or_crystal"}.issubset(ds934_roles)

    ds954_dir = output_dir / "DS90UB954TRGZRQ1"
    ds954_intent = json.loads((ds954_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    ds954_template = json.loads((ds954_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    ds954_roles = {item["role"] for item in ds954_intent["external_components"]}
    assert ds954_intent["datasheet_design_context"]["source_mode"] == "raw_pdf_scan"
    assert ds954_template["default_decoder_template"] == "serial_deserializer_to_csi"
    assert "serial_deserializer_to_csi" in {item["name"] for item in ds954_template["decoder_templates"]}
    assert {"csi_breakout", "link_connector", "poc_filter_network"}.issubset(ds954_roles)

    ds962_dir = output_dir / "DS90UB962WRTDTQ1"
    ds962_intent = json.loads((ds962_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    ds962_template = json.loads((ds962_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    assert ds962_intent["datasheet_design_context"]["source_mode"] == "raw_pdf_scan"
    assert ds962_template["default_decoder_template"] == "serial_deserializer_to_csi"

    ds960_dir = output_dir / "DS90UB960WRTDRQ1"
    ds960_intent = json.loads((ds960_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    ds960_template = json.loads((ds960_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    ds960_roles = {item["role"] for item in ds960_intent["external_components"]}
    assert ds960_intent["datasheet_design_context"]["source_mode"] == "raw_pdf_scan"
    assert ds960_template["default_decoder_template"] == "serial_deserializer_to_csi"
    assert {"link_connector", "csi_breakout", "poc_filter_network", "reset_bias"}.issubset(ds960_roles)

    ds9702_dir = output_dir / "DS90UB9702-Q1"
    ds9702_intent = json.loads((ds9702_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    ds9702_template = json.loads((ds9702_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    assert ds9702_intent["datasheet_design_context"]["source_mode"] == "raw_pdf_scan"
    assert ds9702_template["default_decoder_template"] == "serial_deserializer_to_csi"


def test_gowin_fpga_bundle_export_includes_customer_scenarios(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "GW5AT-60_UG225",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    bundle_dir = output_dir / "GW5AT-60_UG225"
    design_intent = json.loads((bundle_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    module_template = json.loads((bundle_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    quickstart = (bundle_dir / "L2_quickstart.md").read_text(encoding="utf-8")

    scenario_names = {item["name"] for item in design_intent.get("customer_scenarios", [])}
    role_names = {item["role"] for item in design_intent.get("external_components", [])}
    starter_nets = {item["name"] for item in design_intent.get("starter_nets", [])}
    template_names = {item["name"] for item in module_template.get("fpga_templates", [])}

    assert {"qspi_jtag_bringup", "mipi_camera_bridge", "lvds_io_expansion", "high_speed_link_bridge", "ddr_memory_interface"}.issubset(scenario_names)
    assert {"configuration_flash", "boot_mode_straps", "mipi_camera_connector", "lvds_io_connector", "high_speed_link_connector", "memory_connector_or_footprint", "reference_clock_source"}.issubset(role_names)
    assert {"CFG_SPI", "MIPI_CLK", "LVDS_IO", "REFCLK", "SERDES_RX", "DDR_DQ"}.issubset(starter_nets)
    assert {"qspi_jtag_bringup", "mipi_camera_bridge", "lvds_io_expansion", "high_speed_link_bridge", "ddr_memory_interface"}.issubset(template_names)
    assert module_template["default_fpga_template"] == "mipi_camera_bridge"
    assert set(design_intent.get("vendor_design_rules", {}).keys()) == {"power_rules", "config_rules", "clock_rules", "io_rules"}
    assert {item["title"] for item in design_intent.get("reference_design_assets", [])} == {"GW5AT schematic guide", "GW5AT-60 devboard reference"}
    assert "Customer scenarios" in quickstart
    assert "L3 Templates" in quickstart
    assert "Vendor design rules" in quickstart
    assert "Reference assets" in quickstart
    assert "CFGBVS" in quickstart
    assert "RECONFIG_N" in quickstart
    assert "gowin_gw5at_design_guide.md" in quickstart
    assert "gowin_gw5at60_devboard_ref.md" in quickstart
    assert "Start here:" in quickstart


def test_gowin_fpga_scenarios_generalize_across_other_families(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "GW5AR-25_UG256P",
            "--device",
            "GW5AS-25_UG256",
            "--device",
            "GW5AT-15_MG132",
            "--device",
            "GW5AT-138_FPG676A",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    gw5ar_template = json.loads((output_dir / "GW5AR-25_UG256P" / "L3_module_template.json").read_text(encoding="utf-8"))
    gw5as_template = json.loads((output_dir / "GW5AS-25_UG256" / "L3_module_template.json").read_text(encoding="utf-8"))
    gw5at15_template = json.loads((output_dir / "GW5AT-15_MG132" / "L3_module_template.json").read_text(encoding="utf-8"))
    gw5at138_intent = json.loads((output_dir / "GW5AT-138_FPG676A" / "L1_design_intent.json").read_text(encoding="utf-8"))
    gw5at138_template = json.loads((output_dir / "GW5AT-138_FPG676A" / "L3_module_template.json").read_text(encoding="utf-8"))

    assert gw5ar_template["default_fpga_template"] == "qspi_jtag_bringup"
    assert "ddr_memory_interface" in {item["name"] for item in gw5ar_template.get("fpga_templates", [])}
    assert gw5as_template["default_fpga_template"] == "qspi_jtag_bringup"
    assert "lvds_io_expansion" in {item["name"] for item in gw5as_template.get("fpga_templates", [])}
    assert gw5at15_template["default_fpga_template"] == "qspi_jtag_bringup"
    assert "mipi_camera_bridge" not in {item["name"] for item in gw5at15_template.get("fpga_templates", [])}
    assert gw5at138_template["default_fpga_template"] == "qspi_jtag_bringup"
    assert {item["name"] for item in gw5at138_template.get("fpga_templates", [])} >= {"lvds_io_expansion", "ddr_memory_interface"}
    assert {item["source_path"] for item in gw5at138_intent.get("reference_design_assets", [])} == {
        "data/sch_review_export/reference/gowin_gw5at_design_guide.md"
    }
