import json
import subprocess
import sys
from pathlib import Path

from scripts.export_design_bundle import _infer_mcu_traits


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
    adg706_manifest = json.loads((adg706_dir / "bundle_manifest.json").read_text(encoding="utf-8"))
    adg706_quickstart = (adg706_dir / "L2_quickstart.md").read_text(encoding="utf-8")
    adg706_roles = {item["role"] for item in adg706_intent["external_components"]}
    adg706_switch_template = next(item for item in adg706_template.get("switch_templates", []) if item["name"] == "addressable_analog_mux")
    adg706_source_pins = {pin["name"] for ref in adg706_switch_template.get("source_refs", []) for pin in ref.get("pins", [])}

    assert {"supply_decoupling", "address_source_or_straps", "enable_bias", "analog_channel_breakout"}.issubset(adg706_roles)
    assert "input_capacitor" not in adg706_roles
    assert adg706_template["default_switch_template"] == "addressable_analog_mux"
    assert "addressable_analog_mux" in {item["name"] for item in adg706_template.get("switch_templates", [])}
    assert adg706_intent["switch_device_context"]["source"] == "sch_review_export.packages.pins"
    assert adg706_intent["official_source_documents"][0]["path"] == "data/raw/datasheet_PDF/0130-06-00004_ADG706BRU.pdf"
    assert adg706_manifest["official_source_documents"][0]["path"] == "data/raw/datasheet_PDF/0130-06-00004_ADG706BRU.pdf"
    assert {"A0", "A1", "A2"}.issubset(adg706_source_pins)
    assert "Analog switch implementation notes" in adg706_quickstart
    assert "## Official source documents" in adg706_quickstart
    assert "data/raw/datasheet_PDF/0130-06-00004_ADG706BRU.pdf" in adg706_quickstart
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


