#!/usr/bin/env python3
"""Export reusable Agilex 5 knowledge pools and application interfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_DIR = REPO_ROOT / "data" / "sch_review_export"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "debugtool_interface" / "intel_agilex5.json"
DEFAULT_POOL_DIR = REPO_ROOT / "data" / "knowledge_pool" / "fpga" / "intel_agilex5"
INTERFACE_SCHEMA = "opendatasheet-debugtool-interface/1.0"
POOL_SCHEMA = "opendatasheet-knowledge-pool/1.0"
APPLICATION_PROFILE_SCHEMA = "opendatasheet-application-profile/1.0"


DEBUGTOOL_ASSET_MAP = {
    "link_models": [
        {
            "id": "LM-FPGA-JTAG-CONFIG",
            "mapped_interfaces": ["fpga_jtag_configuration", "fpga_configuration_boot"],
        },
        {
            "id": "LM-POWER-CHAIN",
            "mapped_interfaces": ["power_rail_integrity"],
        },
        {
            "id": "LM-PCIE-LINK",
            "mapped_interfaces": ["gts_transceiver_link"],
        },
        {
            "id": "LM-MIPI-DSI-CSI-DPHY",
            "mapped_interfaces": ["mipi_dphy_debug"],
        },
        {
            "id": "LM-DDR-BRINGUP",
            "mapped_interfaces": ["external_memory_interface"],
        },
    ],
    "signatures": [
        {
            "id": "SIG-QUARTUS-CABLE-SEEN-SCAN-CHAIN-FAIL",
            "mapped_interfaces": ["fpga_jtag_configuration"],
        },
        {
            "id": "SIG-JTAG-CABLE-SEEN-NO-TARGET-WAVEFORM",
            "mapped_interfaces": ["fpga_jtag_configuration"],
        },
        {
            "id": "SIG-PCIE-REFCLK-MISSING",
            "mapped_interfaces": ["gts_transceiver_link"],
        },
        {
            "id": "SIG-MIPI-CSI-NO-FRAME-PACKET-COUNTERS-FIRST",
            "mapped_interfaces": ["mipi_dphy_debug"],
        },
        {
            "id": "SIG-MIPI-DSI-BRIDGE-NO-VIDEO-LP11-HSCLK",
            "mapped_interfaces": ["mipi_dphy_debug"],
        },
        {
            "id": "SIG-NIOS-ELF-AFTER-SOF-HARDWARE-MAP",
            "mapped_interfaces": ["nios_soft_core_debug"],
        },
    ],
}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fp:
        return json.load(fp)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _compact_pin(pin: dict[str, Any], *, include_optional: bool = True) -> dict[str, Any]:
    item = {
        "ball": pin.get("pin"),
        "signal": pin.get("name") or pin.get("raw_name"),
        "raw_name": pin.get("raw_name"),
        "bank": pin.get("bank"),
        "function": pin.get("function") or pin.get("category"),
    }
    if include_optional and pin.get("optional_functions"):
        item["optional_functions"] = pin.get("optional_functions")
    return {key: value for key, value in item.items() if value not in (None, "", [])}


def _signal_key(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_")


def _pins_by_exact_signal(device: dict[str, Any], signals: list[str]) -> dict[str, dict[str, Any]]:
    wanted = {_signal_key(signal): signal for signal in signals}
    pins: dict[str, dict[str, Any]] = {}
    for pin in device.get("pins", []) or []:
        for candidate in (pin.get("name"), pin.get("raw_name")):
            key = _signal_key(candidate)
            if key in wanted and wanted[key] not in pins:
                pins[wanted[key]] = _compact_pin(pin)
    return pins


def _pins_by_optional_prefix(device: dict[str, Any], prefixes: list[str]) -> list[dict[str, Any]]:
    prefixes_norm = tuple(_signal_key(prefix) for prefix in prefixes)
    pins: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for pin in device.get("pins", []) or []:
        optionals = pin.get("optional_functions") or []
        matches = [
            optional
            for optional in optionals
            if any(_signal_key(optional).startswith(prefix) for prefix in prefixes_norm)
        ]
        if not matches:
            continue
        key = (pin.get("pin"), pin.get("name"))
        if key in seen:
            continue
        seen.add(key)
        item = _compact_pin(pin)
        item["matched_optional_functions"] = matches
        pins.append(item)
    return pins


def _rails_matching(device: dict[str, Any], tokens: list[str], limit: int | None = None) -> list[dict[str, Any]]:
    tokens_norm = tuple(_signal_key(token) for token in tokens)
    rails: list[dict[str, Any]] = []
    for name in sorted((device.get("supply_specs") or {}).keys()):
        if not any(token in _signal_key(name) for token in tokens_norm):
            continue
        spec = device["supply_specs"][name]
        item = {"name": name}
        for key in ("min", "typ", "max", "unit", "source"):
            if key in spec:
                item[key] = spec[key]
        rails.append(item)
        if limit and len(rails) >= limit:
            break
    return rails


def _all_supply_rail_names(device: dict[str, Any]) -> list[str]:
    return sorted((device.get("supply_specs") or {}).keys())


def _debugtool_fact(fact_id: str, source: str, claim: str, machine: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fact_id,
        "state": "documented",
        "source": source,
        "confidence": "high",
        "claim": claim,
        "machine": machine,
    }


def _jtag_and_config_pins(device: dict[str, Any]) -> dict[str, Any]:
    jtag = _pins_by_exact_signal(device, ["TCK", "TMS", "TDI", "TDO"])
    status = _pins_by_exact_signal(device, ["nCONFIG", "nSTATUS", "CONF_DONE", "INIT_DONE"])
    clock = _pins_by_exact_signal(device, ["OSC_CLK_1"])
    mode = _pins_by_optional_prefix(device, ["MSEL"])
    active_serial = _pins_by_optional_prefix(device, ["AS_"])
    avst = _pins_by_optional_prefix(device, ["AVST"])
    pwrmgt = _pins_by_optional_prefix(device, ["PWRMGT"])
    missing_generic_status = [
        signal
        for signal in ("CONF_DONE", "INIT_DONE")
        if signal not in status
    ]
    return {
        "jtag": jtag,
        "status": status,
        "clock": clock,
        "mode_select": mode,
        "active_serial": active_serial,
        "avst": avst,
        "power_management": pwrmgt,
        "missing_generic_status_signals": missing_generic_status,
    }


def _optional_group_summary(device: dict[str, Any]) -> dict[str, dict[str, Any]]:
    groups = {
        "hps_jtag": ["JTAG_"],
        "hps_uart": ["UART"],
        "hps_sdmmc": ["SDMMC"],
        "hps_emac": ["EMAC", "MDIO"],
        "hps_usb": ["USB"],
        "hps_nand": ["NAND"],
        "hps_trace": ["TRACE"],
        "hps_i2c_i3c": ["I2C", "I3C"],
        "hps_spi": ["SPIM", "SPIS"],
    }
    summary: dict[str, dict[str, Any]] = {}
    for name, prefixes in groups.items():
        pins = _pins_by_optional_prefix(device, prefixes)
        if pins:
            summary[name] = {
                "pin_count": len(pins),
                "sample_pins": pins[:12],
            }
    return summary


def _dqs_pin_summary(device: dict[str, Any]) -> dict[str, Any]:
    pins = [
        pin
        for pin in device.get("pins", []) or []
        if pin.get("dqs_x4") or pin.get("dqs_x8_x9") or pin.get("dqs_x16_x18")
    ]
    by_bank: dict[str, int] = {}
    for pin in pins:
        bank = str(pin.get("bank") or "unknown")
        by_bank[bank] = by_bank.get(bank, 0) + 1
    return {
        "dqs_related_pin_count": len(pins),
        "by_bank": dict(sorted(by_bank.items())),
        "sample_pins": [
            {
                **_compact_pin(pin, include_optional=False),
                "dqs_x4": pin.get("dqs_x4"),
                "dqs_x8_x9": pin.get("dqs_x8_x9"),
                "dqs_x16_x18": pin.get("dqs_x16_x18"),
            }
            for pin in pins[:16]
        ],
    }


def _device_facts(device: dict[str, Any], pin_groups: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    jtag = pin_groups["jtag"]
    for signal, pin in sorted(jtag.items()):
        facts.append(
            _debugtool_fact(
                f"pin.{signal}",
                "sch_review_export.pins",
                f"Configuration JTAG {signal} is on package ball {pin['ball']}.",
                {"signal": signal, **pin},
            )
        )
    for signal, pin in sorted(pin_groups["status"].items()):
        facts.append(
            _debugtool_fact(
                f"pin.{signal}",
                "sch_review_export.pins",
                f"Configuration status/control signal {signal} is on package ball {pin['ball']}.",
                {"signal": signal, **pin},
            )
        )
    resources = (device.get("capability_blocks") or {}).get("fabric_resources") or {}
    if resources.get("logic_elements"):
        facts.append(
            _debugtool_fact(
                "resources.logic_elements",
                "sch_review_export.capability_blocks.fabric_resources",
                f"Device exposes {resources['logic_elements']} logic elements in the parsed capability profile.",
                {"logic_elements": resources["logic_elements"]},
            )
        )
    return facts


def _jtag_evidence_api(
    device: dict[str, Any],
    pin_groups: dict[str, Any],
    config_rails: list[dict[str, Any]],
) -> dict[str, Any]:
    known_gaps = []
    if pin_groups["missing_generic_status_signals"]:
        known_gaps.append(
            {
                "gap": "generic_fpga_status_signal_not_named_in_package_export",
                "signals": pin_groups["missing_generic_status_signals"],
                "impact": "DebugTool's generic CONF_DONE/INIT_DONE checks must be translated to Agilex 5 package-specific configuration status evidence, primarily nCONFIG, nSTATUS, SDM_IO boot pins, and Quartus Programmer status.",
            }
        )
    return {
        "debugtool_link_models": ["LM-FPGA-JTAG-CONFIG"],
        "debugtool_signatures": [
            "SIG-QUARTUS-CABLE-SEEN-SCAN-CHAIN-FAIL",
            "SIG-JTAG-CABLE-SEEN-NO-TARGET-WAVEFORM",
        ],
        "mapped_source_blocks": [
            "pins.CONFIG",
            "capability_blocks.configuration",
            "constraint_blocks.configuration_boot",
            "drc_rules.configuration_pins",
            "drc_rules.agilex5_configuration_clock",
        ],
        "required_evidence": [
            {
                "kind": "log",
                "id": "quartus_jtagconfig_n",
                "tool_hint": "jtagconfig -n and Quartus Programmer Auto Detect output",
                "why": "Separates host/cable enumeration, chain scan, device ID recognition, and soft debug nodes.",
            },
            {
                "kind": "waveform",
                "id": "fpga_end_jtag_waveforms",
                "acquire_at": "FPGA pins or closest accessible probes during Quartus Auto Detect",
                "signals": list(pin_groups["jtag"].values()),
            },
            {
                "kind": "measurement",
                "id": "configuration_power_rails",
                "rails": config_rails,
                "why": "Target VREF, SDM/config bank power, and core rails gate JTAG visibility before bitstream-level hypotheses.",
            },
            {
                "kind": "waveform",
                "id": "configuration_status_and_mode",
                "signals": [
                    *pin_groups["status"].values(),
                    *pin_groups["clock"].values(),
                    *pin_groups["mode_select"],
                ],
                "why": "Mode straps, nCONFIG/nSTATUS, and configuration clock/status evidence should be acquired before changing programming files.",
            },
        ],
        "schematic_review_checks": [
            "Expose a measurable JTAG path at the FPGA end, not only at the connector.",
            "Review TDI/TDO chain order, bypass devices, connector VREF, cable ground, and pull policy.",
            "Check nCONFIG/nSTATUS, MSEL pins, OSC_CLK_1, AS/AVST boot pins, and SDM power rails before chasing Quartus software state.",
        ],
        "known_gaps": known_gaps,
    }


def _configuration_boot_api(device: dict[str, Any], pin_groups: dict[str, Any]) -> dict[str, Any]:
    return {
        "debugtool_link_models": ["LM-FPGA-JTAG-CONFIG"],
        "mapped_source_blocks": [
            "constraint_blocks.configuration_boot",
            "drc_rules.agilex5_configuration_clock",
            "drc_rules.agilex5_pin_connection_guidelines",
        ],
        "required_evidence": [
            {
                "kind": "schematic",
                "id": "boot_mode_straps",
                "signals": pin_groups["mode_select"],
                "why": "MSEL and SDM_IO assignments select the boot path and should match the intended AS/AVST/JTAG configuration flow.",
            },
            {
                "kind": "waveform",
                "id": "as_or_avst_boot_bus_activity",
                "signals": [*pin_groups["active_serial"], *pin_groups["avst"]],
                "why": "If JTAG can see the device but configuration fails, bus activity at the FPGA end separates flash/IP wiring from bitstream causes.",
            },
            {
                "kind": "measurement",
                "id": "sdm_power_management_bus",
                "signals": pin_groups["power_management"],
                "why": "PWRMGT pins affect SmartVID and regulator interaction during configuration and early boot.",
            },
        ],
        "schematic_review_checks": [
            "Freeze the intended configuration mode and verify every SDM_IO multiplexed function against that mode.",
            "Review AS_nCSO, AS_CLK, AS_DATA, AVST data/ready/valid, and AS_nRST routing at the package pins.",
            "Check pull-ups, pull-downs, and unused SDM_IO handling against the Pin Connection Guidelines.",
        ],
    }


def _power_api(device: dict[str, Any], rails: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "debugtool_link_models": ["LM-POWER-CHAIN"],
        "mapped_source_blocks": [
            "supply_specs",
            "power_rails",
            "constraint_blocks.power_integrity",
            "drc_rules.power_integrity",
            "drc_rules.agilex5_power_monotonic_ramp",
        ],
        "required_evidence": [
            {
                "kind": "measurement",
                "id": "same_window_power_ramp",
                "rails": rails["core_and_sdm"][:16],
                "why": "Agilex 5 bring-up faults can masquerade as JTAG/configuration failures when rails are non-monotonic or early rails brown out.",
            },
            {
                "kind": "measurement",
                "id": "smartvid_and_pmbus",
                "rails": rails["smartvid"],
                "why": "SmartVID/PMBus regulator behavior is part of the configuration-time evidence set, not a later optimization detail.",
            },
        ],
        "schematic_review_checks": [
            "Review monotonic ramp, regulator enable dependencies, sense routing, rail grouping, and decoupling before firmware-level hypotheses.",
            "Keep rail names as net aliases so DebugTool can match measured waveforms to datasheet rails.",
        ],
    }


def _gts_api(device: dict[str, Any], gts_rails: list[dict[str, Any]]) -> dict[str, Any] | None:
    hs = (device.get("capability_blocks") or {}).get("high_speed_serial") or {}
    if not hs:
        return None
    refclk = (device.get("constraint_blocks") or {}).get("refclk_requirements") or {}
    return {
        "debugtool_link_models": ["LM-PCIE-LINK"],
        "debugtool_signatures": ["SIG-PCIE-REFCLK-MISSING"],
        "mapped_source_blocks": [
            "capability_blocks.high_speed_serial",
            "constraint_blocks.refclk_requirements",
            "constraint_blocks.gts_transceiver_power_integrity",
            "drc_rules.serdes_refclk",
            "drc_rules.agilex5_gts_transceiver_power_noise",
        ],
        "device_facts": {
            "transceiver_channel_count": hs.get("transceiver_channel_count"),
            "max_rate_gbps": hs.get("max_rate_gbps"),
            "supported_protocols": hs.get("supported_protocols"),
            "pcie4_x4_instance_count": hs.get("pcie4_x4_instance_count"),
            "refclk_pair_count": refclk.get("refclk_pair_count"),
            "common_review_candidates_mhz": refclk.get("common_review_candidates_mhz"),
            "refclk_pairs": refclk.get("refclk_pairs", []),
            "lane_group_mappings": refclk.get("lane_group_mappings", []),
        },
        "required_evidence": [
            {
                "kind": "measurement",
                "id": "gts_power_noise",
                "rails": gts_rails,
                "why": "Transceiver rail noise and sequencing should be checked before protocol training or equalization changes.",
            },
            {
                "kind": "waveform",
                "id": "protocol_refclk",
                "signals": refclk.get("refclk_pairs", []),
                "why": "PCIe/Ethernet/custom SerDes failures need refclk presence, frequency, standard, jitter budget, and pair-to-lane mapping evidence.",
            },
            {
                "kind": "log",
                "id": "quartus_or_ip_link_status",
                "tool_hint": "Transceiver Toolkit, PCIe HIP status, link training status, or protocol IP counters",
            },
        ],
        "schematic_review_checks": [
            "Freeze protocol, lane width, refclk frequency, and pair-to-quad mapping before schematic sign-off.",
            "Check whether the selected ordering code and package support the intended transceiver use case.",
        ],
    }


def _mipi_api(device: dict[str, Any]) -> dict[str, Any] | None:
    io = (device.get("capability_blocks") or {}).get("io_resources") or {}
    count = io.get("mipi_dphy_interface_count") or 0
    if not count:
        return None
    return {
        "debugtool_link_models": ["LM-MIPI-DSI-CSI-DPHY"],
        "debugtool_signatures": [
            "SIG-MIPI-CSI-NO-FRAME-PACKET-COUNTERS-FIRST",
            "SIG-MIPI-DSI-BRIDGE-NO-VIDEO-LP11-HSCLK",
        ],
        "mapped_source_blocks": ["capability_blocks.io_resources"],
        "device_facts": {
            "mipi_dphy_interface_count": count,
            "source": io.get("source"),
        },
        "required_evidence": [
            {
                "kind": "doc",
                "id": "quartus_ip_parameters",
                "fields": [
                    "lane_count",
                    "lane_order",
                    "lane_polarity",
                    "clock_mode",
                    "data_type",
                    "virtual_channel",
                    "pixel_clock",
                ],
                "why": "DebugTool's MIPI path needs project binding facts because the package export does not know the chosen IP instance assignment.",
            },
            {
                "kind": "log",
                "id": "dphy_and_packet_counters",
                "fields": ["LP11/stopstate", "HS clock", "packet count", "data type", "VC", "ECC/CRC"],
            },
        ],
        "schematic_review_checks": [
            "Treat MIPI as project-bound: lane assignment, polarity, termination, LP/HS state, and receiver counters must come from Quartus/IP/register evidence.",
            "Use the package capability count only as a capacity prior, not as proof that a specific lane set is correctly assigned.",
        ],
        "known_gaps": [
            {
                "gap": "mipi_lane_pin_binding_not_normalized",
                "impact": "The current Agilex 5 export exposes family/package MIPI capacity but not concrete D-PHY lane-to-ball assignments for a project IP instance.",
            }
        ],
    }


def _memory_api(device: dict[str, Any], dqs_summary: dict[str, Any]) -> dict[str, Any] | None:
    memory = (device.get("capability_blocks") or {}).get("memory_interface") or {}
    if not memory:
        return None
    return {
        "debugtool_link_models": ["LM-DDR-BRINGUP"],
        "mapped_source_blocks": ["capability_blocks.memory_interface", "pins.dqs_*"],
        "device_facts": {
            "supported_standards": memory.get("supported_standards"),
            "x32_interface_count": memory.get("x32_interface_count"),
            "dqs_pin_summary": dqs_summary,
        },
        "required_evidence": [
            {
                "kind": "log",
                "id": "emif_calibration_state",
                "tool_hint": "Quartus EMIF Toolkit or calibration report",
                "why": "EMIF failures should be separated into calibration stage, lane/byte group, clock/reset, and board signal-integrity causes.",
            },
            {
                "kind": "schematic",
                "id": "memory_byte_lane_mapping",
                "signals": dqs_summary["sample_pins"],
                "why": "DQS/DQ grouping and bank selection are reviewable before board bring-up.",
            },
        ],
        "schematic_review_checks": [
            "Tie the chosen memory topology to banks, DQS groups, voltage rails, reference voltages, reset, clocks, and calibration observability.",
        ],
    }


def _nios_api(device: dict[str, Any]) -> dict[str, Any]:
    return {
        "debugtool_signatures": ["SIG-NIOS-ELF-AFTER-SOF-HARDWARE-MAP"],
        "mapped_source_blocks": ["capability_blocks.configuration", "pins.CONFIG"],
        "required_evidence": [
            {
                "kind": "log",
                "id": "sof_success_and_jtag_nodes",
                "tool_hint": "Quartus Programmer SOF success plus jtagconfig -n node list",
            },
            {
                "kind": "doc",
                "id": "platform_designer_hardware_map",
                "fields": ["sopcinfo", "System ID", "reset vector", "exception vector", "debug module", "JTAG UART"],
            },
        ],
        "schematic_review_checks": [
            "Do not treat ELF/debug failure after SOF success as a pure software problem until JTAG nodes, reset, clock, memory map, and exported hardware image match.",
        ],
    }


def _hps_api(device: dict[str, Any], hps_groups: dict[str, Any], hps_rails: list[dict[str, Any]]) -> dict[str, Any] | None:
    hps = (device.get("capability_blocks") or {}).get("hard_processor") or {}
    if not hps:
        return None
    return {
        "debugtool_link_models": [],
        "mapped_source_blocks": [
            "capability_blocks.hard_processor",
            "pins.optional_functions.HPS",
            "constraint_blocks.hps_power_integrity",
            "drc_rules.agilex5_hps_power_rails",
        ],
        "device_facts": {
            "mode": hps.get("mode"),
            "cores": hps.get("cores"),
            "hps_pin_groups": hps_groups,
        },
        "required_evidence": [
            {
                "kind": "measurement",
                "id": "hps_power_and_reset",
                "rails": hps_rails,
                "why": "HPS boot/debug failures need HPS rail and reset evidence before software image hypotheses.",
            },
            {
                "kind": "schematic",
                "id": "hps_boot_and_console_mapping",
                "pin_groups": hps_groups,
                "why": "Boot media, UART console, JTAG, SDMMC, EMAC, USB, and trace pins are muxed and must match the selected HPS design.",
            },
        ],
        "schematic_review_checks": [
            "DebugTool currently lacks a dedicated HPS boot link model; consume these facts as project-specific evidence inputs.",
        ],
        "known_gaps": [
            {
                "gap": "debugtool_hps_boot_link_model_missing",
                "impact": "A future DebugTool asset should model HPS boot straps, reset, clock, console, boot media, and secure boot/error-state evidence.",
            }
        ],
    }


def build_device_interface(path: Path, device: dict[str, Any]) -> dict[str, Any]:
    capability = device.get("capability_blocks") or {}
    identity = device.get("device_identity") or {}
    pin_groups = _jtag_and_config_pins(device)
    hps_groups = _optional_group_summary(device)
    dqs_summary = _dqs_pin_summary(device)
    rails = {
        "all_names": _all_supply_rail_names(device),
        "core_and_sdm": _rails_matching(
            device,
            ["VCC", "VCCP", "VCCPT", "SDM", "VCCBAT", "VCCADC", "VCCFUSE"],
            limit=32,
        ),
        "smartvid": _rails_matching(device, ["SMARTVID", "VCCP", "PWRMGT"], limit=16),
        "hps": _rails_matching(device, ["HPS"], limit=16),
        "gts": _rails_matching(device, ["GTS", "HSSI"], limit=24),
    }
    evidence_apis: dict[str, Any] = {
        "fpga_jtag_configuration": _jtag_evidence_api(device, pin_groups, rails["core_and_sdm"]),
        "fpga_configuration_boot": _configuration_boot_api(device, pin_groups),
        "power_rail_integrity": _power_api(device, rails),
        "nios_soft_core_debug": _nios_api(device),
    }
    optional_apis = {
        "gts_transceiver_link": _gts_api(device, rails["gts"]),
        "mipi_dphy_debug": _mipi_api(device),
        "external_memory_interface": _memory_api(device, dqs_summary),
        "hps_hard_processor_debug": _hps_api(device, hps_groups, rails["hps"]),
    }
    for name, value in optional_apis.items():
        if value:
            evidence_apis[name] = value

    source_traceability = device.get("source_traceability") or {}
    return {
        "debugtool_profile_id": f"intel_agilex5:{device.get('mpn')}_{device.get('package')}",
        "mpn": device.get("mpn"),
        "package": device.get("package"),
        "device_role": device.get("device_role") or identity.get("device_role"),
        "source_export": _rel(path),
        "source_export_sha256": _sha256(path),
        "source_traceability": {
            key: source_traceability.get(key)
            for key in (
                "package_pinout",
                "device_capability",
                "device_datasheet",
                "pin_connection_guidelines",
            )
            if source_traceability.get(key)
        },
        "selectors": {
            "vendor_aliases": ["Intel", "Altera", "Intel/Altera"],
            "family_aliases": ["Agilex 5", "Agilex5", "A5E"],
            "base_device": identity.get("base_device"),
            "variant_code": (device.get("ordering_variant") or {}).get("variant_code"),
            "has_hps": bool(capability.get("hard_processor")),
            "has_gts_transceiver": bool(capability.get("high_speed_serial")),
            "has_mipi_dphy": bool((capability.get("io_resources") or {}).get("mipi_dphy_interface_count")),
            "has_external_memory_interface": bool(capability.get("memory_interface")),
        },
        "pin_groups": {
            "configuration": pin_groups,
            "hps_optional_function_groups": hps_groups,
            "memory_dqs": dqs_summary,
        },
        "rails": rails,
        "facts": _device_facts(device, pin_groups),
        "evidence_apis": evidence_apis,
    }


def build_debugtool_interface(export_dir: Path = DEFAULT_EXPORT_DIR, pattern: str = "A5E*.json") -> dict[str, Any]:
    paths = sorted(path for path in export_dir.glob(pattern) if path.is_file())
    devices = [build_device_interface(path, _read_json(path)) for path in paths]
    return {
        "_schema": INTERFACE_SCHEMA,
        "vendor": "Intel/Altera",
        "family": "Agilex 5",
        "purpose": "DebugTool-facing evidence API derived from OpenDatasheet sch-review exports.",
        "source_exports": {
            "glob": f"{_rel(export_dir)}/{pattern}",
            "device_count": len(devices),
        },
        "debugtool_assets": DEBUGTOOL_ASSET_MAP,
        "common_review_profile": {
            "first_batch_evidence_order": [
                "quartus_jtagconfig_n",
                "fpga_end_jtag_waveforms",
                "configuration_power_rails",
                "configuration_status_and_mode",
                "same_window_power_ramp",
            ],
            "review_philosophy": "Treat datasheet/package facts as documented priors. Project schematics, measured waveforms, Quartus logs, IP parameters, and register counters are stronger target-system evidence.",
            "known_global_gaps": [
                {
                    "gap": "project_instance_binding",
                    "impact": "OpenDatasheet can expose package capabilities and pin facts, but DebugTool still needs project-specific net names, IP instance parameters, and measured evidence.",
                },
                {
                    "gap": "pin_connection_guideline_rules_not_fully_structured",
                    "impact": "The interface links to the official Pin Connection Guidelines but does not yet encode every unused-pin and pull-policy table as machine rules.",
                },
            ],
        },
        "devices": devices,
    }


def _deepcopy_jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _generic_evidence_api(api: dict[str, Any]) -> dict[str, Any]:
    normalized = _deepcopy_jsonable(api)
    bindings: dict[str, Any] = {}
    link_models = normalized.pop("debugtool_link_models", None)
    signatures = normalized.pop("debugtool_signatures", None)
    if link_models:
        bindings["link_models"] = link_models
    if signatures:
        bindings["signatures"] = signatures
    if bindings:
        normalized["application_bindings"] = {"debugtool": bindings}
    return normalized


def _pool_manifest_yaml(device_count: int) -> str:
    return f"""schema: {POOL_SCHEMA}
