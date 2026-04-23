from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

try:
    from scripts.device_export_view import normalize_normal_ic_export
except ImportError:
    from device_export_view import normalize_normal_ic_export


def collect_normal_ic_constraints(
    device: dict,
    datasheet_design_context: dict | None,
    *,
    best_constraint_match: Callable[..., dict | None],
) -> dict:
    device = normalize_normal_ic_export(device)
    abs_max = device.get("absolute_maximum_ratings", {})
    electrical = device.get("electrical_parameters", {})

    spec_map = {
        "vin_abs_max": {
            "source_kind": "absolute_maximum_ratings",
            "source": abs_max,
            "include": (r"^VIN\b", r"^VCC\b", r"^VDD\b", r"^VS\b", r"supply voltage", r"input voltage range"),
            "exclude": (r"leakage", r"current", r"en pin", r"common mode", r"differential input"),
            "prefer": (r"supply voltage", r"input voltage range"),
            "prefer_keys": ("VIN", "VCC", "VDD", "VS"),
            "unit_allow": ("V",),
        },
        "vin_operating": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"\bVIN\b", r"input voltage", r"supply voltage"),
            "exclude": (r"uvlo", r"threshold", r"leakage", r"input current", r"en pin", r"high level", r"low level", r"logic", r"mode pin", r"fsel", r"\bVEN\b"),
            "prefer": (r"^VIN\b", r"input voltage range", r"^input voltage$"),
            "prefer_keys": ("VIN",),
            "unit_allow": ("V",),
        },
        "vout_range": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"\bVOUT\b", r"output voltage"),
            "exclude": (r"threshold", r"power good", r"tolerance", r"accuracy", r"noise", r"\bhigh\b", r"\blow\b", r"monitor", r"feedback"),
            "prefer": (r"output voltage range", r"^VOUT\b"),
            "prefer_keys": ("VOUT",),
            "unit_allow": ("V",),
        },
        "feedback_reference": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"\bVFB\b", r"feedback voltage"),
            "exclude": (r"accuracy", r"leakage"),
            "prefer": (r"^feedback voltage$", r"^VFB\b"),
            "prefer_keys": ("VFB",),
            "unit_allow": ("V",),
        },
        "iout_max": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"\bILOAD\b", r"load current", r"output current", r"maximum load current"),
            "exclude": (r"quiescent", r"leakage", r"input current", r"ground current", r"noise", r"transient"),
            "prefer": (r"maximum load current", r"^load current$", r"^ILOAD\b"),
            "prefer_keys": ("ILOAD", "IOUT"),
            "unit_allow": ("A", "mA"),
        },
        "current_limit": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"current limit", r"short-circuit current", r"\bILIM"),
            "exclude": (r"quiescent", r"leakage", r"threshold hysteresis"),
            "prefer": (r"short-circuit current limit", r"current limit", r"^ILIM"),
            "prefer_keys": ("ILIM", "ISC"),
            "unit_allow": ("A", "mA"),
        },
        "fsw": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"switch.*freq", r"oscillat.*freq", r"\bFSW\b", r"\bFOSC\b"),
            "prefer": (r"switching frequency", r"oscillator frequency"),
            "prefer_keys": ("FSW", "FOSC"),
            "unit_allow": ("kHz", "MHz", "Hz"),
        },
        "uvlo": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"UVLO", r"undervoltage"),
            "prefer": (r"undervoltage lockout", r"\(rising\)"),
            "prefer_keys": ("VUVLO", "UVLO"),
            "unit_allow": ("V",),
        },
        "thermal_shutdown": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"thermal.*shut", r"over.?temp", r"\bTSD\b"),
            "prefer": (r"thermal shutdown",),
        },
        "quiescent_current": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"quiescent current", r"\bIQ\b"),
            "exclude": (r"disabled", r"shutdown current"),
            "prefer": (r"^quiescent current$", r"operating quiescent current"),
            "prefer_keys": ("IQ",),
        },
        "dropout_voltage": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"dropout voltage", r"\bVDROPOUT\b"),
            "prefer": (r"dropout voltage",),
            "prefer_keys": ("VDROPOUT",),
            "unit_allow": ("V", "mV"),
        },
        "common_mode_range": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"common mode voltage range", r"\bVICR\b", r"\bVCM\b"),
            "exclude": (r"rejection",),
            "prefer": (r"common mode voltage range", r"\bVICR\b"),
            "prefer_keys": ("VICR", "VCM"),
            "unit_allow": ("V",),
        },
        "gain_bandwidth": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"gain bandwidth", r"gain bandwidth product", r"\bGBP\b", r"unity gain bandwidth"),
            "prefer": (r"gain bandwidth", r"gain bandwidth product", r"\bGBP\b"),
            "prefer_keys": ("GBP",),
            "unit_allow": ("MHz", "kHz"),
        },
        "slew_rate": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"slew rate", r"\bSR\b"),
            "prefer": (r"slew rate", r"\bSR\b"),
            "prefer_keys": ("SR",),
        },
        "supply_current": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"supply current", r"power supply current", r"\bICC\b", r"\bISY\b"),
            "exclude": (r"shutdown", r"disabled"),
            "prefer": (r"supply current", r"power supply current", r"per amplifier"),
            "prefer_keys": ("ICC", "ISY"),
        },
        "output_capacitance": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"output capacitance", r"\bCOUT\b", r"capacitance for stability"),
            "exclude": (r"input capacitance",),
            "prefer": (r"output capacitance", r"capacitance for stability"),
            "prefer_keys": ("COUT",),
            "unit_allow": ("pF", "nF", "µF", "μF", "uF", "mF"),
        },
        "output_cap_esr": {
            "source_kind": "electrical_parameters",
            "source": electrical,
            "include": (r"\bESR\b", r"capacitance ESR"),
            "prefer": (r"output/input capacitance esr", r"\bESR\b"),
            "prefer_keys": ("ESR",),
            "unit_allow": ("Ω", "mΩ", "kΩ"),
        },
    }

    collected = {}
    for name, spec in spec_map.items():
        match = best_constraint_match(
            spec["source_kind"],
            spec["source"],
            include=spec["include"],
            exclude=spec.get("exclude", ()),
            prefer=spec.get("prefer", ()),
            prefer_keys=spec.get("prefer_keys", ()),
            unit_allow=spec.get("unit_allow", ()),
        )
        if match:
            collected[name] = match

    datasheet_design_context = datasheet_design_context or {}
    range_map = {
        "VIN": "vin_operating",
        "VOUT": "vout_range",
        "IOUT": "iout_max",
        "FSW": "fsw",
        "FOSC": "fsw",
        "UVLO": "uvlo",
    }
    for hint in datasheet_design_context.get("design_range_hints", []):
        target = range_map.get((hint.get("name") or "").upper())
        if not target or target in collected:
            continue
        collected[target] = {
            "source_kind": "datasheet_range_hint",
            "source_key": hint.get("name"),
            "source_page": hint.get("source_page"),
            "parameter": f"{hint.get('name')} range",
            "min": hint.get("min"),
            "typ": None,
            "max": hint.get("max"),
            "unit": hint.get("unit"),
            "conditions": hint.get("snippet"),
        }
    return collected


