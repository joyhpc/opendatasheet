from __future__ import annotations

import copy
import re
from dataclasses import dataclass


SCHEMA_VERSION_V1 = "sch-review-device/1.1"
SCHEMA_VERSION_V2 = "device-knowledge/2.0"
FORMULA_LHS_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_\-()]*)\s*=")
FORMULA_VARIABLE_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_\-()]*\b")
DESIGNATOR_RE = re.compile(r"\b(?:[RCLQDS]\d+|RILIM|RSENSE|RTERM|CLINK|CIN|COUT|RS|RO|RF|RIN)\b", re.IGNORECASE)
MATH_TOKENS = {"AND", "OR", "MIN", "MAX", "TO"}
ROLE_COMPONENT_TYPES = {
    "input_capacitor": "capacitor",
    "output_capacitor": "capacitor",
    "bootstrap_capacitor": "capacitor",
    "soft_start_capacitor": "capacitor",
    "dvdt_capacitor": "capacitor",
    "snubber_capacitor": "capacitor",
    "link_isolation_capacitor": "capacitor",
    "inductor": "inductor",
    "poc_inductor": "inductor",
    "feedback_divider": "resistor_network",
    "uvlo_divider": "resistor_network",
    "ovp_divider": "resistor_network",
    "pullup_resistor": "resistor",
    "current_limit_resistor": "resistor",
    "gain_resistor": "resistor",
    "sense_resistor": "resistor",
    "line_fault_resistor": "resistor",
    "termination_resistor": "resistor",
    "snubber_resistor": "resistor",
}
NOTE_TOPIC_CATEGORY_MAP = {
    "layout": "pcb_layout",
    "mode_pin_configuration": "configuration",
    "recommended_component_values": "component_selection",
    "feedback_divider_bias": "component_selection",
}


def _non_empty_domains(domains: dict) -> dict:
    filtered = {}
    for key, value in domains.items():
        if value in ({}, [], None):
            continue
        filtered[key] = value
    return filtered


def _canonical_schema_version(domains: dict) -> str:
    return SCHEMA_VERSION_V2 if domains else SCHEMA_VERSION_V1


def _canonical_symbol(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"[^A-Z0-9]+", "", str(text).upper())


def _title_by_page(design_context: dict) -> dict[int, str | None]:
    titles: dict[int, str | None] = {}
    for item in design_context.get("design_page_candidates", []):
        if not isinstance(item, dict):
            continue
        page_num = item.get("page_num")
        if page_num is None:
            continue
        titles[page_num] = item.get("heading")
    return titles


def _build_electrical_lookup(elec_params: dict) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for key, value in (elec_params or {}).items():
        if not isinstance(value, dict):
            continue
        symbol = value.get("symbol") or key
        canonical = _canonical_symbol(symbol)
        if canonical and canonical not in lookup:
            lookup[canonical] = value
    return lookup


def _pick_typical_value(entry: dict) -> float | int | str | None:
    for field in ("typ", "value", "max", "min"):
        value = entry.get(field)
        if value is not None:
            return value
    return None


def _infer_formula_name(item: dict, equation: str) -> str:
    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()

    match = FORMULA_LHS_RE.match(equation)
    base = match.group(1) if match else (item.get("topic") or "formula")
    suffix = item.get("category") or item.get("topic")
    safe = re.sub(r"[^A-Za-z0-9]+", "_", f"{base}_{suffix}" if suffix else base).strip("_")
    return safe or "formula"


def _infer_formula_variables(equation: str, explicit: dict, elec_lookup: dict[str, dict]) -> dict:
    variables: dict[str, dict] = copy.deepcopy(explicit or {})
    tokens = []
    for token in FORMULA_VARIABLE_RE.findall(equation):
        if token.isupper() and token in MATH_TOKENS:
            continue
        if token not in tokens:
            tokens.append(token)

    lhs_match = FORMULA_LHS_RE.match(equation)
    lhs = lhs_match.group(1) if lhs_match else None

    for token in tokens:
        entry = variables.setdefault(token, {})
        if token == lhs:
            entry.setdefault("is_output", True)
        canonical = _canonical_symbol(token)
        ref = entry.get("refers_to")
        if not ref and canonical in elec_lookup:
            ref = elec_lookup[canonical].get("symbol") or token
            entry["refers_to"] = ref
        if ref:
            param = elec_lookup.get(_canonical_symbol(ref), {})
            if param:
                if param.get("unit") and entry.get("unit") is None:
                    entry["unit"] = param.get("unit")
                if param.get("parameter") and entry.get("description") is None:
                    entry["description"] = param.get("parameter")
                typical = _pick_typical_value(param)
                if typical is not None and entry.get("typical") is None:
                    entry["typical"] = typical
        elif token != lhs:
            entry.setdefault("is_input", True)
    return variables


