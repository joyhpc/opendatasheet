from __future__ import annotations

import copy
from dataclasses import dataclass


SCHEMA_VERSION_V1 = "sch-review-device/1.1"
SCHEMA_VERSION_V2 = "device-knowledge/2.0"


def _non_empty_domains(domains: dict) -> dict:
    filtered = {}
    for key, value in domains.items():
        if value in ({}, [], None):
            continue
        filtered[key] = value
    return filtered


def _canonical_schema_version(domains: dict) -> str:
    return SCHEMA_VERSION_V2 if domains else SCHEMA_VERSION_V1


def _normalize_design_context_domain(design_context: dict) -> dict:
    if not design_context:
        return {}

    pages = []
    for item in design_context.get("design_page_candidates", []):
        if not isinstance(item, dict):
            continue
        page_num = item.get("page_num")
        if page_num is None:
            continue
        pages.append(
            {
                "page": page_num,
                "title": item.get("heading"),
                "content_type": item.get("kind"),
            }
        )

    domain = {
        "recommended_external_components": list(design_context.get("recommended_external_components", [])),
        "component_value_hints": list(design_context.get("component_value_hints", [])),
        "design_range_hints": list(design_context.get("design_range_hints", [])),
        "design_equation_hints": list(design_context.get("design_equation_hints", [])),
        "layout_hints": list(design_context.get("layout_hints", [])),
        "supply_recommendations": list(design_context.get("supply_recommendations", [])),
        "topology_hints": list(design_context.get("topology_hints", [])),
        "configuration_mappings": list(design_context.get("configuration_mappings", [])),
        "design_recommendations": list(design_context.get("design_recommendations", [])),
    }
    if pages:
        domain["design_pages"] = {
            "pages": pages,
            "total_pages": len(pages),
        }
    return _non_empty_domains(domain)


def build_normal_ic_domains(
    *,
    packages: dict,
    abs_max: dict,
    elec_params: dict,
    drc_hints: dict,
    thermal: dict,
    design_context: dict,
    register_data: dict,
    timing_data: dict,
    power_seq_data: dict,
    parametric_data: dict,
    protocol_data: dict,
    package_data: dict,
) -> dict:
    return _non_empty_domains(
        {
            "pin": {"packages": copy.deepcopy(packages)} if packages else {},
            "electrical": {
                "absolute_maximum_ratings": copy.deepcopy(abs_max),
                "electrical_parameters": copy.deepcopy(elec_params),
                "drc_hints": copy.deepcopy(drc_hints),
            } if (abs_max or elec_params or drc_hints) else {},
            "thermal": copy.deepcopy(thermal) if thermal else {},
            "design_context": _normalize_design_context_domain(design_context),
            "register": copy.deepcopy(register_data) if register_data else {},
            "timing": copy.deepcopy(timing_data) if timing_data else {},
            "power_sequence": copy.deepcopy(power_seq_data) if power_seq_data else {},
            "parametric": copy.deepcopy(parametric_data) if parametric_data else {},
            "protocol": copy.deepcopy(protocol_data) if protocol_data else {},
            "package": copy.deepcopy(package_data) if package_data else {},
        }
    )


@dataclass(frozen=True)
class NormalIcRecord:
    mpn: str
    manufacturer: str | None
    category: str
    description: str | None
    layers: list[str]
    packages: dict
    absolute_maximum_ratings: dict
    electrical_parameters: dict
    drc_hints: dict
    thermal: dict
    domains: dict

    @property
    def schema_version(self) -> str:
        return _canonical_schema_version(self.domains)


def build_normal_ic_record(
    *,
    mpn: str,
    manufacturer: str | None,
    category: str,
    description: str | None,
    packages: dict,
    abs_max: dict,
    elec_params: dict,
    drc_hints: dict,
    thermal: dict,
    design_context: dict,
    register_data: dict,
    timing_data: dict,
    power_seq_data: dict,
    parametric_data: dict,
    protocol_data: dict,
    package_data: dict,
) -> NormalIcRecord:
    layers = ["L0_skeleton"]
    if elec_params or abs_max:
        layers.append("L1_electrical")

    domains = build_normal_ic_domains(
        packages=packages,
        abs_max=abs_max,
        elec_params=elec_params,
        drc_hints=drc_hints,
        thermal=thermal,
        design_context=design_context,
        register_data=register_data,
        timing_data=timing_data,
        power_seq_data=power_seq_data,
        parametric_data=parametric_data,
        protocol_data=protocol_data,
        package_data=package_data,
    )

    return NormalIcRecord(
        mpn=mpn,
        manufacturer=manufacturer,
        category=category,
        description=description,
        layers=copy.deepcopy(layers),
        packages=copy.deepcopy(packages),
        absolute_maximum_ratings=copy.deepcopy(abs_max),
        electrical_parameters=copy.deepcopy(elec_params),
        drc_hints=copy.deepcopy(drc_hints),
        thermal=copy.deepcopy(thermal),
        domains=copy.deepcopy(domains),
    )


def normal_ic_record_to_export(
    record: NormalIcRecord,
    *,
    capability_blocks: dict | None = None,
    constraint_blocks: dict | None = None,
) -> dict:
    result = {
        "_schema": record.schema_version,
        "_type": "normal_ic",
        "_layers": copy.deepcopy(record.layers),
        "mpn": record.mpn,
        "manufacturer": record.manufacturer,
        "category": record.category,
        "description": record.description,
        "packages": copy.deepcopy(record.packages),
        "absolute_maximum_ratings": copy.deepcopy(record.absolute_maximum_ratings),
        "electrical_parameters": copy.deepcopy(record.electrical_parameters),
        "drc_hints": copy.deepcopy(record.drc_hints),
        "thermal": copy.deepcopy(record.thermal),
    }
    if capability_blocks:
        result["capability_blocks"] = copy.deepcopy(capability_blocks)
    if constraint_blocks:
        result["constraint_blocks"] = copy.deepcopy(constraint_blocks)
    if record.domains:
        result["domains"] = copy.deepcopy(record.domains)
    return result