pool_id: fpga.intel_agilex5
vendor: Intel/Altera
family: Agilex 5
source_exports:
  glob: data/sch_review_export/A5E*.json
  device_count: {device_count}
naming:
  artifact_dir: data/knowledge_pool/fpga/intel_agilex5
  rule: "<domain>/<vendor_family>/<artifact_kind>.json"
  pool_id_rule: "fpga.<vendor_family>"
artifacts:
  device_profiles:
    file: device_profiles.json
    contains: device identity, selectors, source traceability, capability blocks
  pin_signal_map:
    file: pin_signal_map.json
    contains: configuration pins, SDM boot pins, HPS mux groups, memory DQS groups
  electrical_constraints:
    file: electrical_constraints.json
    contains: supply specs, absolute maximums, IO standards, constraint blocks, DRC rules
  diagnostic_evidence_profiles:
    file: diagnostic_evidence_profiles.json
    contains: reusable bring-up/debug evidence requirements and application bindings
  debug_readiness_matrix:
    file: debug_readiness_matrix.json
    contains: coverage matrix for DebugTool-style first-pass debug needs and external evidence boundaries
  application_profiles:
    file: application_profiles.yaml
    contains: read-order policy for each downstream consumer
"""


def _application_profiles_yaml() -> str:
    return f"""schema: {APPLICATION_PROFILE_SCHEMA}
