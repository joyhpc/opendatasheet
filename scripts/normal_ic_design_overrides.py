from __future__ import annotations

import copy
import json


TPS56C215_DATASHEET = {
    "title": "TPS56C215 3.8V to 17V Input, 12A, Synchronous, Step-Down SWIFT Converter datasheet",
    "revision": "Rev. H",
    "document_id": "SLVSD05H",
    "url": "https://www.ti.com/lit/ds/symlink/tps56c215.pdf",
}


def _tps56c215_override() -> dict:
    source = {
        "document_id": TPS56C215_DATASHEET["document_id"],
        "revision": TPS56C215_DATASHEET["revision"],
        "url": TPS56C215_DATASHEET["url"],
    }

    mode_rows = [
        (5.1, 300, "FCCM", "ILIM-1", 400, 10, {"min": 9.775, "typ": 11.5, "max": 13.225, "unit": "A"}),
        (10, 200, "FCCM", "ILIM", 400, 12, {"min": 11.73, "typ": 13.8, "max": 15.87, "unit": "A"}),
        (20, 160, "FCCM", "ILIM-1", 800, 10, {"min": 9.775, "typ": 11.5, "max": 13.225, "unit": "A"}),
        (20, 120, "FCCM", "ILIM", 800, 12, {"min": 11.73, "typ": 13.8, "max": 15.87, "unit": "A"}),
        (51, 200, "FCCM", "ILIM-1", 1200, 10, {"min": 9.775, "typ": 11.5, "max": 13.225, "unit": "A"}),
        (51, 180, "FCCM", "ILIM", 1200, 12, {"min": 11.73, "typ": 13.8, "max": 15.87, "unit": "A"}),
        (51, 150, "DCM", "ILIM-1", 400, 10, {"min": 9.775, "typ": 11.5, "max": 13.225, "unit": "A"}),
        (51, 120, "DCM", "ILIM", 400, 12, {"min": 11.73, "typ": 13.8, "max": 15.87, "unit": "A"}),
        (51, 91, "DCM", "ILIM-1", 800, 10, {"min": 9.775, "typ": 11.5, "max": 13.225, "unit": "A"}),
        (51, 82, "DCM", "ILIM", 800, 12, {"min": 11.73, "typ": 13.8, "max": 15.87, "unit": "A"}),
        (51, 62, "DCM", "ILIM-1", 1200, 10, {"min": 9.775, "typ": 11.5, "max": 13.225, "unit": "A"}),
        (51, 51, "DCM", "ILIM", 1200, 12, {"min": 11.73, "typ": 13.8, "max": 15.87, "unit": "A"}),
    ]
    configuration_mappings = []
    for bottom_kohm, top_kohm, load_mode, current_limit, fsw_khz, supported_iout_a, valley_limit in mode_rows:
        configuration_mappings.append(
            {
                "pin": "MODE",
                "source_page": 17,
                "source_table": "Table 6-3",
                "resistor_divider": {
                    "top_resistor_kohm": top_kohm,
                    "bottom_resistor_kohm": bottom_kohm,
                    "reference_rail": "VREG5",
                    "reference_ground": "AGND",
                    "tolerance": "1%",
                },
                "behavior": {
                    "light_load_operation": load_mode,
                    "current_limit_option": current_limit,
                    "switching_frequency_khz": fsw_khz,
                    "supported_output_current_a": supported_iout_a,
                    "low_side_valley_current_limit": valley_limit,
                },
                "source": copy.deepcopy(source),
            }
        )

    component_matrix = [
        {"vout_v": 0.6, "r_lower_kohm": 10, "r_upper_kohm": 0, "fsw_khz": 400, "lout_uh": 0.68, "cout_min_uf": 300, "cout_max_uf": 500, "cff_pf": None},
        {"vout_v": 0.6, "r_lower_kohm": 10, "r_upper_kohm": 0, "fsw_khz": 800, "lout_uh": 0.47, "cout_min_uf": 100, "cout_max_uf": 500, "cff_pf": None},
        {"vout_v": 0.6, "r_lower_kohm": 10, "r_upper_kohm": 0, "fsw_khz": 1200, "lout_uh": 0.33, "cout_min_uf": 88, "cout_max_uf": 500, "cff_pf": None},
        {"vout_v": 1.2, "r_lower_kohm": 10, "r_upper_kohm": 10, "fsw_khz": 400, "lout_uh": 1.2, "cout_min_uf": 100, "cout_max_uf": 500, "cff_pf": None},
        {"vout_v": 1.2, "r_lower_kohm": 10, "r_upper_kohm": 10, "fsw_khz": 800, "lout_uh": 0.68, "cout_min_uf": 88, "cout_max_uf": 500, "cff_pf": None},
        {"vout_v": 1.2, "r_lower_kohm": 10, "r_upper_kohm": 10, "fsw_khz": 1200, "lout_uh": 0.47, "cout_min_uf": 88, "cout_max_uf": 500, "cff_pf": None},
        {"vout_v": 3.3, "r_lower_kohm": 10, "r_upper_kohm": 45.3, "fsw_khz": 400, "lout_uh": 2.4, "cout_min_uf": 88, "cout_max_uf": 500, "cff_pf": "100-220"},
        {"vout_v": 3.3, "r_lower_kohm": 10, "r_upper_kohm": 45.3, "fsw_khz": 800, "lout_uh": 1.5, "cout_min_uf": 88, "cout_max_uf": 500, "cff_pf": "100-220"},
        {"vout_v": 3.3, "r_lower_kohm": 10, "r_upper_kohm": 45.3, "fsw_khz": 1200, "lout_uh": 1.2, "cout_min_uf": 88, "cout_max_uf": 500, "cff_pf": "100-220"},
        {"vout_v": 5.5, "r_lower_kohm": 10, "r_upper_kohm": 82.5, "fsw_khz": 400, "lout_uh": 3.3, "cout_min_uf": 88, "cout_max_uf": 500, "cff_pf": "100-220"},
        {"vout_v": 5.5, "r_lower_kohm": 10, "r_upper_kohm": 82.5, "fsw_khz": 800, "lout_uh": 2.4, "cout_min_uf": 88, "cout_max_uf": 500, "cff_pf": "100-220"},
        {"vout_v": 5.5, "r_lower_kohm": 10, "r_upper_kohm": 82.5, "fsw_khz": 1200, "lout_uh": 1.5, "cout_min_uf": 88, "cout_max_uf": 700, "cff_pf": "100-220"},
    ]

    return {
        "design_page_candidates": [
            {"page_num": 17, "heading": "MODE Pin Resistor Settings", "kind": "application"},
            {"page_num": 21, "heading": "Typical Application", "kind": "application"},
            {"page_num": 22, "heading": "External Component Selection", "kind": "application"},
            {"page_num": 23, "heading": "Recommended Component Values", "kind": "application"},
        ],
        "component_value_hints": [
            {
                "values": ["470 nH", "4x47 uF", "4x22 uF", "4.7 uF", "56 pF", "51 kOhm / 51 kOhm"],
                "source_page": 21,
                "snippet": "Typical 1.2-V, 12-A application schematic shows the reference inductor, capacitor bank, VREG5 bypass, and MODE divider values.",
            }
        ],
        "design_range_hints": [
            {
                "name": "VIN",
                "min": 4.5,
                "max": 17.0,
                "unit": "V",
                "source_page": 21,
                "snippet": "Typical application input range",
            },
            {
                "name": "VOUT",
                "min": 1.2,
                "max": 1.2,
                "unit": "V",
                "source_page": 21,
                "snippet": "Typical application output set point",
            },
            {
                "name": "IOUT",
                "min": 12.0,
                "max": 12.0,
                "unit": "A",
                "source_page": 21,
                "snippet": "Typical application output current target",
            },
            {
                "name": "FSW",
                "min": 1200.0,
                "max": 1200.0,
                "unit": "kHz",
                "source_page": 21,
                "snippet": "Typical application switching frequency",
            },
        ],
        "recommended_external_components": [
            {
                "role": "feedback_divider",
                "snippet": "For adjustable output voltage, keep the lower leg from Table 7-2 and change only the upper feedback resistor using Equation 6.",
                "source_page": 22,
            },
            {
                "role": "inductor",
                "snippet": "Use Table 7-2 inductor values instead of a generic ripple-current heuristic when selecting operating points for TPS56C215.",
                "source_page": 22,
            },
            {
                "role": "output_capacitor",
                "snippet": "Use the Table 7-2 output-capacitance window for D-CAP3 stability and transient performance.",
                "source_page": 22,
            },
        ],
        "configuration_mappings": configuration_mappings,
        "design_recommendations": [
            {
                "topic": "mode_pin_configuration",
                "pin": "MODE",
                "source_page": 17,
                "source_table": "Table 6-3",
                "rule": "MODE must be derived from the VREG5 rail through a resistor divider to AGND, is sampled during startup, and only resets after VIN power cycling.",
                "source": copy.deepcopy(source),
            },
            {
                "topic": "recommended_component_values",
                "source_page": 23,
                "source_table": "Table 7-2",
                "entries": component_matrix,
                "source": copy.deepcopy(source),
            },
            {
                "topic": "feedback_divider_bias",
                "source_page": 22,
                "source_table": "Table 7-2",
                "equation": "RUPPER = RLOWER * (VOUT / 0.6 - 1)",
                "adjust_only": "RUPPER",
                "recommended_r_lower_kohm": 10,
                "note": "Latest TI datasheet examples in Rev. H use a 10-kOhm lower feedback resistor across the Table 7-2 operating points.",
                "source": copy.deepcopy(source),
            },
        ],
    }