def test_new_switch_family_bundle_exports(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "TS5A2053",
            "--device",
            "SN74CBT3251",
            "--device",
            "SN74CB3Q3125",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    ts5a_dir = output_dir / "TS5A2053"
    ts5a_intent = json.loads((ts5a_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    ts5a_template = json.loads((ts5a_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    ts5a_quickstart = (ts5a_dir / "L2_quickstart.md").read_text(encoding="utf-8")
    ts5a_nets = {item["name"] for item in ts5a_intent["starter_nets"]}

    assert ts5a_template["default_switch_template"] == "spdt_analog_switch"
    assert {"V+", "GND", "EN", "SW_COM", "SW_NO", "SW_NC"}.issubset(ts5a_nets)
    assert ts5a_intent["official_source_documents"][0]["path"] == "data/raw/datasheet_PDF/0130-06-00007_TS5A2053DCTR.pdf"
    assert "SPDT Analog Switch" in ts5a_quickstart

    cbt_dir = output_dir / "SN74CBT3251"
    cbt_intent = json.loads((cbt_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    cbt_template = json.loads((cbt_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    cbt_nets = {item["name"] for item in cbt_intent["starter_nets"]}

    assert cbt_template["default_interface_switch_template"] == "bus_mux_bridge"
    assert {"VCC", "GND", "SEL", "OE_N", "BUS_COM", "BUS_CH"}.issubset(cbt_nets)
    cbt_bridge = next(item for item in cbt_template.get("interface_switch_templates", []) if item["name"] == "bus_mux_bridge")
    cbt_source_pins = {pin["name"] for ref in cbt_bridge.get("source_refs", []) for pin in ref.get("pins", [])}
    assert {"A", "B1", "S0", "S1", "S2", "OE"}.issubset(cbt_source_pins)

    cb3_dir = output_dir / "SN74CB3Q3125"
    cb3_intent = json.loads((cb3_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    cb3_template = json.loads((cb3_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    cb3_nets = {item["name"] for item in cb3_intent["starter_nets"]}

    assert cb3_template["default_interface_switch_template"] == "bus_switch_bridge"
    assert {"VCC", "GND", "BUS_A", "BUS_B"}.issubset(cb3_nets)


def test_tmux111x_family_bundle_export_uses_family_mpn_and_direct_select_bank(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "TMUX1111/TMUX1112/TMUX1113",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    tmux_dir = output_dir / "TMUX1111_TMUX1112_TMUX1113"
    tmux_intent = json.loads((tmux_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    tmux_template = json.loads((tmux_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    tmux_manifest = json.loads((tmux_dir / "bundle_manifest.json").read_text(encoding="utf-8"))
    tmux_quickstart = (tmux_dir / "L2_quickstart.md").read_text(encoding="utf-8")
    tmux_nets = {item["name"] for item in tmux_intent["starter_nets"]}

    assert tmux_template["default_switch_template"] == "direct_control_switch_bank"
    assert {"VDD", "GND", "SEL_BANK", "SIG_PORT_A", "SIG_PORT_B"}.issubset(tmux_nets)
    assert tmux_intent["switch_device_context"]["supports_direct_select_bank"] is True
    assert tmux_intent["official_source_documents"][0]["path"] == "data/raw/datasheet_PDF/0130-06-00016_TMUX1112RSVR.pdf"
    assert tmux_manifest["official_source_documents"][0]["path"] == "data/raw/datasheet_PDF/0130-06-00016_TMUX1112RSVR.pdf"
    tmux_switch = next(item for item in tmux_template.get("switch_templates", []) if item["name"] == "direct_control_switch_bank")
    tmux_source_pins = {pin["name"] for ref in tmux_switch.get("source_refs", []) for pin in ref.get("pins", [])}
    assert {"SEL1", "SEL2", "SEL3", "SEL4", "S1", "D1"}.issubset(tmux_source_pins)
    assert "Control modes: `direct_select_bank`" in tmux_quickstart


def test_interface_switch_bundle_export_includes_high_speed_templates(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "FUSB340",
            "--device",
            "TC7USB40MU",
            "--device",
            "TC7PCI3212MT__TC7PCI3215MT",
            "--device",
            "FST3125",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    fusb_dir = output_dir / "FUSB340"
    fusb_intent = json.loads((fusb_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    fusb_template = json.loads((fusb_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    fusb_quickstart = (fusb_dir / "L2_quickstart.md").read_text(encoding="utf-8")
    fusb_roles = {item["role"] for item in fusb_intent["external_components"]}
    fusb_nets = {item["name"] for item in fusb_intent["starter_nets"]}

    assert {"supply_decoupling", "select_bias", "enable_bias", "esd_review", "ac_coupling_review", "signal_path_breakout"}.issubset(fusb_roles)
    assert {"SS_TXRX_COM", "SS_PORT_A", "SS_PORT_B", "SEL", "OE_N"}.issubset(fusb_nets)
    assert fusb_template["default_interface_switch_template"] == "superspeed_data_switch"
    assert "superspeed_data_switch" in {item["name"] for item in fusb_template.get("interface_switch_templates", [])}
    assert "Interface switch implementation notes" in fusb_quickstart

    usb2_dir = output_dir / "TC7USB40MU"
    usb2_intent = json.loads((usb2_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    usb2_template = json.loads((usb2_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    usb2_roles = {item["role"] for item in usb2_intent["external_components"]}

    assert {"supply_decoupling", "select_bias", "enable_bias", "esd_review", "signal_path_breakout"}.issubset(usb2_roles)
    assert usb2_template["default_interface_switch_template"] == "usb2_data_switch"

    pcie_dir = output_dir / "TC7PCI3212MT_TC7PCI3215MT"
    pcie_intent = json.loads((pcie_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    pcie_template = json.loads((pcie_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    pcie_roles = {item["role"] for item in pcie_intent["external_components"]}
    pcie_nets = {item["name"] for item in pcie_intent["starter_nets"]}

    assert {"supply_decoupling", "select_bias", "enable_bias", "ac_coupling_review", "signal_path_breakout"}.issubset(pcie_roles)
    assert {"PCIE_COM", "PCIE_PORT_A", "PCIE_PORT_B", "SEL", "OE_N"}.issubset(pcie_nets)
    assert pcie_template["default_interface_switch_template"] == "pcie_diff_switch"

    fst_dir = output_dir / "FST3125"
    fst_intent = json.loads((fst_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    fst_template = json.loads((fst_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    fst_manifest = json.loads((fst_dir / "bundle_manifest.json").read_text(encoding="utf-8"))
    fst_quickstart = (fst_dir / "L2_quickstart.md").read_text(encoding="utf-8")
    fst_nets = {item["name"] for item in fst_intent["starter_nets"]}

    assert {"BUS_A", "BUS_B", "OE_N"}.issubset(fst_nets)
    assert fst_intent["official_source_documents"][0]["path"] == "data/raw/datasheet_PDF/0130-06-00006_FST3125MTCX.pdf"
    assert fst_manifest["official_source_documents"][0]["path"] == "data/raw/datasheet_PDF/0130-06-00006_FST3125MTCX.pdf"
    assert fst_template["default_interface_switch_template"] == "bus_switch_bridge"
    assert "bus_switch_bridge" in {item["name"] for item in fst_template.get("interface_switch_templates", [])}
    fst_bridge = next(item for item in fst_template.get("interface_switch_templates", []) if item["name"] == "bus_switch_bridge")
    fst_source_pins = {pin["name"] for ref in fst_bridge.get("source_refs", []) for pin in ref.get("pins", [])}
    assert {"1A", "1B", "2A", "2B"}.intersection(fst_source_pins)
    assert "## Official source documents" in fst_quickstart
    assert "Interface kind: `bus` topology=`bus_switch`" in fst_quickstart


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
    assert {"configuration_flash", "boot_mode_straps", "mipi_camera_connector", "lvds_io_connector", "high_speed_link_connector", "memory_connector_or_footprint", "reference_clock_source", "pcie_link_boundary", "pcie_refclk_source_or_buffer", "custom_serdes_breakout"}.issubset(role_names)
    assert {"CFG_SPI", "MIPI_CLK", "LVDS_IO", "REFCLK", "SERDES_RX", "DDR_DQ", "PCIE_REFCLK", "PCIE_TXRX", "SERDES_USER_REFCLK", "HS_Q0_RX", "HS_Q0_TX", "HS_Q0_REFCLK"}.issubset(starter_nets)
    hs_context = design_intent.get("high_speed_semantic_context", {})
    assert hs_context.get("source") == "sch_review_export.constraint_blocks.refclk_requirements"
    assert "PCIe 3.0" in hs_context.get("protocol_candidates", [])
    hs_scenario = next(item for item in design_intent.get("customer_scenarios", []) if item["name"] == "high_speed_link_bridge")
    assert hs_scenario.get("source") == "semantic_export"
    assert "Q0" in hs_scenario.get("lane_group_refs", [])
    hs_template = next(item for item in module_template.get("fpga_templates", []) if item["name"] == "high_speed_link_bridge")
    assert "PCIe 3.0" in hs_template.get("protocol_candidates", [])
    assert "Q0" in hs_template.get("lane_group_refs", [])
    assert {"JPCIE", "XPCIE", "JHSUSR"}.issubset(set(hs_template.get("blocks", [])))
    assert {"PCIE_REFCLK", "PCIE_TXRX", "SERDES_USER_REFCLK"}.issubset(set(hs_template.get("nets", [])))
    checklist_text = "\n".join(hs_template.get("checklist", []))
    assert "PCIe-capable lane-group ownership" in checklist_text
    assert "custom SerDes lane-group ownership" in checklist_text
    assert module_template.get("high_speed_semantic_context", {}).get("protocol_candidates")
    assert {"qspi_jtag_bringup", "mipi_camera_bridge", "lvds_io_expansion", "high_speed_link_bridge", "ddr_memory_interface"}.issubset(template_names)
    assert module_template["default_fpga_template"] == "mipi_camera_bridge"
    assert set(design_intent.get("vendor_design_rules", {}).keys()) == {"power_rules", "config_rules", "clock_rules", "io_rules"}
    assert {item["title"] for item in design_intent.get("reference_design_assets", [])} == {"GW5AT schematic guide", "GW5AT-60 devboard reference"}
    assert "Customer scenarios" in quickstart
    assert "High-speed semantics" in quickstart
    assert "Lane group `Q0`" in quickstart
    assert "L3 Templates" in quickstart
    assert "Vendor design rules" in quickstart
    assert "Reference assets" in quickstart
    assert "JTAGSEL" in quickstart
    assert "MODE[2:0]" in quickstart
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
    assert gw5at138_template["default_fpga_template"] == "high_speed_link_bridge"
    assert {item["name"] for item in gw5at138_template.get("fpga_templates", [])} >= {"lvds_io_expansion", "ddr_memory_interface"}
    assert {item["source_path"] for item in gw5at138_intent.get("reference_design_assets", [])} == {
        "data/sch_review_export/reference/gowin_gw5at_design_guide.md"
    }



def test_amd_fpga_bundle_export_uses_semantic_high_speed_context(tmp_path):
    output_dir = tmp_path / "bundles"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--device",
            "XCKU3P_FFVA676",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    bundle_dir = output_dir / "XCKU3P_FFVA676"
    design_intent = json.loads((bundle_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    module_template = json.loads((bundle_dir / "L3_module_template.json").read_text(encoding="utf-8"))

    hs_context = design_intent.get("high_speed_semantic_context", {})
    scenario = next(item for item in design_intent.get("customer_scenarios", []) if item["name"] == "high_speed_link_bridge")
    roles = {item["role"] for item in design_intent.get("external_components", [])}
    starter_nets = {item["name"] for item in design_intent.get("starter_nets", [])}

    assert hs_context.get("source") == "sch_review_export.constraint_blocks.refclk_requirements"
    assert "PCIe 4.0" in hs_context.get("protocol_candidates", [])
    assert "224" in {item.get("group_id") for item in hs_context.get("lane_groups", [])}
    assert scenario.get("source") == "semantic_export"
    assert "224" in scenario.get("lane_group_refs", [])
    assert "PCIe 4.0" in scenario.get("protocol_candidates", [])
    assert module_template["default_fpga_template"] == "high_speed_link_bridge"
    hs_template = next(item for item in module_template.get("fpga_templates", []) if item["name"] == "high_speed_link_bridge")
    assert "224" in hs_template.get("lane_group_refs", [])
    assert "PCIe 4.0" in hs_template.get("protocol_candidates", [])
    assert {"JPCIE", "XPCIE", "JETH/SFP/UETH"}.issubset(set(hs_template.get("blocks", [])))
    assert {"PCIE_REFCLK", "PCIE_TXRX", "ETH_REFCLK", "ETH_SERDES"}.issubset(set(hs_template.get("nets", [])))
    connection_notes = "\n".join(item.get("note", "") for item in hs_template.get("connections", []))
    checklist_text = "\n".join(hs_template.get("checklist", []))
    assert "exported protocol candidates" in checklist_text
    assert "exported Ethernet reference-clock candidates" in connection_notes
    assert module_template.get("high_speed_semantic_context", {}).get("lane_groups")
    assert {"pcie_link_boundary", "pcie_refclk_source_or_buffer", "ethernet_serdes_attachment"}.issubset(roles)
    assert {"PCIE_REFCLK", "PCIE_TXRX", "ETH_REFCLK", "ETH_SERDES", "HS_224_RX", "HS_224_TX", "HS_224_REFCLK"}.issubset(starter_nets)


def test_gowin_bundle_rules_are_family_specific(tmp_path):
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
    config_rules = "\n".join(design_intent["vendor_design_rules"]["config_rules"])

    assert "CFGBVS" not in config_rules
    assert "PUDC_B" not in config_rules
    assert "MODE[2:0]" in config_rules
    assert "JTAGSEL" in config_rules


def test_extract_gw1n_dc_supports_combined_datasheet():
    from pathlib import Path
    from scripts.extract_gowin_dc import extract_gowin_dc

    result = extract_gowin_dc(Path("data/raw/datasheet_PDF/0130-08-00028_GW1N-LV2QN48HC7.pdf"))

    assert result["device"] == "GW1N"
    assert len(result["absolute_maximum_ratings"]) >= 3
    assert len(result["recommended_operating"]) >= 3
    assert any(item.get("standard") == "LVCMOS33" and item.get("vcco") == 3.3 for item in result["io_standards"])
    assert any(item.get("standard") == "LVCMOS12" and item.get("vcco") == 1.2 for item in result["io_standards"])



def test_stm32_mcu_bundle_export_includes_minimum_system_templates(tmp_path):
    input_dir = tmp_path / "exports"
    output_dir = tmp_path / "bundles"
    input_dir.mkdir()
    (tmp_path / "extracted").mkdir()
    (tmp_path / "pdfs").mkdir()

    device = {
        "_schema": "sch-review-device/1.1",
        "_type": "normal_ic",
        "mpn": "STM32F401CBU6",
        "manufacturer": "STMicroelectronics",
        "category": "Other",
        "description": "STM32 MCU",
        "packages": {
            "UFQFPN48": {
                "pin_count": 48,
                "pins": {
                    "1": {"name": "VBAT", "direction": "POWER_IN", "signal_type": "POWER", "description": "Backup supply", "unused_treatment": None},
                    "7": {"name": "BOOT0", "direction": "INPUT", "signal_type": "DIGITAL", "description": "Boot configuration", "unused_treatment": None},
                    "8": {"name": "PF0-OSC_IN", "direction": "INPUT", "signal_type": "DIGITAL", "description": "HSE oscillator input", "unused_treatment": None},
                    "9": {"name": "PF1-OSC_OUT", "direction": "OUTPUT", "signal_type": "DIGITAL", "description": "HSE oscillator output", "unused_treatment": None},
                    "14": {"name": "VSS", "direction": "POWER_IN", "signal_type": "POWER", "description": "Ground", "unused_treatment": None},
                    "15": {"name": "VDD", "direction": "POWER_IN", "signal_type": "POWER", "description": "Digital supply", "unused_treatment": None},
                    "21": {"name": "PA13-SWDIO", "direction": "BIDIR", "signal_type": "DIGITAL", "description": "Serial wire debug data", "unused_treatment": None},
                    "22": {"name": "PA14-SWCLK", "direction": "INPUT", "signal_type": "DIGITAL", "description": "Serial wire debug clock", "unused_treatment": None},
                    "23": {"name": "PA15-SWO", "direction": "OUTPUT", "signal_type": "DIGITAL", "description": "Trace output", "unused_treatment": None},
                    "24": {"name": "NRST", "direction": "INPUT", "signal_type": "DIGITAL", "description": "System reset", "unused_treatment": None},
                    "25": {"name": "VDDA", "direction": "POWER_IN", "signal_type": "POWER", "description": "Analog supply", "unused_treatment": None},
                    "26": {"name": "VSSA", "direction": "POWER_IN", "signal_type": "POWER", "description": "Analog ground", "unused_treatment": None},
                    "27": {"name": "VCAP1", "direction": "POWER_IN", "signal_type": "POWER", "description": "Internal regulator capacitor", "unused_treatment": None},
                    "33": {"name": "PA11-USB_DM", "direction": "BIDIR", "signal_type": "DIGITAL", "description": "USB D-", "unused_treatment": None},
                    "34": {"name": "PA12-USB_DP", "direction": "BIDIR", "signal_type": "DIGITAL", "description": "USB D+", "unused_treatment": None}
                }
            }
        },
        "absolute_maximum_ratings": {},
        "electrical_parameters": {},
        "drc_hints": [],
        "thermal": {}
    }

    (input_dir / "STM32F401CBU6.json").write_text(json.dumps(device, ensure_ascii=False, indent=2), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--input-dir",
            str(input_dir),
            "--extracted-dir",
            str(tmp_path / "extracted"),
            "--pdf-dir",
            str(tmp_path / "pdfs"),
            "--device",
            "STM32F401CBU6",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    bundle_dir = output_dir / "STM32F401CBU6"
    design_intent = json.loads((bundle_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    module_template = json.loads((bundle_dir / "L3_module_template.json").read_text(encoding="utf-8"))
    quickstart = (bundle_dir / "L2_quickstart.md").read_text(encoding="utf-8")

    roles = {item["role"] for item in design_intent["external_components"]}
    starter_nets = {item["name"] for item in design_intent["starter_nets"]}
    template_names = {item["name"] for item in module_template.get("mcu_templates", [])}

    assert {"supply_decoupling", "swd_header", "reset_bias_or_button", "boot_mode_straps", "hse_clock_source", "vcap_stabilizer", "analog_rail_filter", "backup_supply_source", "usb_connector_or_esd"}.issubset(roles)
    assert {"VDD", "VSS", "NRST", "SWDIO", "SWCLK", "BOOT0", "HSE_IN", "HSE_OUT", "VDDA", "VSSA", "VCAP", "VBAT", "USB_DP", "USB_DM", "VBUS"}.issubset(starter_nets)
    assert module_template["default_mcu_template"] == "stm32_minimum_system"
    assert {"stm32_minimum_system", "stm32_usb_device"}.issubset(template_names)
    assert "MCU implementation notes" in quickstart
    assert "MCU templates" in quickstart



def test_bundle_export_tolerates_string_constraint_entries(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "bundles"
    input_dir.mkdir()

    device = {
        "_schema": "sch-review-device/1.1",
        "_type": "normal_ic",
        "_layers": ["L0_skeleton", "L1_electrical"],
        "mpn": "STRING-CONSTRAINT-IC",
        "manufacturer": "TestVendor",
        "category": "LDO",
        "description": "Synthetic device with legacy string constraint entries",
        "packages": {
            "SOT23-5": {
                "pin_count": 5,
                "pins": {
                    "1": {"name": "IN", "direction": "POWER_IN", "signal_type": "POWER", "description": "Input supply", "unused_treatment": None},
                    "2": {"name": "GND", "direction": "POWER_IN", "signal_type": "POWER", "description": "Ground", "unused_treatment": None},
                    "3": {"name": "EN", "direction": "INPUT", "signal_type": "DIGITAL", "description": "Enable", "unused_treatment": None},
                    "4": {"name": "NC", "direction": "INPUT", "signal_type": "NC", "description": "No connect", "unused_treatment": None},
                    "5": {"name": "OUT", "direction": "POWER_OUT", "signal_type": "POWER", "description": "Regulated output", "unused_treatment": None}
                }
            }
        },
        "absolute_maximum_ratings": {
            "VIN": {
                "parameter": "Input voltage",
                "min": -0.3,
                "max": 6.0,
                "unit": "V",
                "conditions": None
            },
            "legacy_note": "Do not exceed absolute maximum conditions."
        },
        "electrical_parameters": {
            "VOUT": {
                "parameter": "Output voltage",
                "min": 1.8,
                "typ": 1.8,
                "max": 1.8,
                "unit": "V",
                "conditions": None
            },
            "legacy_condition": "Stable with 1uF output capacitor."
        },
        "drc_hints": {
            "vin_abs_max": {"max": 6.0, "unit": "V"},
            "vout_nominal": {"typ": 1.8, "unit": "V"}
        },
        "thermal": {}
    }

    (input_dir / "STRING-CONSTRAINT-IC.json").write_text(json.dumps(device, ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_design_bundle.py",
            "--input-dir",
            str(input_dir),
            "--extracted-dir",
            str(tmp_path / "extracted"),
            "--pdf-dir",
            str(tmp_path / "pdfs"),
            "--device",
            "STRING-CONSTRAINT-IC",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "generated" in result.stdout
    bundle_dir = output_dir / "STRING-CONSTRAINT-IC"
    design_intent = json.loads((bundle_dir / "L1_design_intent.json").read_text(encoding="utf-8"))
    assert design_intent["device_ref"]["mpn"] == "STRING-CONSTRAINT-IC"
    assert bundle_dir.joinpath("L2_quickstart.md").exists()



def test_infer_mcu_traits_separates_hse_and_lse_pins():
    device = {
        "mpn": "STM32H745xI/G",
        "manufacturer": "STMicroelectronics",
        "packages": {
            "LQFP144": {
                "pin_count": 4,
                "pins": {
                    "10": {"name": "PC14-OSC32_IN", "description": "32.768 kHz crystal oscillator input", "direction": "BIDIRECTIONAL", "signal_type": "ANALOG"},
                    "11": {"name": "PC15-OSC32_OUT", "description": "32.768 kHz crystal oscillator output", "direction": "BIDIRECTIONAL", "signal_type": "ANALOG"},
                    "25": {"name": "PH0-OSC_IN", "description": "High-speed external crystal oscillator input", "direction": "BIDIRECTIONAL", "signal_type": "ANALOG"},
                    "26": {"name": "PH1-OSC_OUT", "description": "High-speed external crystal oscillator output", "direction": "BIDIRECTIONAL", "signal_type": "ANALOG"},
                },
            }
        },
    }

    traits = _infer_mcu_traits(device, {"control_inputs": []})

    assert {item["name"] for item in traits["hse_pins"]} == {"PH0-OSC_IN", "PH1-OSC_OUT"}
    assert {item["name"] for item in traits["lse_pins"]} == {"PC14-OSC32_IN", "PC15-OSC32_OUT"}