pool_id: fpga.intel_agilex5
applications:
  schematic_review:
    intent: board-level schematic review and sign-off
    read_order:
      - electrical_constraints.json
      - pin_signal_map.json
      - device_profiles.json
      - ../../../sch_review_export/A5E*.json
    required_keys:
      - supply_specs
      - constraint_blocks
      - drc_rules
      - pin_groups.configuration
      - pin_groups.memory_dqs
  debugtool:
    intent: staged fault isolation and evidence planning
    read_order:
      - debug_readiness_matrix.json
      - diagnostic_evidence_profiles.json
      - pin_signal_map.json
      - electrical_constraints.json
      - device_profiles.json
    application_bindings:
      link_models:
        - LM-FPGA-JTAG-CONFIG
        - LM-POWER-CHAIN
        - LM-PCIE-LINK
        - LM-MIPI-DSI-CSI-DPHY
        - LM-DDR-BRINGUP
      signatures:
        - SIG-QUARTUS-CABLE-SEEN-SCAN-CHAIN-FAIL
        - SIG-JTAG-CABLE-SEEN-NO-TARGET-WAVEFORM
        - SIG-PCIE-REFCLK-MISSING
        - SIG-MIPI-CSI-NO-FRAME-PACKET-COUNTERS-FIRST
        - SIG-MIPI-DSI-BRIDGE-NO-VIDEO-LP11-HSCLK
        - SIG-NIOS-ELF-AFTER-SOF-HARDWARE-MAP
  eda_drc:
    intent: machine DRC/netlist checks
    read_order:
      - electrical_constraints.json
      - pin_signal_map.json
      - device_profiles.json
    required_keys:
      - drc_rules
      - supply_specs
      - io_standard_specs
      - pin_groups.configuration
  bringup_playbook:
    intent: first article board bring-up checklist
    read_order:
      - debug_readiness_matrix.json
      - diagnostic_evidence_profiles.json
      - electrical_constraints.json
      - pin_signal_map.json
