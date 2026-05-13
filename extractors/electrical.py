"""Electrical parameter extraction module.

Handles L1a vision extraction (component info, absolute_maximum_ratings,
electrical_characteristics) and L2/L5 physics validation.
"""
import math
import re

from extractors.base import BaseExtractor
from extractors.gemini_json import call_gemini_json_response


# ============================================
# Prompts
# ============================================

PROMPT_ID = "opendatasheet.electrical.vision"
PROMPT_VERSION = "1.0.0"

VISION_PROMPT = """You are an expert electronic component datasheet parser. These images show pages from an electronic component datasheet.

CRITICAL RULES:
1. Extract ALL electrical parameters with min/typ/max values and units
2. Many datasheets have DUAL-ROW format: each parameter has TWO rows of min/typ/max
   - One row for 25\u00b0C specs, another for full temperature range
   - You MUST extract BOTH rows as separate entries
3. If the datasheet covers MULTIPLE VARIANTS (e.g., different output voltages),
   extract parameters for ALL variants separately
4. Include test conditions for each parameter
5. If a value is not specified, use null
6. Extract pin definitions if visible
7. Output ONLY valid JSON, no markdown, no code fences

OUTPUT JSON SCHEMA:
{
  "component": {
    "mpn": "string (main part number)",
    "manufacturer": "string",
    "category": "string (LDO/Buck/OpAmp/Switch/Logic/ADC/DAC/Interface/FPGA/CPLD/SoC/Other)",
    "description": "string (one line)"
  },
  "absolute_maximum_ratings": [
    {"parameter": "string", "raw_name": "string", "symbol": "string", "min": null or number, "typ": null or number, "max": null or number, "unit": "string", "conditions": "string or null"}
  ],
  "electrical_characteristics": [
    {"parameter": "string", "raw_name": "string", "symbol": "string", "min": null or number, "typ": null or number, "max": null or number, "unit": "string", "conditions": "string or null", "device": "string (variant if applicable)", "temp_range": "25C or full or null"}
  ],
  "pin_definitions": [
    {"pin_number": "string or number", "pin_name": "string", "type": "string", "description": "string"}
  ]
}"""


# ============================================
# Physics validation helpers (Q1)
# ============================================

def get_supported_modes(min_val, typ_val, max_val):
    """Infer supported layout modes: ALGEBRAIC or MAGNITUDE."""
    vals = [v for v in [min_val, typ_val, max_val] if v is not None]
    if len(vals) <= 1:
        modes = ['ALGEBRAIC']
        if not vals or vals[0] <= 0:
            modes.append('MAGNITUDE')
        return modes
    modes = []
    if all(vals[i] <= vals[i+1] for i in range(len(vals)-1)):
        modes.append('ALGEBRAIC')
    if all(vals[i] >= vals[i+1] for i in range(len(vals)-1)) and all(v <= 0 for v in vals):
        modes.append('MAGNITUDE')
    return modes


def get_physical_interval(min_val, max_val, mode):
    """Map literal min/max to physical number-line interval [L, U]."""
    if mode == 'ALGEBRAIC':
        L = min_val if min_val is not None else -math.inf
        U = max_val if max_val is not None else math.inf
        return L, U
    elif mode == 'MAGNITUDE':
        L = max_val if max_val is not None else -math.inf
        U = min_val if min_val is not None else 0.0
        return L, U


# ============================================
# Gemini API call helper
# ============================================

def _call_gemini_vision(
    client,
    model,
    images,
    prompt,
    max_retries=2,
    prompt_id=PROMPT_ID,
    prompt_version=PROMPT_VERSION,
):
    """Call Gemini Vision API and parse the result into canonical JSON."""
    return call_gemini_json_response(
        client,
        model,
        images,
        prompt,
        max_retries=max_retries,
        prompt_id=prompt_id,
        prompt_version=prompt_version,
    )


