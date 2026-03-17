#!/usr/bin/env python3
"""Helpers to converge vendor-specific FPGA pinout parses onto a stable schema."""

from __future__ import annotations

import copy
import re


def _safe_upper(value) -> str:
    return (value or "").upper()


def _infer_vendor(device: str, source_file: str | None, current_vendor: str | None) -> str | None:
    if current_vendor:
        return current_vendor
    device_upper = _safe_upper(device)
    source_upper = _safe_upper(source_file)
    if device_upper.startswith("XC") or source_upper.endswith("PKG.TXT"):
        return "AMD"
    if device_upper.startswith("GW"):
        return "Gowin"
    if device_upper.startswith(("ECP5", "LIFCL")):
        return "Lattice"
    if device_upper.startswith("A5E"):
        return "Intel/Altera"
    return current_vendor


def _infer_gowin_family_series(device: str) -> tuple[str | None, str | None]:
    device_upper = _safe_upper(device)
    if device_upper.startswith("GW5AR"):
        return "Arora V", "Arora VR"
    if device_upper.startswith("GW5AS"):
        return "Arora V", "Arora VS"
    if device_upper.startswith("GW5AT"):
        return "Arora V", "Arora VT"
    if device_upper.startswith("GW5A"):
        return "Arora V", "Arora V"
    return None, None


def _infer_amd_family_series(device: str) -> tuple[str | None, str | None]:
    device_upper = _safe_upper(device)
    if device_upper.startswith("XCKU"):
        return "Kintex UltraScale+", "Kintex UltraScale+"
    if device_upper.startswith("XCAU"):
        return "Artix UltraScale+", "Artix UltraScale+"
    if device_upper.startswith("XCVU"):
        return "Virtex UltraScale+", "Virtex UltraScale+"
    if device_upper.startswith("XCVC"):
        return "Versal", "Versal"
    return None, None


def _infer_lattice_family_series(device: str) -> tuple[str | None, str | None]:
    device_upper = _safe_upper(device)
    if device_upper.startswith("ECP5"):
        return "ECP5", "ECP5"
    if device_upper.startswith("LIFCL"):
        return "CrossLink-NX", "CrossLink-NX"
    return None, None


def _infer_intel_identity(device: str, family: str | None, series: str | None, base_device: str | None) -> tuple[str | None, str | None, str | None]:
    family = family or "Agilex 5"
    series = series or "E-Series"
    if not base_device:
        match = re.match(r"^(A5E)[A-Z](\d{3}[AB])$", _safe_upper(device))
        if match:
            base_device = f"{match.group(1)}{match.group(2)}"
    return family, series, base_device


def _infer_identity(data: dict) -> tuple[str | None, str | None, str | None, str | None]:
    device = data.get("device", "")
    source_file = data.get("source_file")
    vendor = _infer_vendor(device, source_file, data.get("_vendor"))
    family = data.get("_family")
    series = data.get("_series")
    base_device = data.get("_base_device") or data.get("device")

    if vendor == "Gowin":
        inferred_family, inferred_series = _infer_gowin_family_series(device)
        family = family or inferred_family
        series = series or inferred_series
    elif vendor == "AMD":
        inferred_family, inferred_series = _infer_amd_family_series(device)
        family = family or inferred_family
        series = series or inferred_series
    elif vendor == "Lattice":
        inferred_family, inferred_series = _infer_lattice_family_series(device)
        family = family or inferred_family
        series = series or inferred_series
    elif vendor == "Intel/Altera":
        family, series, base_device = _infer_intel_identity(device, family, series, base_device)

    return vendor, family, series, base_device


def _infer_polarity(name: str | None) -> str | None:
    if not name:
        return None
    upper = name.upper()
    if upper.endswith(("_P", "P")):
        return "P"
    if upper.endswith(("_N", "N", "M")):
        return "N"
    return None


def _normalize_lookup(lookup: dict | None) -> dict:
    lookup = copy.deepcopy(lookup or {})
    if "pin_to_name" not in lookup and "by_pin" in lookup:
        lookup["pin_to_name"] = lookup["by_pin"]
    if "name_to_pin" not in lookup and "by_name" in lookup:
        lookup["name_to_pin"] = lookup["by_name"]
    return lookup


