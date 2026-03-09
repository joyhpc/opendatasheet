"""Thermal parameter extraction module.

Thermal parameters (theta_ja, theta_jc, power dissipation, etc.) are currently
extracted as part of the electrical extraction (they appear in the same datasheet
tables). This module post-processes the electrical extraction results to isolate
the thermal parameter subset.
"""
import re

from extractors.base import BaseExtractor


# Patterns to identify thermal parameters
THERMAL_PARAMETER_PATTERNS = [
    re.compile(r'(?i)thermal\s+resistance'),
    re.compile(r'(?i)theta\s*j[ac]'),
    re.compile(r'(?i)\u03b8\s*j[ac]'),           # theta symbol
    re.compile(r'(?i)junction[\s\-]+to[\s\-]+(ambient|case|board)'),
    re.compile(r'(?i)power\s+dissipation'),
    re.compile(r'(?i)junction\s+temperature'),
    re.compile(r'(?i)thermal\s+(shutdown|data|characteristics?|information)'),
    re.compile(r'(?i)R\u03b8J[AC]'),               # R-theta-JA / R-theta-JC
    re.compile(r'(?i)thermal\s+impedance'),
    re.compile(r'(?i)\u03c8\s*j[actb]'),           # psi symbol variants
]

THERMAL_SYMBOL_KEYWORDS = {
    'theta_ja', 'theta_jc', 'theta_jb',
    'rthja', 'rthjc', 'rthjb',
    'psi_jt', 'psi_jb',
}


def _is_thermal_parameter(param: dict) -> bool:
    """Check if a parameter dict describes a thermal quantity."""
    name = (param.get("parameter") or "").lower()
    symbol = (param.get("symbol") or "").lower()
    raw_name = (param.get("raw_name") or "").lower()

    combined = f"{name} {symbol} {raw_name}"

    # Check against regex patterns
    for pattern in THERMAL_PARAMETER_PATTERNS:
        if pattern.search(combined):
            return True

    # Check against symbol keywords
    for kw in THERMAL_SYMBOL_KEYWORDS:
        if kw in symbol.replace(" ", "").replace("-", "").replace("_", ""):
            return True

    # Check unit: thermal resistance is typically \u00b0C/W
    unit = (param.get("unit") or "").lower()
    if "\u00b0c/w" in unit or "c/w" in unit:
        return True

    return False


class ThermalExtractor(BaseExtractor):
    """Isolates thermal parameters from the electrical extraction result.

    Thermal data lives in the same datasheet tables as electrical parameters
    (absolute_maximum_ratings, electrical_characteristics). This extractor
    does NOT make its own Gemini API call; instead, it post-processes the
    electrical extraction output to separate the thermal subset.

    select_pages() returns an empty list because no separate rendering is needed.
    extract() expects the already-parsed electrical extraction dict and filters it.
    validate() applies thermal-specific sanity checks.
    """

    DOMAIN_NAME = "thermal"

    def select_pages(self) -> list[int]:
        """No separate pages needed -- thermal data is extracted by ElectricalExtractor."""
        return []

    def extract(self, rendered_images) -> dict:
        """Post-process electrical extraction to isolate thermal parameters.

        `rendered_images` is expected to be the electrical extraction result dict
        (passed via the pipeline orchestrator), not actual images.
        """
        if isinstance(rendered_images, dict) and ("absolute_maximum_ratings" in rendered_images or "electrical_characteristics" in rendered_images):
            source = rendered_images
        else:
            # No electrical data available
            return {"thermal_parameters": []}

        thermal_params = []
        for section in ["absolute_maximum_ratings", "electrical_characteristics"]:
            for param in source.get(section, []):
                if _is_thermal_parameter(param):
                    entry = dict(param)
                    entry["source_section"] = section
                    thermal_params.append(entry)

        return {"thermal_parameters": thermal_params}

    def validate(self, extraction_result: dict) -> dict:
        """Validate thermal parameter sanity."""
        issues = []
        params = extraction_result.get("thermal_parameters", [])

        for p in params:
            name = p.get("parameter", "")
            unit = (p.get("unit") or "").lower()
            max_v = p.get("max")

            # Thermal resistance should typically be positive
            min_v = p.get("min")
            if min_v is not None and min_v < 0 and ("\u00b0c/w" in unit or "c/w" in unit):
                issues.append({
                    "level": "warning",
                    "message": f"Thermal resistance '{name}' has negative min={min_v} {unit}"
                })

            # Junction temperature max should be reasonable (< 200\u00b0C)
            if "junction" in name.lower() and "temperature" in name.lower():
                if max_v is not None and max_v > 200:
                    issues.append({
                        "level": "warning",
                        "message": f"Junction temperature '{name}' max={max_v}\u00b0C seems unusually high"
                    })

        return {"thermal_validation": issues, "thermal_count": len(params)}