@dataclass(frozen=True)
class NormalIcBundleDeps:
    pick_preferred_package: Callable[[dict], str | None]
    group_normal_ic_pins: Callable[[dict, str | None], tuple[dict, list]]
    infer_mcu_traits: Callable[[dict, dict], dict | None]
    datasheet_component_entries: Callable[[dict], list[dict]]
    is_decoder_like: Callable[[dict], bool]
    infer_decoder_traits: Callable[[dict, dict], dict]
    decoder_external_components: Callable[[dict], list[dict]]
    is_interface_switch_like: Callable[[dict], bool]
    infer_interface_switch_traits: Callable[[dict], dict]
    interface_switch_external_components: Callable[[dict], list[dict]]
    is_signal_switch_like: Callable[[dict], bool]
    infer_switch_traits: Callable[[dict], dict]
    switch_external_components: Callable[[dict], list[dict]]
    mcu_external_components: Callable[[dict], list[dict]]
    normal_ic_external_components: Callable[[dict, dict], list[dict]]
    decoder_starter_nets: Callable[[dict], list[dict]]
    interface_switch_starter_nets: Callable[[dict], list[dict]]
    switch_starter_nets: Callable[[dict], list[dict]]
    mcu_starter_nets: Callable[[dict], list[dict]]
    collect_constraints: Callable[[dict, dict | None], dict]


