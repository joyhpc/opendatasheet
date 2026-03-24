#!/usr/bin/env python3
"""Normalize automotive serializer/deserializer devices into a shared model.

This script is intentionally isolated from the main exporter so we can enrich
existing checked-in data without coupling the normalization policy to the
already-busy export pipeline.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_PATH = REPO_ROOT / "data" / "normalization" / "automotive_video_serdes_profiles.json"
DEFAULT_EXTRACTED_DIR = REPO_ROOT / "data" / "extracted_v2"
DEFAULT_EXPORT_DIR = REPO_ROOT / "data" / "sch_review_export"
DEFAULT_SELECTION_DIR = REPO_ROOT / "data" / "selection_profile"


def _load_json(path: Path) -> dict:
    with path.open() as fp:
        return json.load(fp)


def _write_json(path: Path, payload: dict) -> None:
    with path.open("w") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
        fp.write("\n")


def _ensure_dict(payload: dict, key: str) -> dict:
    value = payload.get(key)
    if not isinstance(value, dict):
        value = {}
        payload[key] = value
    return value


def _set_component_category(payload: dict, category: str) -> None:
    extraction = payload.get("extraction")
    if isinstance(extraction, dict):
        component = extraction.get("component")
        if isinstance(component, dict):
            component["category"] = category

    domains = payload.get("domains")
    if isinstance(domains, dict):
        electrical = domains.get("electrical")
        if isinstance(electrical, dict):
            component = electrical.get("component")
            if isinstance(component, dict):
                component["category"] = category


def _selection_features(profile: dict) -> list[str]:
    bridge = profile.get("serial_video_bridge", {})
    features = ["function:automotive_video_serdes"]
    role = bridge.get("device_role")
    if role:
        features.append(f"role:{role}")
    system_path = bridge.get("system_path")
    if system_path:
        features.append(f"system_path:{system_path}")
    for family in bridge.get("link_families", []) or []:
        features.append(f"link_family:{family.lower()}")
    video_output = bridge.get("video_output", {})
    protocol = video_output.get("protocol")
    if protocol:
        features.append(f"video_output:{protocol.lower().replace(' ', '_')}")
    for phy in video_output.get("phy_types", []) or []:
        features.append(f"phy:{phy.lower()}")
    return features


def _system_path_review_items(system_path: str | None) -> list[str]:
    if system_path == "camera_module_to_domain_controller":
        return [
            "Freeze coax vs STP assumptions, connector ownership, and PoC policy for the selected serial link.",
            "Freeze D-PHY vs C-PHY mode and lane/trio allocation against the downstream SoC or bridge.",
            "Verify sensor-control tunneling, lock observability, frame-sync ownership, and sideband GPIO usage.",
        ]
    if system_path == "domain_controller_to_display":
        return [
            "Freeze serial-link family, cable topology, display connector ownership, and any PoC or remote-power policy.",
            "Freeze display-side timing, bridge or panel compatibility, and video-format mapping before schematic sign-off.",
            "Verify blanking, reset, lock-loss recovery, and sideband control behavior for the display path.",
        ]
    return [
        "Freeze link family, transport media, connector ownership, and power-delivery assumptions for the selected serial link.",
        "Freeze downstream protocol mode, PHY allocation, and sink compatibility before schematic sign-off.",
        "Verify reset, control-channel ownership, lock status observability, and sideband GPIO usage.",
    ]


def _build_serial_video_bridge_constraint(profile: dict) -> dict:
    bridge = profile["serial_video_bridge"]
    video_output = bridge.get("video_output", {})
    system_path = bridge.get("system_path")
    return {
        "class": "interface",
        "review_required": True,
        "device_role": bridge.get("device_role"),
        "system_path": system_path,
        "link_families": bridge.get("link_families", []),
        "video_protocol": video_output.get("protocol"),
        "phy_types": video_output.get("phy_types", []),
        "selection_note": "Freeze serial-link family, transport media, CSI-2 PHY mode, and downstream receiver compatibility before schematic sign-off.",
        "review_items": _system_path_review_items(system_path),
        "source": bridge.get("source_basis", "manual_profile"),
    }


def _derive_mipi_phy_from_bridge(profile: dict) -> dict | None:
    bridge = profile.get("serial_video_bridge", {})
    video_output = bridge.get("video_output", {})
    phy_types = video_output.get("phy_types", [])
    if not phy_types:
        return None

    block = {
        "class": "mipi_phy",
        "present": True,
        "phy_types": list(phy_types),
        "directions": [video_output.get("direction", "TX")],
        "transport": video_output.get("protocol"),
        "source": bridge.get("source_basis", "manual_profile"),
    }

    dphy = video_output.get("dphy")
    if isinstance(dphy, dict) and dphy:
        block["dphy"] = copy.deepcopy(dphy)
        block["dphy"]["port_count"] = video_output.get("port_count")

    cphy = video_output.get("cphy")
    if isinstance(cphy, dict) and cphy:
        block["cphy"] = copy.deepcopy(cphy)
        block["cphy"]["port_count"] = video_output.get("port_count")

    source_pages = []
    for section in (video_output, dphy or {}, cphy or {}):
        if isinstance(section, dict):
            for page in section.get("source_pages", []) or []:
                if isinstance(page, int) and page not in source_pages:
                    source_pages.append(page)
    if source_pages:
        block["source_pages"] = source_pages
    return block


def normalize_extracted(payload: dict, profile: dict) -> dict:
    normalized = copy.deepcopy(payload)
    _set_component_category(normalized, profile["category"])

    protocol_domain = profile.get("protocol_domain")
    if protocol_domain:
        domains = _ensure_dict(normalized, "domains")
        domains["protocol"] = copy.deepcopy(protocol_domain)

    return normalized


def normalize_export(payload: dict, profile: dict) -> dict:
    normalized = copy.deepcopy(payload)
    normalized["category"] = profile["category"]

    capability_blocks = _ensure_dict(normalized, "capability_blocks")
    capability_blocks["serial_video_bridge"] = copy.deepcopy(profile["serial_video_bridge"])

    mipi_phy = _derive_mipi_phy_from_bridge(profile)
    if mipi_phy:
        capability_blocks.setdefault("mipi_phy", mipi_phy)

    constraint_blocks = _ensure_dict(normalized, "constraint_blocks")
    constraint_blocks["serial_video_bridge"] = _build_serial_video_bridge_constraint(profile)
    if mipi_phy and "mipi_phy" not in constraint_blocks:
        constraint_blocks["mipi_phy"] = {
            "class": "clocking",
            "review_required": True,
            "directions": mipi_phy.get("directions", []),
            "phy_types": mipi_phy.get("phy_types", []),
            "source": mipi_phy.get("source"),
        }

    protocol_domain = profile.get("protocol_domain")
    if protocol_domain:
        domains = _ensure_dict(normalized, "domains")
        domains["protocol"] = copy.deepcopy(protocol_domain)

    return normalized


def normalize_selection(payload: dict, profile: dict) -> dict:
    normalized = copy.deepcopy(payload)
    normalized["category"] = profile["category"]

    features = list(normalized.get("features", []))
    for feature in _selection_features(profile):
        if feature not in features:
            features.append(feature)
    normalized["features"] = features
    return normalized


def apply_profiles(
    *,
    profiles: dict,
    extracted_dir: Path,
    export_dir: Path,
    selection_dir: Path,
) -> list[str]:
    written = []
    for mpn, profile in profiles.items():
        status = profile.get("status", "active")
        if status != "active":
            print(f"skip {mpn}: status={status}")
            continue

        extracted_path = extracted_dir / profile["extracted_file"]
        export_path = export_dir / profile["export_file"]
        selection_path = selection_dir / profile["selection_file"]

        missing = [str(path) for path in (extracted_path, export_path, selection_path) if not path.exists()]
        if missing:
            print(f"skip {mpn}: missing files {', '.join(missing)}")
            continue

        extracted = normalize_extracted(_load_json(extracted_path), profile)
        exported = normalize_export(_load_json(export_path), profile)
        selection = normalize_selection(_load_json(selection_path), profile)

        _write_json(extracted_path, extracted)
        _write_json(export_path, exported)
        _write_json(selection_path, selection)
        written.extend([str(extracted_path), str(export_path), str(selection_path)])
        print(f"normalized {mpn}")
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE_PATH)
    parser.add_argument("--extracted-dir", type=Path, default=DEFAULT_EXTRACTED_DIR)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--selection-dir", type=Path, default=DEFAULT_SELECTION_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile_payload = _load_json(args.profile)
    profiles = profile_payload.get("devices", {})
    if not isinstance(profiles, dict) or not profiles:
        raise SystemExit("no profiles found")

    apply_profiles(
        profiles=profiles,
        extracted_dir=args.extracted_dir,
        export_dir=args.export_dir,
        selection_dir=args.selection_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