class ElectricalExtractor(BaseExtractor):
    """Extracts electrical parameters: component info, absolute maximum ratings,
    electrical characteristics. Also runs L2 monotonicity/unit validation and
    L5 physics rule validation (temperature envelope, LDO Iq range)."""

    DOMAIN_NAME = "electrical"

    def select_pages(self) -> list[int]:
        """Select electrical + cover pages for vision extraction."""
        electrical_pages = [p.page_num for p in self.page_classification if p.category == "electrical"]
        cover_pages = [p.page_num for p in self.page_classification if p.category == "cover"]
        return sorted(set(electrical_pages + cover_pages))

    def extract(self, rendered_images) -> dict:
        """L1a: Use Gemini Vision to extract electrical parameters from page images."""
        if isinstance(rendered_images, dict):
            images = list(rendered_images.values())
        else:
            images = rendered_images

        if not images:
            return {"error": "No images to extract from"}

        return _call_gemini_vision(self.client, self.model, images, VISION_PROMPT)

    def validate(self, extraction_result: dict) -> dict:
        """Run L2 monotonicity/unit validation and L5 physics validation."""
        if "error" in extraction_result:
            return {"l2_validation": [], "l5_physics": []}

        l2 = self._validate_extraction(extraction_result)
        l5 = self._validate_physics(extraction_result)
        return {
            "l2_validation": l2,
            "l5_physics": l5,
        }

    # ----------------------------------------------------------
    # L2: Monotonicity / unit validation
    # ----------------------------------------------------------

    def _validate_extraction(self, data: dict) -> list[dict]:
        """L2 validation: monotonicity and unit format checks."""
        results = []
        for section in ["absolute_maximum_ratings", "electrical_characteristics"]:
            params = data.get(section, [])
            for p in params:
                name = p.get("parameter", "")
                min_v = p.get("min")
                typ_v = p.get("typ")
                max_v = p.get("max")
                vals = [v for v in [min_v, typ_v, max_v] if v is not None]
                if len(vals) >= 2:
                    modes = get_supported_modes(min_v, typ_v, max_v)
                    if modes:
                        results.append({
                            "param": name, "rule": "monotonicity", "passed": True,
                            "message": f"OK (modes: {','.join(modes)})"
                        })
                    else:
                        results.append({
                            "param": name, "rule": "monotonicity", "passed": False,
                            "message": f"min/typ/max not monotonic: {min_v}/{typ_v}/{max_v}"
                        })
                unit = p.get("unit", "")
                if unit and not re.match(r'^[\u00b5\u03bcunmpkMGT]?[AVW\u03a9HzFsS\u00b0C%dB/()RMS]+$', unit):
                    results.append({
                        "param": name, "rule": "unit_valid", "passed": False,
                        "message": f"Suspicious unit: {unit}"
                    })
        return results

    # ----------------------------------------------------------
    # L5: Physics rule engine
    # ----------------------------------------------------------

    def _validate_physics(self, data: dict) -> list[dict]:
        """L5: Domain-knowledge-driven physics rule validation."""
        results = []
        ec = data.get("electrical_characteristics", [])

        # --- Rule 1: Temperature envelope law ---
        param_groups = {}
        for p in ec:
            param_name = p.get("parameter", "")
            device = p.get("device") or str(p.get("applies_to", ""))
            temp = p.get("temp_range", "")
            if not temp or not param_name:
                continue
            key = (param_name, device)
            if key not in param_groups:
                param_groups[key] = {}
            param_groups[key][temp] = {
                "min": p.get("min"),
                "typ": p.get("typ"),
                "max": p.get("max"),
            }

        for (param_name, device), temps in param_groups.items():
            if "25C" in temps and "full" in temps:
                t25 = temps["25C"]
                tfull = temps["full"]

                modes_25 = get_supported_modes(t25["min"], t25["typ"], t25["max"])
                modes_full = get_supported_modes(tfull["min"], tfull["typ"], tfull["max"])
                common_modes = set(modes_25) & set(modes_full)

                if not common_modes:
                    results.append({
                        "param": f"{param_name} ({device})",
                        "rule": "temp_envelope",
                        "passed": False,
                        "message": f"25C and full temp data have conflicting conventions (modes_25={modes_25}, modes_full={modes_full})"
                    })
                    continue

                eps = 1e-9
                envelope_ok = False
                winning_mode = None
                for mode in common_modes:
                    L_25, U_25 = get_physical_interval(t25["min"], t25["max"], mode)
                    L_ft, U_ft = get_physical_interval(tfull["min"], tfull["max"], mode)

                    lower_ok = True
                    upper_ok = True
                    if math.isfinite(L_25) and math.isfinite(L_ft):
                        lower_ok = L_ft <= L_25 + eps
                    if math.isfinite(U_25) and math.isfinite(U_ft):
                        upper_ok = U_ft >= U_25 - eps

                    if lower_ok and upper_ok:
                        envelope_ok = True
                        winning_mode = mode
                        break

                if envelope_ok:
                    results.append({
                        "param": f"{param_name} ({device})",
                        "rule": "temp_envelope",
                        "passed": True,
                        "message": f"OK (mode: {winning_mode})"
                    })
                else:
                    results.append({
                        "param": f"{param_name} ({device})",
                        "rule": "temp_envelope",
                        "passed": False,
                        "message": "full temp physical interval does not contain 25C interval"
                    })

        # --- Rule 2: LDO-specific constraints ---
        category = data.get("component", {}).get("category", "").upper()
        if category == "LDO":
            for p in ec:
                name = p.get("parameter", "").lower()
                if "quiescent" in name or name in ("iq",):
                    unit = p.get("unit", "").lower()
                    typ_v = p.get("typ")
                    if typ_v is not None:
                        if "ua" in unit or "\u00b5a" in unit or "\u03bca" in unit:
                            typ_ma = typ_v / 1000
                        elif "ma" in unit:
                            typ_ma = typ_v
                        elif "a" in unit and "m" not in unit and "\u00b5" not in unit:
                            typ_ma = typ_v * 1000
                        else:
                            typ_ma = typ_v
                        if typ_ma > 50:
                            results.append({
                                "param": p.get("parameter", "Iq"),
                                "rule": "ldo_iq_range",
                                "passed": False,
                                "message": f"Iq typ={typ_v}{unit} ({typ_ma:.1f}mA) seems too high for LDO"
                            })

        return results