@dataclass(frozen=True)
class NormalIcModuleTemplateDeps:
    sanitize_name: Callable[[str], str]
    append_net_once: Callable[[list[dict], str, str], None]
    append_block_once: Callable[..., None]
    infer_opamp_traits: Callable[[dict, dict], dict]
    opamp_topology_candidates: Callable[[dict], list[dict]]
    opamp_standard_templates: Callable[[dict, dict, list[dict]], list[dict]]
    choose_default_opamp_template: Callable[[list[dict], list[dict]], str | None]
    decoder_topology_candidates: Callable[[dict], list[dict]]
    decoder_standard_templates: Callable[[dict, dict, list[dict]], list[dict]]
    choose_default_decoder_template: Callable[[list[dict], list[dict]], str | None]
    interface_switch_standard_templates: Callable[[dict, dict], list[dict]]
    choose_default_interface_switch_template: Callable[[list[dict]], str | None]
    switch_standard_templates: Callable[[dict, dict], list[dict]]
    choose_default_switch_template: Callable[[list[dict]], str | None]
    mcu_standard_templates: Callable[[dict, dict], list[dict]]
    choose_default_mcu_template: Callable[[list[dict]], str | None]


def build_normal_ic_design_intent(
    device: dict,
    datasheet_design_context: dict | None,
    *,
    bundle_schema: str,
    deps: NormalIcBundleDeps,
) -> dict:
    device = normalize_normal_ic_export(device)
    preferred_package = deps.pick_preferred_package(device)
    pin_groups, attention_items = deps.group_normal_ic_pins(device, preferred_package)
    datasheet_design_context = datasheet_design_context or {}
    constraints = deps.collect_constraints(device, datasheet_design_context)
    category = (device.get("category") or "").lower()
    decoder_device_context = None
    interface_switch_device_context = None
    switch_device_context = None
    mcu_device_context = deps.infer_mcu_traits(device, pin_groups, datasheet_context=datasheet_design_context)

    datasheet_components = deps.datasheet_component_entries(datasheet_design_context)
    if deps.is_decoder_like(device):
        decoder_device_context = deps.infer_decoder_traits(device, pin_groups, datasheet_context=datasheet_design_context)
        external_components = deps.decoder_external_components(decoder_device_context)
        noisy_roles = {
            "inductor",
            "feedback_divider",
            "bootstrap_capacitor",
            "current_limit_resistor",
            "dvdt_capacitor",
            "uvlo_divider",
            "ovp_divider",
            "gain_resistor",
            "sense_resistor",
            "snubber_capacitor",
            "snubber_resistor",
            "filter_network",
        }
        datasheet_components = [item for item in datasheet_components if item.get("role") not in noisy_roles]
    elif deps.is_interface_switch_like(device):
        interface_switch_device_context = deps.infer_interface_switch_traits(device, datasheet_context=datasheet_design_context)
        external_components = deps.interface_switch_external_components(interface_switch_device_context)
        noisy_roles = {
            "input_capacitor",
            "output_capacitor",
            "snubber_capacitor",
            "snubber_resistor",
            "filter_network",
        }
        datasheet_components = [item for item in datasheet_components if item.get("role") not in noisy_roles]
    elif deps.is_signal_switch_like(device):
        switch_device_context = deps.infer_switch_traits(device, datasheet_context=datasheet_design_context)
        external_components = deps.switch_external_components(switch_device_context)
        noisy_roles = {
            "input_capacitor",
            "output_capacitor",
            "snubber_capacitor",
            "snubber_resistor",
            "filter_network",
        }
        datasheet_components = [item for item in datasheet_components if item.get("role") not in noisy_roles]
    elif mcu_device_context:
        external_components = deps.mcu_external_components(mcu_device_context)
    else:
        external_components = deps.normal_ic_external_components(device, pin_groups)
    external_components.extend(datasheet_components)

    if "opamp" in category or "amplifier" in category or "comparator" in category:
        starter_nets = [
            {"name": "V+", "purpose": "analog_positive_supply"},
            {"name": "GND", "purpose": "module_ground"},
            {"name": "VIN_SIG", "purpose": "analog_input_signal"},
            {"name": "VOUT_ANA", "purpose": "analog_output_signal"},
            {"name": "VREF", "purpose": "analog_reference_or_bias"},
        ]
    elif decoder_device_context:
        starter_nets = deps.decoder_starter_nets(decoder_device_context)
    elif interface_switch_device_context:
        starter_nets = deps.interface_switch_starter_nets(interface_switch_device_context)
    elif switch_device_context:
        starter_nets = deps.switch_starter_nets(switch_device_context)
    elif mcu_device_context:
        starter_nets = deps.mcu_starter_nets(mcu_device_context)
    else:
        starter_nets = [
            {"name": "VIN", "purpose": "primary_input_supply"},
            {"name": "GND", "purpose": "module_ground"},
        ]
        if pin_groups["power_outputs"]:
            starter_nets.append({"name": "VOUT", "purpose": "regulated_or_power_output"})
        if pin_groups["control_inputs"]:
            starter_nets.append({"name": "EN", "purpose": "enable_or_mode_control"})
        if pin_groups["status_outputs"]:
            starter_nets.append({"name": "PG", "purpose": "status_feedback"})

    return {
        "_schema": bundle_schema,
        "bundle_layer": "L1_design_intent",
        "device_ref": {
            "mpn": device.get("mpn"),
            "type": device.get("_type"),
            "category": device.get("category"),
            "manufacturer": device.get("manufacturer"),
            "preferred_package": preferred_package,
            "packages": sorted(device.get("packages", {}).keys()),
        },
        "pin_groups": pin_groups,
        "attention_items": attention_items,
        "constraints": constraints,
        "external_components": external_components,
        "starter_nets": starter_nets,
        "decoder_device_context": decoder_device_context,
        "interface_switch_device_context": interface_switch_device_context,
        "switch_device_context": switch_device_context,
        "mcu_device_context": mcu_device_context,
        "datasheet_design_context": datasheet_design_context,
    }