"""


def _debug_readiness_matrix() -> dict[str, Any]:
    return {
        "_schema": f"{POOL_SCHEMA}/debug-readiness-matrix",
        "pool_id": "fpga.intel_agilex5",
        "purpose": "State exactly which DebugTool-style debug needs are satisfied by parsed OpenDatasheet facts and which still require project/bench evidence.",
        "readiness_summary": {
            "satisfies": [
                "first_pass_debug_triage",
                "evidence_request_generation",
                "schematic_preflight_for_debug_observability",
                "datasheet_backed_prior_for_probability_ranking",
            ],
            "does_not_satisfy_without_external_evidence": [
                "final_root_cause_closure",
                "board_instance_net_name_resolution",
                "Quartus_project_IP_instance_binding",
                "live_waveform_or_register_log_interpretation",
            ],
            "decision": "sufficient_for_debugtool_first_pass_and_evidence_planning",
        },
        "coverage_levels": {
            "covered": "Parsed facts directly provide the needed device/package knowledge.",
            "covered_for_first_pass": "Parsed facts are enough to rank hypotheses and request the right first evidence batch.",
            "partial_project_binding_required": "Parsed facts provide capability/pin/constraint priors, but the selected project instance must bind nets, IP parameters, or measured state.",
            "external_required": "Not a datasheet/package fact; must come from project files, lab measurements, or tool logs.",
        },
        "requirements": [
            {
                "id": "fpga_jtag_configuration",
                "debugtool_assets": [
                    "LM-FPGA-JTAG-CONFIG",
                    "SIG-QUARTUS-CABLE-SEEN-SCAN-CHAIN-FAIL",
                    "SIG-JTAG-CABLE-SEEN-NO-TARGET-WAVEFORM",
                ],
                "coverage_level": "covered_for_first_pass",
                "parsed_facts": [
                    "TCK/TMS/TDI/TDO package balls",
                    "nCONFIG/nSTATUS package balls",
                    "MSEL pins via SDM_IO optional functions",
                    "AS/AVST boot pins via SDM_IO optional functions",
                    "OSC_CLK_1 package ball",
                    "SDM/config/core rail names and nominal voltage specs",
                    "Agilex 5 package/device identity for tool mismatch checks",
                ],
                "external_required": [
                    "jtagconfig -n / Quartus Programmer Auto Detect output",
                    "FPGA-end TCK/TMS/TDI/TDO waveforms",
                    "connector VREF, cable power sense, ground, ribbon/adapter continuity",
                    "actual JTAG chain order and bypass-device state",
                    "programming file and Quartus device support version",
                ],
                "known_translation": "Generic CONF_DONE/INIT_DONE checks in FPGA debug recipes must be translated to Agilex 5 nCONFIG/nSTATUS, SDM_IO boot pins, and Quartus status evidence.",
                "meets_debug_need": True,
            },
            {
                "id": "configuration_boot",
                "debugtool_assets": ["LM-FPGA-JTAG-CONFIG"],
                "coverage_level": "covered_for_first_pass",
                "parsed_facts": [
                    "MSEL0/MSEL1/MSEL2 package balls",
                    "AS_CLK/AS_DATA/AS_nCSO/AS_nRST SDM_IO mappings",
                    "AVSTx8 data/ready/valid/clock SDM_IO mappings",
                    "PWRMGT_SCL/PWRMGT_SDA/PWRMGT_ALERT mappings",
                    "POR delay and configuration clock constraints",
                ],
                "external_required": [
                    "selected boot mode from schematic/Quartus settings",
                    "flash or host interface schematic nets",
                    "boot bus activity waveform at FPGA end",
                    "actual pull-up/pull-down and unused SDM_IO policy from schematic",
                ],
                "meets_debug_need": True,
            },
            {
                "id": "power_rail_integrity",
                "debugtool_assets": ["LM-POWER-CHAIN"],
                "coverage_level": "covered_for_first_pass",
                "parsed_facts": [
                    "supply_specs",
                    "power_rails",
                    "absolute maximum ratings",
                    "SmartVID/PMBus-related constraints",
                    "monotonic ramp rule and core/SDM/HPS/GTS rail groupings",
                ],
                "external_required": [
                    "actual regulator topology",
                    "enable/PG dependency graph",
                    "same-window ramp waveforms",
                    "rail noise and brownout measurements",
                    "board net aliases matching rail names",
                ],
                "meets_debug_need": True,
            },
            {
                "id": "gts_transceiver_link",
                "debugtool_assets": ["LM-PCIE-LINK", "SIG-PCIE-REFCLK-MISSING"],
                "coverage_level": "covered_for_first_pass",
                "parsed_facts": [
                    "GTS transceiver channel count and supported protocols",
                    "PCIe 4.0 lane-width capability",
                    "refclk pair package balls and lane group mappings",
                    "common 100 MHz / 156.25 MHz review candidates",
                    "GTS/HSSI rail noise constraints",
                ],
                "external_required": [
                    "selected protocol/IP instance",
                    "actual lane polarity/order and connector mapping",
                    "refclk source schematic and jitter measurement",
                    "PERST#/reset sideband implementation where protocol requires it",
                    "Transceiver Toolkit / PCIe HIP / protocol status logs",
                ],
                "meets_debug_need": True,
            },
            {
                "id": "mipi_dphy_debug",
                "debugtool_assets": [
                    "LM-MIPI-DSI-CSI-DPHY",
                    "SIG-MIPI-CSI-NO-FRAME-PACKET-COUNTERS-FIRST",
                    "SIG-MIPI-DSI-BRIDGE-NO-VIDEO-LP11-HSCLK",
                ],
                "coverage_level": "partial_project_binding_required",
                "parsed_facts": [
                    "package/family MIPI D-PHY interface count",
                    "IO resource capability source traceability",
                ],
                "external_required": [
                    "selected MIPI IP lane count/order/polarity",
                    "project lane-to-ball assignment",
                    "LP11/stopstate/HS clock/data state",
                    "packet counters, VC/data type/ECC/CRC",
                    "source/sink timing and register initialization evidence",
                ],
                "meets_debug_need": True,
                "boundary": "Enough to trigger the right DebugTool path and request the right evidence, not enough to close a MIPI no-frame/no-video root cause alone.",
            },
            {
                "id": "external_memory_interface",
                "debugtool_assets": ["LM-DDR-BRINGUP"],
                "coverage_level": "partial_project_binding_required",
                "parsed_facts": [
                    "supported DDR4/LPDDR4/LPDDR5 standards",
                    "x32 interface count",
                    "DQS/DQ package group hints by bank",
                    "IO voltage constraints",
                ],
                "external_required": [
                    "selected EMIF IP parameters",
                    "memory topology and schematic byte-lane binding",
                    "calibration report/toolkit state",
                    "memory clock/reset/reference voltage measurements",
                ],
                "meets_debug_need": True,
                "boundary": "Enough for review and first evidence request; EMIF calibration closure still needs Quartus/project and lab evidence.",
            },
            {
                "id": "nios_soft_core_debug",
                "debugtool_assets": ["SIG-NIOS-ELF-AFTER-SOF-HARDWARE-MAP"],
                "coverage_level": "partial_project_binding_required",
                "parsed_facts": [
                    "configuration JTAG pins",
                    "device identity/package",
                    "fabric capability prior",
                ],
                "external_required": [
                    "SOF success and jtagconfig -n node list",
                    "sopcinfo/System ID/debug module/JTAG UART",
                    "reset vector, exception vector, memory map, and regenerated hardware image",
                ],
                "meets_debug_need": True,
                "boundary": "OpenDatasheet can anchor JTAG/device facts; Nios failure analysis is necessarily project-file dependent.",
            },
            {
                "id": "hps_hard_processor_debug",
                "debugtool_assets": [],
                "coverage_level": "partial_project_binding_required",
                "parsed_facts": [
                    "A5ED HPS presence and core profile",
                    "HPS rail group",
                    "HPS optional functions for JTAG/UART/SDMMC/EMAC/USB/NAND/TRACE/SPI/I2C/I3C",
                ],
                "external_required": [
                    "selected HPS boot source and pinmux",
                    "HPS reset/clock/rail waveforms",
                    "UART console, boot ROM/error code, debugger/JTAG state",
                    "boot image and secure-boot configuration",
                ],
                "meets_debug_need": True,
                "boundary": "The knowledge pool has enough package facts for HPS debug evidence planning, but DebugTool should add a dedicated HPS boot link model.",
            },
        ],
    }


def build_knowledge_pool(export_dir: Path = DEFAULT_EXPORT_DIR, pattern: str = "A5E*.json") -> dict[str, Any]:
    paths = sorted(path for path in export_dir.glob(pattern) if path.is_file())
    records = []
    for path in paths:
        device = _read_json(path)
        records.append((path, device, build_device_interface(path, device)))

    device_profiles = []
    pin_signal_map = []
    electrical_constraints = []
    diagnostic_profiles = []
    for path, device, profile in records:
        profile_id = profile["debugtool_profile_id"].replace("intel_agilex5:", "fpga.intel_agilex5.")
        common = {
            "profile_id": profile_id,
            "mpn": profile["mpn"],
            "package": profile["package"],
            "source_export": profile["source_export"],
            "source_export_sha256": profile["source_export_sha256"],
        }
        device_profiles.append(
            {
                **common,
                "device_role": profile["device_role"],
                "selectors": profile["selectors"],
                "source_traceability": profile["source_traceability"],
                "capability_blocks": device.get("capability_blocks") or {},
                "facts": profile["facts"],
            }
        )
        pin_signal_map.append(
            {
                **common,
                "pin_groups": profile["pin_groups"],
            }
        )
        electrical_constraints.append(
            {
                **common,
                "rails": profile["rails"],
                "supply_specs": device.get("supply_specs") or {},
                "power_rails": device.get("power_rails") or {},
                "absolute_maximum_ratings": device.get("absolute_maximum_ratings") or {},
                "io_standard_specs": device.get("io_standard_specs") or {},
                "constraint_blocks": device.get("constraint_blocks") or {},
                "drc_rules": device.get("drc_rules") or {},
            }
        )
        diagnostic_profiles.append(
            {
                **common,
                "selectors": profile["selectors"],
                "evidence_apis": {
                    name: _generic_evidence_api(api)
                    for name, api in profile["evidence_apis"].items()
                },
            }
        )

    device_count = len(records)
    return {
        "pool_manifest.yaml": _pool_manifest_yaml(device_count),
        "application_profiles.yaml": _application_profiles_yaml(),
        "device_profiles.json": {
            "_schema": f"{POOL_SCHEMA}/device-profiles",
            "pool_id": "fpga.intel_agilex5",
            "devices": device_profiles,
        },
        "pin_signal_map.json": {
            "_schema": f"{POOL_SCHEMA}/pin-signal-map",
            "pool_id": "fpga.intel_agilex5",
            "devices": pin_signal_map,
        },
        "electrical_constraints.json": {
            "_schema": f"{POOL_SCHEMA}/electrical-constraints",
            "pool_id": "fpga.intel_agilex5",
            "devices": electrical_constraints,
        },
        "diagnostic_evidence_profiles.json": {
            "_schema": f"{POOL_SCHEMA}/diagnostic-evidence-profiles",
            "pool_id": "fpga.intel_agilex5",
            "application_bindings": {"debugtool": DEBUGTOOL_ASSET_MAP},
            "devices": diagnostic_profiles,
        },
        "debug_readiness_matrix.json": _debug_readiness_matrix(),
    }


def write_interface(interface: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as fp:
        json.dump(interface, fp, indent=2, ensure_ascii=False)
        fp.write("\n")


def write_knowledge_pool(pool: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in pool.items():
        path = output_dir / filename
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8", newline="\n")
        else:
            with path.open("w", encoding="utf-8", newline="\n") as fp:
                json.dump(content, fp, indent=2, ensure_ascii=False)
                fp.write("\n")


def _check_text_file(path: Path, rendered: str, label: str) -> bool:
    if not path.exists():
        print(f"Missing {label}: {path}")
        return False
    if path.read_text(encoding="utf-8") != rendered:
        print(f"{label} is stale: {path}")
        return False
    return True


def _check_json_file(path: Path, content: dict[str, Any], label: str) -> bool:
    rendered = json.dumps(content, indent=2, ensure_ascii=False) + "\n"
    return _check_text_file(path, rendered, label)


def check_knowledge_pool(pool: dict[str, Any], output_dir: Path) -> bool:
    ok = True
    for filename, content in pool.items():
        path = output_dir / filename
        if isinstance(content, str):
            ok = _check_text_file(path, content, f"Knowledge pool artifact {filename}") and ok
        else:
            ok = _check_json_file(path, content, f"Knowledge pool artifact {filename}") and ok
    return ok


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a reusable Agilex 5 knowledge pool and DebugTool compatibility interface."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_EXPORT_DIR, help="Directory containing sch-review JSON exports.")
    parser.add_argument("--pattern", default="A5E*.json", help="Glob pattern for Intel Agilex 5 exports.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="DebugTool compatibility JSON output path.")
    parser.add_argument("--pool-dir", type=Path, default=DEFAULT_POOL_DIR, help="Reusable knowledge pool output directory.")
    parser.add_argument("--check", action="store_true", help="Fail if checked-in outputs differ from regenerated content.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    interface = build_debugtool_interface(args.input_dir, args.pattern)
    pool = build_knowledge_pool(args.input_dir, args.pattern)
    if args.check:
        ok = _check_json_file(args.output, interface, "DebugTool compatibility interface")
        ok = check_knowledge_pool(pool, args.pool_dir) and ok
        if ok:
            print(f"Agilex 5 knowledge pool and DebugTool interface are up to date.")
            return 0
        return 1
    write_interface(interface, args.output)
    write_knowledge_pool(pool, args.pool_dir)
    print(f"Wrote {len(interface['devices'])} Agilex 5 DebugTool profiles to {args.output}")
    print(f"Wrote reusable Agilex 5 knowledge pool to {args.pool_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
