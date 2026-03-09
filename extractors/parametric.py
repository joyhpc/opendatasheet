"""Parametric extraction module.

Aggregates key selection parameters from electrical extraction results for
component comparison and selection. This module does NOT call Gemini API;
it post-processes the electrical extraction output (similar to the thermal
extractor).
"""
import re

from extractors.base import BaseExtractor


# ---------------------------------------------------------------------------
# Spec-type classification patterns
# ---------------------------------------------------------------------------
# Each key maps to a list of compiled regex patterns. The patterns are matched
# against the combined string of parameter name + symbol + raw_name.

SPEC_TYPE_PATTERNS = {
    "input_voltage": [
        re.compile(r"(?i)(input|supply|vin)\s*(voltage|range)"),
        re.compile(r"(?i)\bV(IN|CC|DD|S)\b"),
    ],
    "output_voltage": [
        re.compile(r"(?i)(output|vout)\s*voltage"),
        re.compile(r"(?i)\bV(OUT|O)\b"),
    ],
    "output_current": [
        re.compile(r"(?i)(output|load)\s*current"),
        re.compile(r"(?i)\bI(OUT|LOAD|O)\b"),
    ],
    "quiescent_current": [
        re.compile(r"(?i)(quiescent|ground)\s*current"),
        re.compile(r"(?i)\bI(Q|GND)\b"),
    ],
    "switching_frequency": [
        re.compile(r"(?i)(switch|oscillat|clock)\s*freq"),
        re.compile(r"(?i)\bf(SW|OSC|CLK)\b"),
    ],
    "dropout_voltage": [
        re.compile(r"(?i)drop\s*out"),
        re.compile(r"(?i)\bV(DO|DROPOUT)\b"),
    ],
    "accuracy": [
        re.compile(r"(?i)(accuracy|regulation|tolerance)"),
    ],
    "efficiency": [
        re.compile(r"(?i)efficiency"),
    ],
    "bandwidth": [
        re.compile(r"(?i)bandwidth|GBW|unity.gain"),
        re.compile(r"(?i)\b(GBP|BW|UGB)\b"),
    ],
    "slew_rate": [
        re.compile(r"(?i)slew\s*rate"),
        re.compile(r"(?i)\bSR\b"),
    ],
    "input_offset": [
        re.compile(r"(?i)(input|offset)\s*voltage"),
        re.compile(r"(?i)\bV(IO|OS)\b"),
    ],
    "supply_current": [
        re.compile(r"(?i)supply\s*current"),
        re.compile(r"(?i)\bI(CC|DD|SUPPLY)\b"),
    ],
    "leakage_current": [
        re.compile(r"(?i)leakage\s*current"),
    ],
    "on_resistance": [
        re.compile(r"(?i)on.resistance"),
        re.compile(r"(?i)\bR(ON|DS)\b"),
    ],
    "propagation_delay": [
        re.compile(r"(?i)propagation\s*delay"),
        re.compile(r"(?i)\bt(PD|PLH|PHL)\b"),
    ],
    "power_dissipation": [
        re.compile(r"(?i)power\s*dissipation"),
        re.compile(r"(?i)\bP(D|DISS)\b"),
    ],
}

# Allowed spec_type values (must stay in sync with the schema enum)
VALID_SPEC_TYPES = {
    "input_voltage", "output_voltage", "output_current", "quiescent_current",
    "switching_frequency", "dropout_voltage", "accuracy", "efficiency",
    "bandwidth", "slew_rate", "input_offset", "supply_current",
    "leakage_current", "on_resistance", "propagation_delay",
    "power_dissipation", "other",
}

# Patterns for operating-condition extraction from AMR / EC
_TEMP_PATTERNS = [
    re.compile(r"(?i)(operating|storage|ambient|junction)?\s*temp"),
]
_INPUT_VOLTAGE_PATTERNS = [
    re.compile(r"(?i)(input|supply)\s*(voltage|range)"),
    re.compile(r"(?i)\bV(IN|CC|DD|S)\b"),
]
_OUTPUT_VOLTAGE_PATTERNS = [
    re.compile(r"(?i)(output)\s*voltage"),
    re.compile(r"(?i)\bV(OUT|O)\b"),
]
_OUTPUT_CURRENT_PATTERNS = [
    re.compile(r"(?i)(output|load)\s*current"),
    re.compile(r"(?i)\bI(OUT|LOAD|O)\b"),
]


def _classify_spec_type(param: dict) -> str:
    """Classify a parameter dict into a normalized spec_type string."""
    name = (param.get("parameter") or "").strip()
    symbol = (param.get("symbol") or "").strip()
    raw_name = (param.get("raw_name") or "").strip()
    combined = f"{name} {symbol} {raw_name}"

    for spec_type, patterns in SPEC_TYPE_PATTERNS.items():
        for pat in patterns:
            if pat.search(combined):
                return spec_type
    return "other"


