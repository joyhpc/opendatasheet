from __future__ import annotations

import copy


def detect_export_format(payload: dict) -> str:
    if "domains" in payload and isinstance(payload["domains"], dict):
        return "domains"
    return "flat"


def _domains(payload: dict) -> dict:
    domains = payload.get("domains", {})
    return domains if isinstance(domains, dict) else {}


def _electrical_domain(payload: dict) -> dict:
    electrical = _domains(payload).get("electrical", {})
    return electrical if isinstance(electrical, dict) else {}


def _pin_domain(payload: dict) -> dict:
    pin = _domains(payload).get("pin", {})
    return pin if isinstance(pin, dict) else {}


def get_export_packages(payload: dict) -> dict:
    packages = _pin_domain(payload).get("packages")
    if isinstance(packages, dict):
        return packages
    return payload.get("packages", {}) if isinstance(payload.get("packages", {}), dict) else {}


def get_export_absolute_maximum_ratings(payload: dict) -> dict:
    abs_max = _electrical_domain(payload).get("absolute_maximum_ratings")
    if isinstance(abs_max, dict):
        return abs_max
    return payload.get("absolute_maximum_ratings", {}) if isinstance(payload.get("absolute_maximum_ratings", {}), dict) else {}


def get_export_electrical_parameters(payload: dict) -> dict:
    elec = _electrical_domain(payload).get("electrical_parameters")
    if isinstance(elec, dict):
        return elec
    return payload.get("electrical_parameters", {}) if isinstance(payload.get("electrical_parameters", {}), dict) else {}


def get_export_drc_hints(payload: dict) -> dict:
    hints = _electrical_domain(payload).get("drc_hints")
    if isinstance(hints, dict):
        return hints
    return payload.get("drc_hints", {}) if isinstance(payload.get("drc_hints", {}), dict) else {}


def get_export_thermal(payload: dict) -> dict:
    thermal = _domains(payload).get("thermal")
    if isinstance(thermal, dict):
        return thermal
    return payload.get("thermal", {}) if isinstance(payload.get("thermal", {}), dict) else {}


def get_export_design_context(payload: dict) -> dict:
    design_context = _domains(payload).get("design_context")
    if isinstance(design_context, dict):
        return design_context
    return payload.get("design_context", {}) if isinstance(payload.get("design_context", {}), dict) else {}


def get_export_register_domain(payload: dict) -> dict:
    register = _domains(payload).get("register")
    return register if isinstance(register, dict) else {}


def normalize_normal_ic_export(payload: dict) -> dict:
    if payload.get("_type") != "normal_ic":
        return copy.deepcopy(payload)

    normalized = copy.deepcopy(payload)
    normalized["packages"] = copy.deepcopy(get_export_packages(payload))
    normalized["absolute_maximum_ratings"] = copy.deepcopy(get_export_absolute_maximum_ratings(payload))
    normalized["electrical_parameters"] = copy.deepcopy(get_export_electrical_parameters(payload))
    normalized["drc_hints"] = copy.deepcopy(get_export_drc_hints(payload))
    normalized["thermal"] = copy.deepcopy(get_export_thermal(payload))
    return normalized
