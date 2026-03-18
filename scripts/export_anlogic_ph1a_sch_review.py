#!/usr/bin/env python3
"""Export Anlogic PH1A package-capability parses to sch-review FPGA JSON.

This exporter intentionally works from package-level capability parses rather
than pretending that full ball-map pinouts already exist. It emits synthetic
package anchors so downstream tooling can consume review rules without
mislabeling them as real package pins.
"""

from __future__ import annotations

import json
from pathlib import Path

from build_fpga_catalog import build_catalog

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "anlogic_ph1a"
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


def _package_banks(record: dict) -> dict:
    package_bank_data = record.get("package_io_banks", {}) or {}
    banks = {}
    for bank_id in package_bank_data.get("hr_banks") or []:
        banks[str(bank_id)] = {
            "bank": str(bank_id),
            "bank_type": "HRIO",
            "source": package_bank_data.get("source"),
            "evidence_level": package_bank_data.get("evidence_level"),
            "total_pins": 0,
            "io_pins": 0,
        }
    for bank_id in package_bank_data.get("hp_banks") or []:
        banks[str(bank_id)] = {
            "bank": str(bank_id),
            "bank_type": "HPIO",
            "source": package_bank_data.get("source"),
            "evidence_level": package_bank_data.get("evidence_level"),
            "total_pins": 0,
            "io_pins": 0,
        }
    return banks


def _anchor_pins(record: dict) -> list[dict]:
    package_bank_data = record.get("package_io_banks", {}) or {}
    capability_blocks = record.get("capability_blocks", {}) or {}
    pins: list[dict] = []

    for bank_id in package_bank_data.get("hr_banks") or []:
        pins.append({
            "pin": f"BANK{bank_id}_ANCHOR",
            "name": f"BANK{bank_id}_HRIO_ANCHOR",
            "function": "SPECIAL",
            "bank": str(bank_id),
            "drc": {"must_review": True},
            "attrs": {"synthetic": True, "scope": "package_level_bank", "bank_type": "HRIO"},
        })
    for bank_id in package_bank_data.get("hp_banks") or []:
        pins.append({
            "pin": f"BANK{bank_id}_ANCHOR",
            "name": f"BANK{bank_id}_HPIO_ANCHOR",
            "function": "SPECIAL",
            "bank": str(bank_id),
            "drc": {"must_review": True},
            "attrs": {"synthetic": True, "scope": "package_level_bank", "bank_type": "HPIO"},
        })

    for capability_name in ("memory_interface", "mipi_phy", "high_speed_serial", "pcie"):
        block = capability_blocks.get(capability_name, {}) or {}
        present = block.get("present", True)
        if present is False:
            continue
        pins.append({
            "pin": f"{capability_name.upper()}_ANCHOR",
            "name": f"{capability_name.upper()}_ANCHOR",
            "function": "SPECIAL",
            "bank": None,
            "drc": {"must_review": True},
            "attrs": {"synthetic": True, "scope": "package_level_capability", "capability": capability_name},
        })

    if not pins:
        pins.append({
            "pin": "PACKAGE_CAPABILITY_ANCHOR",
            "name": "PACKAGE_CAPABILITY_ANCHOR",
            "function": "SPECIAL",
            "bank": None,
            "drc": {"must_review": True},
            "attrs": {"synthetic": True, "scope": "package_level_capability"},
        })
    return pins


def _lookup_from_pins(pins: list[dict]) -> dict:
    return {
        "by_pin": {pin["pin"]: pin["name"] for pin in pins if pin.get("pin") and pin.get("name")},
        "by_name": {pin["name"]: pin["pin"] for pin in pins if pin.get("pin") and pin.get("name")},
    }


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


def _constraint_blocks(record: dict, capability_blocks: dict) -> dict:
    blocks = {}
    hs = capability_blocks.get("high_speed_serial", {}) or {}
    if hs.get("present"):
        protocols = hs.get("supported_protocols", []) or []
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
        pcie = capability_blocks.get("pcie", {}) or {}
        if pcie.get("phy_banks"):
            refclk_pair["bank"] = "/".join(str(bank) for bank in pcie.get("phy_banks", []))
            refclk_pair["review_banks"] = pcie.get("phy_banks", [])
        blocks["refclk_requirements"] = {
            "class": "clocking",
            "required": True,
            "selection_required": True,
            "review_required": True,
            "package_level_only": True,
            "source": hs.get("source"),
            "refclk_pair_count": 1,
            "refclk_pairs": [refclk_pair],
            "supported_protocols": protocols,
            "protocol_refclk_profiles": _normalize_protocol_refclk_profiles(protocols),
            "protocol_matrix": hs.get("protocol_matrix", {}),
            "package_rate_ceiling_gbps": hs.get("package_rate_ceiling_gbps"),
            "selection_note": "Current export is package-level only: freeze refclk owner, adjacent-DUAL sharing direction, and protocol-to-bank mapping before schematic sign-off.",
        }
        if hs.get("notes"):
            blocks["refclk_requirements"]["review_notes"] = hs.get("notes")

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
    pins = _anchor_pins(record)
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
        "power_rails": {},
        "banks": _package_banks(record),
        "diff_pairs": [],
        "drc_rules": {},
        "pins": pins,
        "lookup": _lookup_from_pins(pins),
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
        if record.get("_type") == "fpga_family_package_matrix":
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
