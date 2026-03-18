#!/usr/bin/env python3
"""Export Anlogic PH1A pinout parses to sch-review FPGA JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path

from build_fpga_catalog import build_catalog

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "pinout"
OUTPUT_DIR = REPO_ROOT / "data" / "sch_review_export"
CATALOG_PATH = OUTPUT_DIR / "_fpga_catalog.json"
SCHEMA_VERSION = "sch-review-device/1.1"


def _protocol_bundle_context(protocols: list[str]) -> dict:
    bundle_tags: list[str] = []
    use_case_tags: list[str] = []

    def add_unique(target: list[str], value: str) -> None:
        if value and value not in target:
            target.append(value)

    if protocols:
        add_unique(bundle_tags, "SerDes")
        add_unique(bundle_tags, "clock")
        add_unique(use_case_tags, "high_speed_link")

    if any(protocol.startswith("PCIe") or protocol == "PCI Express" for protocol in protocols):
        add_unique(bundle_tags, "PCIe")
        add_unique(use_case_tags, "pcie_link")
    if any(protocol in ("SGMII", "1000BASE-KX", "XAUI", "RXAUI", "10GBASE-KR", "10GBASE-KX4") for protocol in protocols):
        add_unique(bundle_tags, "Ethernet")
        add_unique(use_case_tags, "ethernet_link")

    return {
        "bundle_tags": bundle_tags,
        "use_case_tags": use_case_tags,
    }


def _normalize_protocol_refclk_profiles(protocols: list[str] | None) -> dict:
    profiles = {}
    protocol_map = {
        "PCI Express": [100.0],
        "SGMII": [125.0],
        "1000BASE-KX": [125.0],
        "QSGMII": [125.0],
        "XAUI": [156.25],
        "RXAUI": [156.25],
        "10GBASE-KX4": [156.25],
        "10GBASE-KR": [156.25],
        "JESD204B": [62.5, 125.0, 156.25, 250.0],
        "SRIO": [125.0, 156.25],
        "CEI": [156.25],
        "CPRI": [122.88, 153.6, 245.76],
    }
    for protocol in protocols or []:
        freqs = protocol_map.get(protocol)
        if freqs:
            profiles[protocol] = {
                "frequencies_mhz": freqs,
                "source": "package_level_protocol_review",
            }
    return profiles


def _capability_blocks(record: dict) -> dict:
    blocks = json.loads(json.dumps(record.get("capability_blocks", {}) or {}))
    defaults = {
        "memory_interface": "memory_interface",
        "mipi_phy": "mipi_phy",
        "high_speed_serial": "high_speed_serial",
        "pcie": "pcie",
    }
    for key, class_name in defaults.items():
        if isinstance(blocks.get(key), dict):
            blocks[key].setdefault("class", class_name)
            if key == "high_speed_serial":
                lane_pairs = blocks[key].get("channel_pairs")
                if lane_pairs is not None:
                    blocks[key].setdefault("rx_lane_pairs", lane_pairs)
                    blocks[key].setdefault("tx_lane_pairs", lane_pairs)
    return blocks


def _normalize_pins_for_export(pins: list[dict]) -> list[dict]:
    function_map = {
        "MIPI": "IO",
        "SERDES_RX": "GT",
        "SERDES_TX": "GT",
        "SERDES_REFCLK": "GT",
    }
    normalized = []
    for pin in pins or []:
        entry = json.loads(json.dumps(pin))
        raw_function = entry.get("function")
        entry["function"] = function_map.get(raw_function, raw_function)
        attrs = entry.setdefault("attrs", {})
        if raw_function != entry.get("function"):
            attrs.setdefault("raw_function", raw_function)
        normalized.append(entry)
    return normalized


def _refclk_pairs(record: dict, protocols: list[str], pcie: dict) -> list[dict]:
    pairs = []
    for pair in record.get("diff_pairs", []) or []:
        pair_type = pair.get("type")
        if pair_type not in {"SERDES_REFCLK", "GT_REFCLK", "REFCLK"}:
            continue
        refclk_pair = {
            "type": "REFCLK",
            "pair_name": pair.get("pair_name"),
            "p_pin": pair.get("p_pin"),
            "n_pin": pair.get("n_pin"),
            "p_name": pair.get("p_name"),
            "n_name": pair.get("n_name"),
            "bank": pair.get("bank"),
            "source": "official_pinlist",
            "package_level_only": False,
            "candidate_protocols": protocols,
        }
        refclk_pair.update(_protocol_bundle_context(protocols))
        if pcie.get("phy_banks"):
            refclk_pair["review_banks"] = pcie.get("phy_banks", [])
        pairs.append(refclk_pair)
    return pairs


def _lane_index(pair_name: str | None) -> int | None:
    text = pair_name or ""
    match = None
    for pattern in (r"^[RT]X(\d+)_\d+$", r"^REFCLK_(\d+)$", r"^DPHY\d+_D(\d+)$"):
        match = re.match(pattern, text)
        if match:
            return int(match.group(1))
    return None


def _lane_group_mappings(record: dict, refclk_pairs: list[dict], protocols: list[str], protocol_matrix: dict | None) -> tuple[list[dict], list[dict]]:
    protocol_matrix = protocol_matrix or {}
    groups: dict[str, dict] = {}
    for pair in record.get("diff_pairs", []) or []:
        pair_type = pair.get("type")
        bank = pair.get("bank")
        if pair_type not in {"SERDES_RX", "SERDES_TX", "GT_RX", "GT_TX"} or not bank:
            continue
        group_id = str(bank)
        entry = groups.setdefault(
            group_id,
            {
                "group_id": group_id,
                "group_type": "bank",
                "bank": str(bank),
                "rx_pair_names": [],
                "tx_pair_names": [],
                "lane_indices": [],
                "refclk_pair_names": [],
                "refclk_indices": [],
                "source": "bank_level_pinout_inference",
            },
        )
        if pair_type in {"SERDES_RX", "GT_RX"} and pair.get("pair_name"):
            entry["rx_pair_names"].append(pair["pair_name"])
        if pair_type in {"SERDES_TX", "GT_TX"} and pair.get("pair_name"):
            entry["tx_pair_names"].append(pair["pair_name"])
        lane_index = _lane_index(pair.get("pair_name"))
        if lane_index is not None:
            entry["lane_indices"].append(lane_index)

    enriched_refclk_pairs = []
    for pair in refclk_pairs:
        entry = dict(pair)
        bank = str(pair.get("bank")) if pair.get("bank") is not None else None
        if bank and bank in groups:
            entry["group_id"] = bank
            entry["mapped_lane_groups"] = [bank]
            groups[bank]["refclk_pair_names"].append(pair.get("pair_name"))
            refclk_index = _lane_index(pair.get("pair_name"))
            if refclk_index is not None:
                entry["refclk_index"] = refclk_index
                groups[bank]["refclk_indices"].append(refclk_index)
        enriched_refclk_pairs.append(entry)

    lane_group_mappings = []
    for group_id in sorted(groups):
        entry = dict(groups[group_id])
        entry["rx_pair_names"] = sorted(set(entry["rx_pair_names"]))
        entry["tx_pair_names"] = sorted(set(entry["tx_pair_names"]))
        entry["lane_indices"] = sorted(set(entry["lane_indices"]))
        entry["refclk_pair_names"] = sorted(set(entry["refclk_pair_names"]))
        entry["refclk_indices"] = sorted(set(entry["refclk_indices"]))
        max_lane_pairs = min(len(entry["rx_pair_names"]), len(entry["tx_pair_names"])) or max(len(entry["rx_pair_names"]), len(entry["tx_pair_names"]))
        entry["max_lane_pairs"] = max_lane_pairs
        candidate_protocols = []
        protocol_lane_widths = {}
        for protocol, meta in protocol_matrix.items():
            lane_widths = [width for width in (meta or {}).get("lane_widths", []) if isinstance(width, int) and width <= max_lane_pairs]
            if lane_widths:
                candidate_protocols.append(protocol)
                protocol_lane_widths[protocol] = lane_widths
        if not candidate_protocols:
            candidate_protocols = list(protocols)
        entry["candidate_protocols"] = candidate_protocols
        if protocol_lane_widths:
            entry["protocol_lane_widths"] = protocol_lane_widths
        entry["selection_required"] = bool(candidate_protocols)
        if candidate_protocols:
            entry["selection_note"] = "Freeze the protocol/IP assignment for this bank-level lane group and bind it to one of the mapped refclk pairs before schematic sign-off."
            entry.update(_protocol_bundle_context(candidate_protocols))
        lane_group_mappings.append(entry)

    group_map = {group["group_id"]: group for group in lane_group_mappings}
    final_refclk_pairs = []
    for pair in enriched_refclk_pairs:
        entry = dict(pair)
        protocols_for_pair = []
        protocol_lane_widths = {}
        for group_id in entry.get("mapped_lane_groups", []) or []:
            group = group_map.get(group_id, {})
            for protocol in group.get("candidate_protocols", []) or []:
                if protocol not in protocols_for_pair:
                    protocols_for_pair.append(protocol)
            for protocol, widths in (group.get("protocol_lane_widths", {}) or {}).items():
                protocol_lane_widths.setdefault(protocol, [])
                protocol_lane_widths[protocol] = sorted(set(protocol_lane_widths[protocol]) | set(widths))
        if protocols_for_pair:
            entry["candidate_protocols"] = protocols_for_pair
            entry.update(_protocol_bundle_context(protocols_for_pair))
        if protocol_lane_widths:
            entry["protocol_lane_widths"] = protocol_lane_widths
        final_refclk_pairs.append(entry)
    return final_refclk_pairs, lane_group_mappings


def _constraint_blocks(record: dict, capability_blocks: dict) -> dict:
    blocks = {}
    hs = capability_blocks.get("high_speed_serial", {}) or {}
    if hs.get("present"):
        protocols = hs.get("supported_protocols", []) or []
        pcie = capability_blocks.get("pcie", {}) or {}
        refclk_pairs = _refclk_pairs(record, protocols, pcie)
        lane_group_mappings = []
        package_level_only = not bool(refclk_pairs)
        if refclk_pairs:
            refclk_pairs, lane_group_mappings = _lane_group_mappings(record, refclk_pairs, protocols, hs.get("protocol_matrix"))
        if not refclk_pairs:
            refclk_pair = {
                "type": "REFCLK",
                "pair_name": "PACKAGE_REFCLK_ANCHOR",
                "p_pin": "REFCLK_P_ANCHOR",
                "n_pin": "REFCLK_N_ANCHOR",
                "p_name": "REFCLK_P_ANCHOR",
                "n_name": "REFCLK_N_ANCHOR",
                "package_level_only": True,
                "candidate_protocols": protocols,
                "source": hs.get("source"),
            }
            refclk_pair.update(_protocol_bundle_context(protocols))
            if pcie.get("phy_banks"):
                refclk_pair["bank"] = "/".join(str(bank) for bank in pcie.get("phy_banks", []))
                refclk_pair["review_banks"] = pcie.get("phy_banks", [])
            refclk_pairs = [refclk_pair]
        blocks["refclk_requirements"] = {
            "class": "clocking",
            "required": True,
            "selection_required": True,
            "review_required": True,
            "package_level_only": package_level_only,
            "source": hs.get("source"),
            "refclk_pair_count": len(refclk_pairs),
            "refclk_pairs": refclk_pairs,
            "supported_protocols": protocols,
            "protocol_refclk_profiles": _normalize_protocol_refclk_profiles(protocols),
            "protocol_matrix": hs.get("protocol_matrix", {}),
            "package_rate_ceiling_gbps": hs.get("package_rate_ceiling_gbps"),
            "selection_note": (
                "Official pinlist exposes concrete REFCLK pairs; freeze refclk owner, bank ownership, and protocol mapping before schematic sign-off."
                if not package_level_only
                else "Current export is package-level only: freeze refclk owner, adjacent-DUAL sharing direction, and protocol-to-bank mapping before schematic sign-off."
            ),
        }
        if hs.get("notes"):
            blocks["refclk_requirements"]["review_notes"] = hs.get("notes")
        if lane_group_mappings:
            blocks["refclk_requirements"]["lane_group_mappings"] = lane_group_mappings

    memory = capability_blocks.get("memory_interface", {}) or {}
    package_banks = record.get("package_io_banks", {}) or {}
    if memory.get("present"):
        blocks["memory_interface_review"] = {
            "class": "memory_interface",
            "required": True,
            "review_required": True,
            "source": memory.get("source"),
            "supported_standards": memory.get("supported_standards", []),
            "max_rate_mbps": memory.get("max_rate_mbps"),
            "max_data_width_bits": memory.get("max_data_width_bits"),
            "preferred_hp_banks": package_banks.get("hp_banks"),
            "selection_note": "Freeze DDR bank ownership, byte-group placement, and VREF strategy against the exact package before schematic sign-off.",
        }
        if memory.get("notes"):
            blocks["memory_interface_review"]["review_notes"] = memory.get("notes")

    mipi = capability_blocks.get("mipi_phy", {}) or {}
    if "present" in mipi:
        blocks["mipi_phy"] = {
            "class": "clocking",
            "review_required": bool(mipi.get("present")),
            "directions": mipi.get("directions", []),
            "source": mipi.get("source"),
        }

    pcie = capability_blocks.get("pcie", {}) or {}
    if pcie:
        blocks["pcie_review"] = {
            "class": "high_speed_serial",
            "review_required": pcie.get("present") is not False,
            "present": pcie.get("present"),
            "phy_banks": pcie.get("phy_banks", []),
            "max_link_width": pcie.get("max_link_width"),
            "generations": pcie.get("generations", []),
            "source": pcie.get("source"),
        }
        if pcie.get("notes"):
            blocks["pcie_review"]["review_notes"] = pcie.get("notes")

    if record.get("source_conflicts"):
        blocks["source_consistency_review"] = {
            "class": "source_consistency",
            "review_required": True,
            "conflicts": record.get("source_conflicts"),
            "selection_note": "Package-level facts disagree across official locales; do not freeze board assumptions until the exact package capability is re-confirmed.",
        }
    return blocks


def _export_record(record: dict) -> dict:
    device = record["device"]
    package = record["package"]
    capability_blocks = _capability_blocks(record)
    result = {
        "_schema": SCHEMA_VERSION,
        "_type": "fpga",
        "mpn": device,
        "manufacturer": "Anlogic",
        "category": "FPGA",
        "description": None,
        "package": package,
        "device_identity": record["device_identity"],
        "supply_specs": {},
        "io_standard_specs": {},
        "thermal": {},
        "power_rails": record.get("power_rails", {}),
        "banks": record.get("banks", {}),
        "diff_pairs": record.get("diff_pairs", []),
        "drc_rules": record.get("drc_rules", {}),
        "pins": _normalize_pins_for_export(record.get("pins", [])),
        "lookup": record.get("lookup", {}),
        "summary": record.get("summary", {}),
        "resources": record.get("resources"),
        "package_info": record.get("package_info"),
        "package_summary": record.get("package_summary"),
        "package_io_banks": record.get("package_io_banks"),
        "source_conflicts": record.get("source_conflicts"),
        "source_traceability": record.get("source_traceability"),
        "capability_blocks": capability_blocks,
        "constraint_blocks": _constraint_blocks(record, capability_blocks),
    }
    return result


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for path in sorted(INPUT_DIR.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("_vendor") != "Anlogic" or not str(record.get("device", "")).startswith("PH1A"):
            continue
        result = _export_record(record)
        out_path = OUTPUT_DIR / f"{result['mpn']}.json"
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written += 1

    catalog = build_catalog(OUTPUT_DIR)
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {written} Anlogic FPGA sch-review exports")
    print(f"updated {CATALOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