def _has_numeric_value(param: dict) -> bool:
    """Return True if the parameter has at least one numeric min/typ/max."""
    return any(
        isinstance(param.get(k), (int, float))
        for k in ("min", "typ", "max")
    )


def _match_any(patterns: list, text: str) -> bool:
    """Return True if any pattern matches *text*."""
    return any(p.search(text) for p in patterns)


def _safe_num(val) -> float | None:
    """Coerce to float or return None."""
    if isinstance(val, (int, float)):
        return float(val)
    return None


class ParametricExtractor(BaseExtractor):
    """Aggregates key selection parameters from electrical extraction data.

    This extractor does NOT make its own Gemini API call. It post-processes
    the electrical extraction result (absolute_maximum_ratings and
    electrical_characteristics arrays) to produce a normalised parametric
    summary suitable for component comparison and selection.

    select_pages() returns an empty list because no separate rendering is
    needed.  extract() expects the already-parsed electrical extraction dict
    (passed via the pipeline orchestrator), not actual images.
    """

    DOMAIN_NAME = "parametric"

    # ------------------------------------------------------------------
    # BaseExtractor interface
    # ------------------------------------------------------------------

    def select_pages(self) -> list[int]:
        """No separate pages needed -- parametric data comes from electrical extraction."""
        return []

    def extract(self, rendered_images) -> dict:
        """Post-process electrical extraction to build parametric data.

        ``rendered_images`` is expected to be the electrical extraction result
        dict (passed via the pipeline orchestrator), not actual images.
        """
        if isinstance(rendered_images, dict) and (
            "absolute_maximum_ratings" in rendered_images
            or "electrical_characteristics" in rendered_images
        ):
            source = rendered_images
        else:
            return {
                "key_specs": [],
                "operating_conditions": {},
                "parametric_summary": {
                    "category": None,
                    "total_key_specs": 0,
                    "has_voltage_specs": False,
                    "has_current_specs": False,
                    "has_frequency_specs": False,
                    "packages_available": [],
                },
            }

        key_specs = self._build_key_specs(source)
        operating_conditions = self._build_operating_conditions(source)
        summary = self._build_summary(source, key_specs)

        return {
            "key_specs": key_specs,
            "operating_conditions": operating_conditions,
            "parametric_summary": summary,
        }

    def validate(self, extraction_result: dict) -> dict:
        """Validate parametric extraction result."""
        issues: list[dict] = []
        key_specs = extraction_result.get("key_specs", [])
        operating_conditions = extraction_result.get("operating_conditions", {})

        # --- Check spec_type values are from the allowed enum ---
        for ks in key_specs:
            st = ks.get("spec_type")
            if st not in VALID_SPEC_TYPES:
                issues.append({
                    "level": "error",
                    "message": (
                        f"Invalid spec_type '{st}' for parameter "
                        f"'{ks.get('name', '?')}'"
                    ),
                })

        # --- Operating-condition sanity ---
        vin_min = operating_conditions.get("vin_min")
        vin_max = operating_conditions.get("vin_max")
        if (
            vin_min is not None
            and vin_max is not None
            and vin_min > vin_max
        ):
            issues.append({
                "level": "warning",
                "message": (
                    f"vin_min ({vin_min}) > vin_max ({vin_max})"
                ),
            })

        vout_min = operating_conditions.get("vout_min")
        vout_max = operating_conditions.get("vout_max")
        if (
            vout_min is not None
            and vout_max is not None
            and vout_min > vout_max
        ):
            issues.append({
                "level": "warning",
                "message": (
                    f"vout_min ({vout_min}) > vout_max ({vout_max})"
                ),
            })

        temp_min = operating_conditions.get("temp_min")
        temp_max = operating_conditions.get("temp_max")
        if temp_min is not None and temp_max is not None:
            if temp_min > temp_max:
                issues.append({
                    "level": "warning",
                    "message": (
                        f"temp_min ({temp_min}) > temp_max ({temp_max})"
                    ),
                })
            if temp_max - temp_min > 500:
                issues.append({
                    "level": "warning",
                    "message": (
                        f"Temperature range ({temp_min} to {temp_max}) "
                        "exceeds 500 degrees -- possibly wrong unit"
                    ),
                })

        # --- Warn if no key specs found ---
        if not key_specs:
            category = extraction_result.get(
                "parametric_summary", {}
            ).get("category")
            issues.append({
                "level": "warning",
                "message": (
                    f"No key specs found for device "
                    f"(category={category or '?'})"
                ),
            })

        return {
            "parametric_validation": issues,
            "parametric_key_spec_count": len(key_specs),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_key_specs(self, source: dict) -> list[dict]:
        """Scan AMR and EC arrays and classify each parameter."""
        key_specs: list[dict] = []
        seen: set[tuple] = set()

        for section in ("absolute_maximum_ratings", "electrical_characteristics"):
            for param in source.get(section, []):
                if not _has_numeric_value(param):
                    continue

                spec_type = _classify_spec_type(param)
                name = (param.get("parameter") or "").strip()
                if not name:
                    continue

                # Deduplicate by (name, spec_type, min, typ, max)
                dedup_key = (
                    name.lower(),
                    spec_type,
                    param.get("min"),
                    param.get("typ"),
                    param.get("max"),
                )
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                entry: dict = {
                    "name": name,
                    "spec_type": spec_type,
                    "min": _safe_num(param.get("min")),
                    "typ": _safe_num(param.get("typ")),
                    "max": _safe_num(param.get("max")),
                    "unit": param.get("unit") or None,
                    "conditions": param.get("conditions") or None,
                    "source_parameter": param.get("raw_name") or name,
                }
                key_specs.append(entry)

        return key_specs

    def _build_operating_conditions(self, source: dict) -> dict:
        """Extract operating-condition ranges from AMR and EC data."""
        oc: dict = {
            "vin_min": None,
            "vin_max": None,
            "vout_min": None,
            "vout_max": None,
            "iout_max": None,
            "temp_min": None,
            "temp_max": None,
            "temp_unit": "C",
        }

        all_params: list[dict] = []
        for section in ("absolute_maximum_ratings", "electrical_characteristics"):
            all_params.extend(source.get(section, []))

        for param in all_params:
            name = (param.get("parameter") or "").strip()
            symbol = (param.get("symbol") or "").strip()
            raw_name = (param.get("raw_name") or "").strip()
            combined = f"{name} {symbol} {raw_name}"

            # --- Input voltage ---
            if _match_any(_INPUT_VOLTAGE_PATTERNS, combined):
                v_min = _safe_num(param.get("min"))
                v_max = _safe_num(param.get("max"))
                if v_min is not None and (oc["vin_min"] is None or v_min < oc["vin_min"]):
                    oc["vin_min"] = v_min
                if v_max is not None and (oc["vin_max"] is None or v_max > oc["vin_max"]):
                    oc["vin_max"] = v_max

            # --- Output voltage ---
            if _match_any(_OUTPUT_VOLTAGE_PATTERNS, combined):
                v_min = _safe_num(param.get("min"))
                v_max = _safe_num(param.get("max"))
                if v_min is not None and (oc["vout_min"] is None or v_min < oc["vout_min"]):
                    oc["vout_min"] = v_min
                if v_max is not None and (oc["vout_max"] is None or v_max > oc["vout_max"]):
                    oc["vout_max"] = v_max

            # --- Output current ---
            if _match_any(_OUTPUT_CURRENT_PATTERNS, combined):
                i_max = _safe_num(param.get("max"))
                if i_max is not None and (oc["iout_max"] is None or i_max > oc["iout_max"]):
                    oc["iout_max"] = i_max

            # --- Temperature ---
            if _match_any(_TEMP_PATTERNS, combined):
                unit = (param.get("unit") or "").strip()
                # Only consider celsius-ish units
                if unit and "F" in unit.upper() and "C" not in unit.upper():
                    continue
                t_min = _safe_num(param.get("min"))
                t_max = _safe_num(param.get("max"))
                if t_min is not None and (oc["temp_min"] is None or t_min < oc["temp_min"]):
                    oc["temp_min"] = t_min
                if t_max is not None and (oc["temp_max"] is None or t_max > oc["temp_max"]):
                    oc["temp_max"] = t_max

        return oc

    def _build_summary(self, source: dict, key_specs: list[dict]) -> dict:
        """Build a parametric summary dict."""
        spec_types_present = {ks["spec_type"] for ks in key_specs}

        voltage_types = {
            "input_voltage", "output_voltage", "dropout_voltage",
        }
        current_types = {
            "output_current", "quiescent_current", "supply_current",
            "leakage_current",
        }
        frequency_types = {
            "switching_frequency", "bandwidth",
        }

        # Packages: extract unique pin names from pin_definitions if available
        packages: list[str] = []
        pin_defs = source.get("pin_definitions", [])
        if pin_defs and isinstance(pin_defs, list):
            # Try to find package info from pin_definitions; typically the
            # pin list itself does not carry package names, so we just note
            # that pin data exists.
            pass

        category = source.get("component", {}).get("category") or None

        return {
            "category": category,
            "total_key_specs": len(key_specs),
            "has_voltage_specs": bool(spec_types_present & voltage_types),
            "has_current_specs": bool(spec_types_present & current_types),
            "has_frequency_specs": bool(spec_types_present & frequency_types),
            "packages_available": packages,
        }