def build_normal_ic_module_template(
    device: dict,
    design_intent: dict,
    *,
    bundle_schema: str,
    deps: NormalIcModuleTemplateDeps,
) -> dict:
    device = normalize_normal_ic_export(device)
    module_name = deps.sanitize_name(device.get("mpn") or "device") + "_module"
    nets = list(design_intent.get("starter_nets", []))
    blocks = [
        {
            "ref": "U1",
            "type": "device",
            "mpn": device.get("mpn"),
            "package": design_intent.get("device_ref", {}).get("preferred_package")
            or design_intent.get("device_ref", {}).get("package"),
        }
    ]
    for component in design_intent.get("external_components", []):
        blocks.append(
            {
                "ref": component.get("designator"),
                "type": "support_component",
                "role": component.get("role"),
                "status": component.get("status"),
                "connect_between": component.get("connect_between"),
            }
        )

    topology_candidates = []
    opamp_templates = []
    decoder_templates = []
    interface_switch_templates = []
    switch_templates = []
    fpga_scenarios = []
    fpga_templates = []
    opamp_device_context = None
    decoder_device_context = design_intent.get("decoder_device_context")
    interface_switch_device_context = design_intent.get("interface_switch_device_context")
    switch_device_context = design_intent.get("switch_device_context")
    mcu_device_context = design_intent.get("mcu_device_context")
    category = (device.get("category") or "").lower()
    mcu_templates = []
    default_mcu_template = None
    default_opamp_template = None
    default_decoder_template = None
    default_interface_switch_template = None
    default_switch_template = None
    default_fpga_template = None

    if "opamp" in category or "amplifier" in category:
        opamp_device_context = deps.infer_opamp_traits(device, design_intent)
        topology_candidates = deps.opamp_topology_candidates(design_intent)
        opamp_templates = deps.opamp_standard_templates(device, design_intent, topology_candidates)
        default_opamp_template = deps.choose_default_opamp_template(opamp_templates, topology_candidates)
        for net_name, net_purpose in (
            (opamp_device_context["suggested_power_nets"]["positive"], "analog_positive_supply"),
            (opamp_device_context["suggested_power_nets"]["negative"], "analog_negative_supply_or_ground"),
            (opamp_device_context["suggested_power_nets"]["reference"], "analog_reference_or_bias"),
        ):
            deps.append_net_once(nets, net_name, net_purpose)
        for candidate in topology_candidates:
            for net in candidate.get("nets", []):
                deps.append_net_once(nets, net["name"], net["purpose"])
            for block in candidate.get("blocks", []):
                deps.append_block_once(
                    blocks,
                    block["ref"],
                    block["type"],
                    block["role"],
                    topology=candidate["name"],
                )
    elif decoder_device_context:
        topology_candidates = deps.decoder_topology_candidates(decoder_device_context)
        decoder_templates = deps.decoder_standard_templates(device, decoder_device_context, topology_candidates)
        default_decoder_template = deps.choose_default_decoder_template(decoder_templates, topology_candidates)
        for candidate in topology_candidates:
            for net in candidate.get("nets", []):
                deps.append_net_once(nets, net["name"], net["purpose"])
            for block in candidate.get("blocks", []):
                deps.append_block_once(
                    blocks,
                    block["ref"],
                    block["type"],
                    block["role"],
                    topology=candidate["name"],
                )
    elif interface_switch_device_context:
        interface_switch_templates = deps.interface_switch_standard_templates(device, interface_switch_device_context)
        default_interface_switch_template = deps.choose_default_interface_switch_template(interface_switch_templates)
        for template in interface_switch_templates:
            for net_name in template.get("nets", []):
                deps.append_net_once(nets, net_name, "interface_switch_template_placeholder")
            for block_name in template.get("blocks", []):
                if block_name == "U1":
                    continue
                deps.append_block_once(
                    blocks,
                    block_name,
                    "topology_block",
                    "interface_switch_template_block",
                    template=template["name"],
                )
    elif switch_device_context:
        switch_templates = deps.switch_standard_templates(device, switch_device_context)
        default_switch_template = deps.choose_default_switch_template(switch_templates)
        for template in switch_templates:
            for net_name in template.get("nets", []):
                deps.append_net_once(nets, net_name, "switch_template_placeholder")
            for block_name in template.get("blocks", []):
                if block_name == "U1":
                    continue
                deps.append_block_once(
                    blocks,
                    block_name,
                    "topology_block",
                    "switch_template_block",
                    template=template["name"],
                )
    elif mcu_device_context:
        mcu_templates = deps.mcu_standard_templates(device, mcu_device_context)
        default_mcu_template = deps.choose_default_mcu_template(mcu_templates)
        for template in mcu_templates:
            for net_name in template.get("nets", []):
                deps.append_net_once(nets, net_name, "mcu_template_placeholder")
            for block_name in template.get("blocks", []):
                if block_name == "U1":
                    continue
                deps.append_block_once(
                    blocks,
                    block_name,
                    "topology_block",
                    "mcu_template_block",
                    template=template["name"],
                )
            for net_name in template.get("nets", []):
                deps.append_net_once(nets, net_name, "switch_template_placeholder")
            for block_name in template.get("blocks", []):
                if block_name == "U1":
                    continue
                deps.append_block_once(
                    blocks,
                    block_name,
                    "topology_block",
                    "switch_template_block",
                    template=template["name"],
                )

    todos = [
        "Confirm preferred package against footprint library and assembly constraints.",
        "Replace placeholder values with datasheet-approved component values.",
        "Review all attention_items before schematic release.",
        "Close the power loop layout early for power devices before PCB placement starts.",
    ]
    for candidate in topology_candidates:
        for item in candidate.get("todo", []):
            if item not in todos:
                todos.append(item)

    return {
        "_schema": bundle_schema,
        "bundle_layer": "L3_module_template",
        "module_name": module_name,
        "device": {
            "mpn": device.get("mpn"),
            "category": device.get("category"),
            "manufacturer": device.get("manufacturer"),
        },
        "nets": nets,
        "blocks": blocks,
        "opamp_device_context": opamp_device_context,
        "decoder_device_context": decoder_device_context,
        "interface_switch_device_context": interface_switch_device_context,
        "switch_device_context": switch_device_context,
        "mcu_device_context": mcu_device_context,
        "topology_candidates": topology_candidates,
        "opamp_templates": opamp_templates,
        "decoder_templates": decoder_templates,
        "interface_switch_templates": interface_switch_templates,
        "switch_templates": switch_templates,
        "mcu_templates": mcu_templates,
        "fpga_scenarios": fpga_scenarios,
        "fpga_templates": fpga_templates,
        "high_speed_semantic_context": design_intent.get("high_speed_semantic_context"),
        "default_opamp_template": default_opamp_template,
        "default_decoder_template": default_decoder_template,
        "default_interface_switch_template": default_interface_switch_template,
        "default_switch_template": default_switch_template,
        "default_mcu_template": default_mcu_template,
        "default_fpga_template": default_fpga_template,
        "todo": todos,
    }