def _formula_source(item: dict, page_titles: dict[int, str | None]) -> dict:
    source = copy.deepcopy(item.get("source", {})) if isinstance(item.get("source"), dict) else {}
    page = item.get("source_page")
    if page is None and isinstance(source, dict):
        page = source.get("page")
    if page is not None:
        source["page"] = page
        if source.get("section") is None and page in page_titles and page_titles[page]:
            source["section"] = page_titles[page]
    return source


def _derive_design_formulas(design_context: dict, elec_params: dict) -> list[dict]:
    page_titles = _title_by_page(design_context)
    elec_lookup = _build_electrical_lookup(elec_params)
    formulas = []
    seen = set()

    def append_formula(item: dict, *, default_category: str | None = None, default_purpose: str | None = None) -> None:
        equation = item.get("equation")
        if not isinstance(equation, str) or "=" not in equation:
            return
        normalized = equation.strip()
        source = _formula_source(item, page_titles)
        marker = (
            _infer_formula_name(item, normalized),
            normalized,
            source.get("page"),
            item.get("topic"),
        )
        if marker in seen:
            return
        seen.add(marker)
        entry = {
            "name": _infer_formula_name(item, normalized),
            "formula": normalized,
            "variables": _infer_formula_variables(normalized, item.get("variables", {}), elec_lookup),
            "source": source,
            "purpose": item.get("purpose") or item.get("description") or item.get("note") or default_purpose,
            "category": item.get("category") or default_category,
        }
        if item.get("formula_latex"):
            entry["formula_latex"] = item.get("formula_latex")
        formulas.append(_non_empty_domains(entry))

    for item in design_context.get("design_formulas", []):
        if isinstance(item, dict):
            append_formula(item)
    for item in design_context.get("design_equation_hints", []):
        if isinstance(item, dict):
            append_formula(item, default_category="derived_hint")
    for item in design_context.get("design_recommendations", []):
        if isinstance(item, dict) and item.get("equation"):
            append_formula(item, default_category=item.get("topic"), default_purpose=item.get("rule"))
    return formulas


def _format_note_title(topic: str | None) -> str | None:
    if not topic:
        return None
    return topic.replace("_", " ").strip().title()


def _derive_application_notes(design_context: dict) -> list[dict]:
    notes = []
    seen = set()

    def append_note(entry: dict) -> None:
        marker = repr(entry)
        if marker in seen:
            return
        seen.add(marker)
        notes.append(entry)

    for index, item in enumerate(design_context.get("application_notes", []), start=1):
        if not isinstance(item, dict):
            continue
        note = copy.deepcopy(item)
        note.setdefault("id", f"AN-{index:03d}")
        append_note(_non_empty_domains(note))

    next_id = len(notes) + 1
    for item in design_context.get("design_recommendations", []):
        if not isinstance(item, dict):
            continue
        content = item.get("rule") or item.get("note")
        if not content:
            continue
        append_note(
            _non_empty_domains(
                {
                    "id": f"AN-{next_id:03d}",
                    "category": NOTE_TOPIC_CATEGORY_MAP.get(item.get("topic"), "design_guidance"),
                    "title": _format_note_title(item.get("topic")),
                    "content": content,
                    "source": {"page": item.get("source_page"), "section": item.get("source_table")},
                    "severity": "recommendation",
                }
            )
        )
        next_id += 1

    for item in design_context.get("layout_hints", []):
        if not isinstance(item, dict) or not item.get("hint"):
            continue
        append_note(
            {
                "id": f"AN-{next_id:03d}",
                "category": "pcb_layout",
                "title": "Layout Guidance",
                "content": item.get("hint"),
                "source": {"page": item.get("source_page")},
                "severity": "critical" if "minimize" in item.get("hint", "").lower() else "recommendation",
            }
        )
        next_id += 1

    return notes


def _infer_component_type(item: dict) -> str | None:
    if item.get("type"):
        return item.get("type")
    role = item.get("role") or item.get("component")
    return ROLE_COMPONENT_TYPES.get(role)


def _infer_designator(item: dict) -> str | None:
    designator = item.get("designator")
    if designator:
        return designator
    text = " ".join(str(item.get(field) or "") for field in ("snippet", "purpose", "component"))
    match = DESIGNATOR_RE.search(text)
    return match.group(0) if match else None