def _normalize_pin(pin: dict) -> dict:
    normalized = copy.deepcopy(pin)
    if "polarity" not in normalized or normalized.get("polarity") is None:
        inferred = _infer_polarity(normalized.get("name"))
        if inferred:
            normalized["polarity"] = inferred

    canonical = {"pin", "name", "function", "bank", "polarity", "drc", "attrs"}
    attrs = {key: value for key, value in normalized.items() if key not in canonical}
    normalized["attrs"] = attrs
    return normalized


def _normalize_bank(bank_name: str, bank: dict) -> dict:
    normalized = copy.deepcopy(bank)
    normalized.setdefault("bank", bank_name)
    if "total_pins" not in normalized and isinstance(normalized.get("pins"), list):
        normalized["total_pins"] = len(normalized["pins"])
    if "io_pins" not in normalized:
        if "io_count" in normalized:
            normalized["io_pins"] = normalized["io_count"]
        elif isinstance(normalized.get("pins"), list):
            normalized["io_pins"] = len(normalized["pins"])

    canonical = {"bank", "total_pins", "io_pins", "attrs"}
    attrs = {key: value for key, value in normalized.items() if key not in canonical}
    normalized["attrs"] = attrs
    return normalized


def _normalize_diff_pair(index: int, pair: dict) -> dict:
    normalized = copy.deepcopy(pair)
    normalized.setdefault("p_pin", normalized.get("true_pin"))
    normalized.setdefault("n_pin", normalized.get("comp_pin"))
    normalized.setdefault("p_name", normalized.get("true_name"))
    normalized.setdefault("n_name", normalized.get("comp_name"))
    if "pair_name" not in normalized or normalized.get("pair_name") is None:
        normalized["pair_name"] = normalized.get("p_name") or normalized.get("true_name") or f"pair_{index}"

    canonical = {"type", "pair_name", "p_pin", "n_pin", "p_name", "n_name", "bank", "attrs"}
    attrs = {key: value for key, value in normalized.items() if key not in canonical}
    normalized["attrs"] = attrs
    return normalized


def _normalize_source_traceability(data: dict) -> dict | None:
    traceability = copy.deepcopy(data.get("source_traceability") or {})
    package_pinout = copy.deepcopy(traceability.get("package_pinout") or {})
    for key in (
        "source_file",
        "source_document_id",
        "source_url",
        "source_index_url",
        "source_version",
        "source_status",
        "source_revision_note",
    ):
        if key in data and data[key] is not None:
            package_pinout.setdefault(key, data[key])
    if package_pinout:
        traceability["package_pinout"] = package_pinout
    return traceability or None


def normalize_fpga_parse_result(data: dict) -> dict:
    normalized = copy.deepcopy(data)
    vendor, family, series, base_device = _infer_identity(normalized)

    if vendor:
        normalized["_vendor"] = vendor
    if family:
        normalized["_family"] = family
    if series:
        normalized["_series"] = series
    if base_device:
        normalized["_base_device"] = base_device

    normalized["lookup"] = _normalize_lookup(normalized.get("lookup"))
    normalized["pins"] = [_normalize_pin(pin) for pin in normalized.get("pins", [])]
    normalized["banks"] = {
        bank_name: _normalize_bank(bank_name, bank)
        for bank_name, bank in (normalized.get("banks") or {}).items()
    }
    normalized["diff_pairs"] = [
        _normalize_diff_pair(index, pair)
        for index, pair in enumerate(normalized.get("diff_pairs", []), start=1)
    ]

    traceability = _normalize_source_traceability(normalized)
    if traceability:
        normalized["source_traceability"] = traceability

    vendor_extension_keys = [
        key
        for key in ("ordering_variant",)
        if key in normalized and normalized.get(key) is not None
    ]
    normalized["vendor_extensions"] = {
        key: copy.deepcopy(normalized[key]) for key in vendor_extension_keys
    }

    return normalized