NORMAL_IC_DESIGN_CONTEXT_OVERRIDES = {
    "TPS56C215": _tps56c215_override(),
}


LIST_MERGE_KEYS = {
    "design_page_candidates",
    "recommended_external_components",
    "component_value_hints",
    "design_range_hints",
    "design_equation_hints",
    "layout_hints",
    "supply_recommendations",
    "topology_hints",
    "configuration_mappings",
    "design_recommendations",
}


def _dedupe_list(items: list) -> list:
    seen = set()
    result = []
    for item in items:
        marker = json.dumps(item, sort_keys=True, ensure_ascii=True) if isinstance(item, (dict, list)) else repr(item)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def merge_design_context(base: dict | None, overlay: dict | None) -> dict:
    merged = copy.deepcopy(base or {})
    for key, value in (overlay or {}).items():
        if key in LIST_MERGE_KEYS:
            existing = merged.get(key, [])
            if not isinstance(existing, list):
                existing = []
            incoming = value if isinstance(value, list) else [value]
            merged[key] = _dedupe_list(existing + copy.deepcopy(incoming))
            continue
        merged[key] = copy.deepcopy(value)
    return merged


def get_normal_ic_design_context_override(mpn: str | None) -> dict:
    if not mpn:
        return {}
    return copy.deepcopy(NORMAL_IC_DESIGN_CONTEXT_OVERRIDES.get(mpn, {}))