def _derive_typical_application(design_context: dict, formulas: list[dict]) -> dict:
    existing = copy.deepcopy(design_context.get("typical_application", {}))
    if existing:
        return existing

    pages = [item for item in design_context.get("design_page_candidates", []) if isinstance(item, dict) and item.get("kind") == "application"]
    page = pages[0] if pages else {}
    formula_names = [item.get("name") for item in formulas if isinstance(item, dict)]
    components = []

    for item in design_context.get("recommended_external_components", []):
        if not isinstance(item, dict):
            continue
        role = item.get("role") or item.get("component")
        related_formula = item.get("related_formula")
        if not related_formula and role:
            role_slug = str(role).lower()
            for formula_name in formula_names:
                if formula_name and any(token in str(formula_name).lower() for token in role_slug.split("_")):
                    related_formula = formula_name
                    break
        components.append(
            _non_empty_domains(
                {
                    "designator": _infer_designator(item),
                    "type": _infer_component_type(item),
                    "connection": item.get("connection", []),
                    "typical_value": item.get("typical_value") or item.get("value_hint") or item.get("value"),
                    "purpose": item.get("purpose") or item.get("snippet") or role,
                    "related_formula": related_formula,
                }
            )
        )

    design_example = {}
    for hint in design_context.get("design_range_hints", []):
        if not isinstance(hint, dict):
            continue
        name = str(hint.get("name") or "").upper()
        unit = hint.get("unit")
        minimum = hint.get("min")
        maximum = hint.get("max")
        if name == "VIN" and minimum is not None and maximum is not None:
            design_example["vin_range"] = f"{minimum}{unit} to {maximum}{unit}"
        elif name == "VOUT" and maximum is not None:
            value = maximum if minimum in (None, maximum) else f"{minimum} to {maximum}"
            design_example["vout"] = f"{value}{unit}"
        elif name == "IOUT" and maximum is not None:
            value = maximum if minimum in (None, maximum) else f"{minimum} to {maximum}"
            design_example["i_limit"] = f"{value}{unit}"
        elif name in {"FSW", "FOSC"} and maximum is not None:
            value = maximum if minimum in (None, maximum) else f"{minimum} to {maximum}"
            design_example["switching_frequency"] = f"{value}{unit}"

    return _non_empty_domains(
        {
            "figure": page.get("heading"),
            "page": page.get("page_num"),
            "title": page.get("heading"),
            "components": components,
            "design_example": design_example,
        }
    )


def _annotate_electrical_parameters(elec_params: dict, formulas: list[dict]) -> dict:
    annotated = copy.deepcopy(elec_params or {})
    formula_refs: dict[str, set[str]] = {}
    for formula in formulas:
        if not isinstance(formula, dict):
            continue
        name = formula.get("name")
        for variable in (formula.get("variables") or {}).values():
            if not isinstance(variable, dict):
                continue
            refers_to = variable.get("refers_to")
            if not refers_to or not name:
                continue
            formula_refs.setdefault(_canonical_symbol(refers_to), set()).add(name)

    for key, value in annotated.items():
        if not isinstance(value, dict):
            continue
        refs = formula_refs.get(_canonical_symbol(value.get("symbol") or key), set())
        if refs:
            value["used_in_design"] = True
            value["used_in_formulas"] = sorted(refs)
    return annotated


def _normalize_design_context_domain(design_context: dict, elec_params: dict) -> tuple[dict, list[dict]]:
    if not design_context:
        return {}, []

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

    design_formulas = _derive_design_formulas(design_context, elec_params)
    typical_application = _derive_typical_application(design_context, design_formulas)
    application_notes = _derive_application_notes(design_context)

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
        "design_formulas": design_formulas,
        "typical_application": typical_application,
        "application_notes": application_notes,
    }
    if pages:
        domain["design_pages"] = {
            "pages": pages,
            "total_pages": len(pages),
        }
    return _non_empty_domains(domain), design_formulas


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
    normalized_design_context, design_formulas = _normalize_design_context_domain(design_context, elec_params)
    annotated_elec_params = _annotate_electrical_parameters(elec_params, design_formulas)
    return _non_empty_domains(
        {
            "pin": {"packages": copy.deepcopy(packages)} if packages else {},
            "electrical": {
                "absolute_maximum_ratings": copy.deepcopy(abs_max),
                "electrical_parameters": copy.deepcopy(annotated_elec_params),
                "drc_hints": copy.deepcopy(drc_hints),
            } if (abs_max or annotated_elec_params or drc_hints) else {},
            "thermal": copy.deepcopy(thermal) if thermal else {},
            "design_context": normalized_design_context,
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
    canonical_electrical = copy.deepcopy(domains.get("electrical", {}).get("electrical_parameters", elec_params))

    return NormalIcRecord(
        mpn=mpn,
        manufacturer=manufacturer,
        category=category,
        description=description,
        layers=copy.deepcopy(layers),
        packages=copy.deepcopy(packages),
        absolute_maximum_ratings=copy.deepcopy(abs_max),
        electrical_parameters=canonical_electrical,
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
