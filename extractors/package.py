"""Package and mechanical extraction module.

Handles extraction of package/mechanical data from datasheets including
physical dimensions, pin counts, pad geometry, land patterns, thermal
properties, moisture sensitivity levels, marking, and ordering information.
"""
import json
import re
import time

from google.genai import types

from extractors.base import BaseExtractor


# ============================================
# Prompts
# ============================================

PACKAGE_EXTRACTION_PROMPT = """You are an expert electronic component datasheet parser specializing in package and mechanical specifications.
Analyze the provided datasheet page images and extract ALL package/mechanical data into a structured JSON format.

CRITICAL RULES:
1. Extract every package variant/option shown in the datasheet
2. For dimensions, always capture min/nom/max where available
3. All dimension values should be in millimeters (mm) unless explicitly stated otherwise
4. If a value is not specified or not visible, use null
5. Output ONLY valid JSON, no markdown, no code fences

PACKAGE FIELDS TO EXTRACT:
For each package variant found, extract:
- package_name: Full package designation (e.g., "VQFN-48", "SOIC-8", "BGA-256")
- package_type: Package family type (e.g., "QFN", "BGA", "SOIC", "SOT-23", "TSSOP", "DFN", "WLCSP", "TO-220", "DPAK", "SOP", "LQFP", "HTSSOP")
- pin_count: Total number of pins/balls/pads (integer)
- pitch_mm: Pin/ball pitch in millimeters (number or null)
- body_length_mm: Package body length with min/nom/max: {"min": N, "nom": N, "max": N}
- body_width_mm: Package body width with min/nom/max: {"min": N, "nom": N, "max": N}
- body_height_mm: Package body height/standoff with min/nom/max: {"min": N, "nom": N, "max": N}
- lead_span_mm: Overall dimension including leads with min/nom/max: {"min": N, "nom": N, "max": N}
- terminal_width_mm: Lead/terminal width with min/nom/max, or null if not specified
- terminal_length_mm: Lead/terminal length (foot length) with min/nom/max, or null if not specified
- exposed_pad: Whether package has an exposed/thermal pad. Object or null:
  {"present": true/false, "length_mm": N, "width_mm": N, "description": "..."}
- land_pattern: Recommended PCB land pattern/footprint. Object or null:
  {"pad_length_mm": N, "pad_width_mm": N, "pad_pitch_mm": N, "paste_mask_pct": N, "notes": "..."}
- thermal_properties: Thermal performance data. Object or null:
  {"theta_ja_c_per_w": N, "theta_jc_c_per_w": N, "theta_jb_c_per_w": N, "psi_jt_c_per_w": N, "psi_jb_c_per_w": N, "power_dissipation_w": N, "notes": "..."}
- moisture_sensitivity: MSL rating and related info. Object or null:
  {"msl_level": "MSL 3", "peak_reflow_temp_c": N, "floor_life_hours": N}
- reflow_profile: Reflow soldering profile parameters. Object or null:
  {"peak_temp_c": N, "time_above_liquidus_s": N, "ramp_rate_c_per_s": N, "preheat_temp_min_c": N, "preheat_temp_max_c": N, "classification": "Pb-free" or "SnPb"}
- weight_mg: Package weight in milligrams, or null
- marking: Device marking/top marking information. Object or null:
  {"marking_code": "...", "marking_description": "...", "marking_diagram": true/false}
- ordering_info: Ordering information. List or null:
  [{"part_number": "...", "package_type": "...", "temperature_range": "...", "packing": "...", "quantity_per_reel": N}]

SUMMARY FIELDS:
- total_packages: Integer count of all package variants extracted
- package_types: List of unique package types found (e.g., ["QFN", "BGA"])
- has_exposed_pad: Boolean, true if any package has an exposed/thermal pad
- has_land_pattern: Boolean, true if land pattern data was found
- has_thermal_data: Boolean, true if thermal resistance data was found
- has_ordering_info: Boolean, true if ordering information was found

OUTPUT JSON SCHEMA:
{
  "packages": [
    {
      "package_name": "VQFN-48",
      "package_type": "QFN",
      "pin_count": 48,
      "pitch_mm": 0.5,
      "body_length_mm": {"min": 6.9, "nom": 7.0, "max": 7.1},
      "body_width_mm": {"min": 6.9, "nom": 7.0, "max": 7.1},
      "body_height_mm": {"min": 0.8, "nom": 0.85, "max": 0.9},
      "lead_span_mm": null,
      "terminal_width_mm": {"min": 0.18, "nom": 0.25, "max": 0.30},
      "terminal_length_mm": {"min": 0.30, "nom": 0.40, "max": 0.50},
      "exposed_pad": {"present": true, "length_mm": 5.6, "width_mm": 5.6, "description": "Thermal pad"},
      "land_pattern": {"pad_length_mm": 0.85, "pad_width_mm": 0.30, "pad_pitch_mm": 0.5, "paste_mask_pct": 80, "notes": null},
      "thermal_properties": {"theta_ja_c_per_w": 28.5, "theta_jc_c_per_w": 4.3, "theta_jb_c_per_w": null, "psi_jt_c_per_w": 0.3, "psi_jb_c_per_w": 13.5, "power_dissipation_w": 3.5, "notes": null},
      "moisture_sensitivity": {"msl_level": "MSL 3", "peak_reflow_temp_c": 260, "floor_life_hours": 168},
      "reflow_profile": {"peak_temp_c": 260, "time_above_liquidus_s": 60, "ramp_rate_c_per_s": 3.0, "preheat_temp_min_c": 150, "preheat_temp_max_c": 200, "classification": "Pb-free"},
      "weight_mg": 120,
      "marking": {"marking_code": "ABC123", "marking_description": "Top marking", "marking_diagram": true},
      "ordering_info": [{"part_number": "DEV1234RHAR", "package_type": "VQFN-48", "temperature_range": "-40 to 125", "packing": "Tape and Reel", "quantity_per_reel": 2500}]
    }
  ],
  "package_summary": {
    "total_packages": 1,
    "package_types": ["QFN"],
    "has_exposed_pad": true,
    "has_land_pattern": true,
    "has_thermal_data": true,
    "has_ordering_info": true
  }
}

IMPORTANT:
- Extract ALL package variants visible in the images
- Capture all dimension tolerances (min/nom/max) where they are specified
- If only a single dimension value is given, put it in "nom" and set min/max to null
- Include ALL ordering information variants with their part numbers
- Preserve exact part numbers and marking codes from the datasheet (do not rename)
- Convert inches to mm if dimensions are in inches (1 inch = 25.4 mm)
- For BGA packages, extract ball diameter and ball pitch separately
- For QFN/DFN packages, always look for exposed/thermal pad dimensions
"""


# ============================================
# Page selection patterns
# ============================================

# Patterns used to identify pages that contain package/mechanical content
PACKAGE_PAGE_PATTERNS = [
    # Package section headers
    re.compile(r'(?i)\bpackage\b'),
    re.compile(r'(?i)\bmechanical\b'),
    re.compile(r'(?i)\bphysical\s+dimensions?\b'),
    re.compile(r'(?i)\boutline\s+drawing\b'),
    re.compile(r'(?i)\bpackage\s+outline\b'),
    re.compile(r'(?i)\bmechanical\s+drawing\b'),
    re.compile(r'(?i)\bpackage\s+drawing\b'),
    # Package types
    re.compile(r'(?i)\bQFN\b'),
    re.compile(r'(?i)\bBGA\b'),
    re.compile(r'(?i)\bSOIC\b'),
    re.compile(r'(?i)\bSOT[-\s]?\d'),
    re.compile(r'(?i)\bTSSOP\b'),
    re.compile(r'(?i)\bDFN\b'),
    re.compile(r'(?i)\bWLCSP\b'),
    re.compile(r'(?i)\bTO[-\s]?220\b'),
    re.compile(r'(?i)\bDPAK\b'),
    re.compile(r'(?i)\bD2PAK\b'),
    re.compile(r'(?i)\bLQFP\b'),
    re.compile(r'(?i)\bHTSSOP\b'),
    re.compile(r'(?i)\bSOP\b'),
    re.compile(r'(?i)\bMSOP\b'),
    re.compile(r'(?i)\bCSP\b'),
    # Dimensions and data
    re.compile(r'(?i)\bpackage\s+dimensions?\b'),
    re.compile(r'(?i)\bmechanical\s+data\b'),
    re.compile(r'(?i)\bdimension(?:s|ed)?\s+(?:table|drawing)\b'),
    re.compile(r'(?i)\bbody\s+(?:length|width|height|size)\b'),
    # Land pattern and footprint
    re.compile(r'(?i)\bland\s+pattern\b'),
    re.compile(r'(?i)\bfootprint\b'),
    re.compile(r'(?i)\brecommended\s+pad\b'),
    re.compile(r'(?i)\bPCB\s+layout\b'),
    re.compile(r'(?i)\bpad\s+(?:layout|geometry|dimensions?)\b'),
    re.compile(r'(?i)\bsolder\s+pad\b'),
    # Assembly and soldering
    re.compile(r'(?i)\bsoldering\b'),
    re.compile(r'(?i)\breflow\b'),
    re.compile(r'(?i)\bsolder(?:ing)?\s+profile\b'),
    re.compile(r'(?i)\bmoisture\s+sensitivity\b'),
    re.compile(r'(?i)\bMSL\b'),
    re.compile(r'(?i)\breflow\s+(?:temperature|profile|soldering)\b'),
    # Ordering information
    re.compile(r'(?i)\bordering\s+information\b'),
    re.compile(r'(?i)\border\s+code\b'),
    re.compile(r'(?i)\bdevice\s+marking\b'),
    re.compile(r'(?i)\bpart\s+number(?:ing)?\b'),
    re.compile(r'(?i)\bpackage\s+(?:marking|identification)\b'),
    # Thermal pad
    re.compile(r'(?i)\bthermal\s+pad\b'),
    re.compile(r'(?i)\bexposed\s+pad\b'),
    re.compile(r'(?i)\bPowerPAD\b'),
    re.compile(r'(?i)\bDAP\b'),
    re.compile(r'(?i)\bdie\s+attach\s+pad\b'),
    # Additional patterns
    re.compile(r'(?i)\bpackage\s+information\b'),
    re.compile(r'(?i)\bpackage\s+type\b'),
    re.compile(r'(?i)\bmechanical\s+specification\b'),
    re.compile(r'(?i)\btape\s+and\s+reel\b'),
]

# Minimum number of pattern matches required to select a page
PACKAGE_PAGE_THRESHOLD = 2


# ============================================
# Valid enums and constants
# ============================================

# Supported package type enum (35+ types)
VALID_PACKAGE_TYPES = {
    "QFN", "VQFN", "WQFN", "UQFN", "TQFN",
    "DFN", "WDFN", "UDFN", "SON",
    "BGA", "FBGA", "WLCSP", "DSBGA", "LFBGA", "TFBGA", "CABGA", "UBGA",
    "SOIC", "SOP", "SSOP", "TSSOP", "HTSSOP", "MSOP", "QSOP",
    "SOT-23", "SOT-223", "SOT-363", "SOT-563", "SOT-89", "SOT-323",
    "LQFP", "TQFP", "PQFP", "MQFP", "EQFP",
    "TO-220", "TO-252", "TO-263", "TO-92", "TO-247", "TO-3P",
    "DPAK", "D2PAK", "D3PAK",
    "SC-70", "SC-88", "SC-59",
    "CSP", "LGA", "PLCC",
    "DIP", "PDIP", "CDIP", "CERDIP",
    "QFP", "TSOP",
    "SIP", "ZIP", "WSON",
}

# Dimension sanity limits (mm)
_DIM_MIN_VALUE = 0.0
_DIM_MAX_REASONABLE = 200.0  # 200mm is a very large package

# Pin pitch limits (mm)
_PITCH_MIN = 0.2
_PITCH_MAX = 5.0

# Reflow temperature limits (Celsius)
_REFLOW_TEMP_MIN = 220
_REFLOW_TEMP_MAX = 280

# Theta_JA limits (C/W)
_THETA_JA_MIN = 1.0
_THETA_JA_MAX = 500.0


# ============================================
# Gemini API call helper
# ============================================

def _call_gemini_vision(client, model, images, prompt, max_retries=2):
    """Call Gemini Vision API with retry logic. Returns parsed dict or error dict."""
    contents = [prompt]
    for img in images:
        contents.append(types.Part.from_bytes(data=img, mime_type='image/png'))

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model, contents=contents, config={"temperature": 0.1}
            )
            raw = response.text
            # Clean markdown wrapping
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            # Find JSON boundaries
            start = raw.find('{')
            end = raw.rfind('}')
            if start >= 0 and end > start:
                raw = raw[start:end + 1]
            result = json.loads(raw.strip())
            if isinstance(result, list):
                result = result[0] if result else {"error": "Empty list"}
            if not isinstance(result, dict):
                return {"error": f"Unexpected type: {type(result).__name__}"}
            # Normalize key names — the model might use alternate keys
            if "packages" not in result:
                for key in ["package_list", "packageList", "package_data",
                            "package_variants", "mechanical"]:
                    if key in result:
                        result["packages"] = result.pop(key)
                        break
            if "package_summary" not in result:
                for key in ["summary", "packageSummary", "mechanical_summary"]:
                    if key in result:
                        result["package_summary"] = result.pop(key)
                        break
            return result
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                time.sleep(3)
                continue
            return {
                "error": f"JSON parse failed: {str(e)}",
                "raw": raw[:500] if 'raw' in dir() else "",
            }
        except Exception as e:
            if attempt < max_retries and (
                "503" in str(e) or "429" in str(e) or "504" in str(e)
                or "timeout" in str(e).lower()
                or "ReadTimeout" in str(type(e).__name__)
                or "ConnectTimeout" in str(type(e).__name__)
            ):
                time.sleep(10)
                continue
            return {"error": str(e)}


# ============================================
# Validation helpers
# ============================================

def _check_dimension_minmax(dim_obj, dim_label, package_label):
    """Validate a min/nom/max dimension object.

    Returns list of issue dicts.
    """
    issues = []
    if dim_obj is None or not isinstance(dim_obj, dict):
        return issues

    min_val = dim_obj.get("min")
    nom_val = dim_obj.get("nom")
    max_val = dim_obj.get("max")

    values = {}
    for key, val in [("min", min_val), ("nom", nom_val), ("max", max_val)]:
        if val is not None:
            if not isinstance(val, (int, float)):
                issues.append({
                    "level": "error",
                    "message": (
                        f"{package_label} {dim_label}.{key}: "
                        f"value '{val}' is not numeric"
                    ),
                })
                continue
            if val < _DIM_MIN_VALUE:
                issues.append({
                    "level": "error",
                    "message": (
                        f"{package_label} {dim_label}.{key}: "
                        f"negative dimension {val} mm"
                    ),
                })
            elif val > _DIM_MAX_REASONABLE:
                issues.append({
                    "level": "warning",
                    "message": (
                        f"{package_label} {dim_label}.{key}: "
                        f"unusually large dimension {val} mm"
                    ),
                })
            values[key] = val

    # Check min <= nom <= max ordering
    if "min" in values and "nom" in values:
        if values["min"] > values["nom"]:
            issues.append({
                "level": "error",
                "message": (
                    f"{package_label} {dim_label}: "
                    f"min ({values['min']}) > nom ({values['nom']})"
                ),
            })
    if "nom" in values and "max" in values:
        if values["nom"] > values["max"]:
            issues.append({
                "level": "error",
                "message": (
                    f"{package_label} {dim_label}: "
                    f"nom ({values['nom']}) > max ({values['max']})"
                ),
            })
    if "min" in values and "max" in values:
        if values["min"] > values["max"]:
            issues.append({
                "level": "error",
                "message": (
                    f"{package_label} {dim_label}: "
                    f"min ({values['min']}) > max ({values['max']})"
                ),
            })

    return issues


def _validate_pitch(pitch_mm, package_label):
    """Validate pin pitch is within reasonable range.

    Returns list of issue dicts.
    """
    issues = []
    if pitch_mm is None:
        return issues
    if not isinstance(pitch_mm, (int, float)):
        issues.append({
            "level": "error",
            "message": f"{package_label}: pitch value '{pitch_mm}' is not numeric",
        })
        return issues
    if pitch_mm <= 0:
        issues.append({
            "level": "error",
            "message": f"{package_label}: pitch {pitch_mm} mm is non-positive",
        })
    elif pitch_mm < _PITCH_MIN:
        issues.append({
            "level": "warning",
            "message": (
                f"{package_label}: pitch {pitch_mm} mm is below "
                f"typical minimum ({_PITCH_MIN} mm)"
            ),
        })
    elif pitch_mm > _PITCH_MAX:
        issues.append({
            "level": "warning",
            "message": (
                f"{package_label}: pitch {pitch_mm} mm exceeds "
                f"typical maximum ({_PITCH_MAX} mm)"
            ),
        })
    return issues


def _validate_reflow_temp(reflow_obj, package_label):
    """Validate reflow profile peak temperature.

    Returns list of issue dicts.
    """
    issues = []
    if reflow_obj is None or not isinstance(reflow_obj, dict):
        return issues
    peak_temp = reflow_obj.get("peak_temp_c")
    if peak_temp is None:
        return issues
    if not isinstance(peak_temp, (int, float)):
        issues.append({
            "level": "error",
            "message": (
                f"{package_label} reflow: peak_temp_c "
                f"'{peak_temp}' is not numeric"
            ),
        })
        return issues
    if peak_temp < _REFLOW_TEMP_MIN:
        issues.append({
            "level": "warning",
            "message": (
                f"{package_label} reflow: peak_temp_c {peak_temp} C "
                f"is below typical minimum ({_REFLOW_TEMP_MIN} C)"
            ),
        })
    elif peak_temp > _REFLOW_TEMP_MAX:
        issues.append({
            "level": "warning",
            "message": (
                f"{package_label} reflow: peak_temp_c {peak_temp} C "
                f"exceeds typical maximum ({_REFLOW_TEMP_MAX} C)"
            ),
        })
    return issues


def _validate_thermal_properties(thermal_obj, package_label):
    """Validate thermal resistance values.

    Returns list of issue dicts.
    """
    issues = []
    if thermal_obj is None or not isinstance(thermal_obj, dict):
        return issues
    theta_ja = thermal_obj.get("theta_ja_c_per_w")
    if theta_ja is not None:
        if not isinstance(theta_ja, (int, float)):
            issues.append({
                "level": "error",
                "message": (
                    f"{package_label} thermal: theta_ja "
                    f"'{theta_ja}' is not numeric"
                ),
            })
        elif theta_ja < _THETA_JA_MIN:
            issues.append({
                "level": "warning",
                "message": (
                    f"{package_label} thermal: theta_ja {theta_ja} C/W "
                    f"is below typical minimum ({_THETA_JA_MIN} C/W)"
                ),
            })
        elif theta_ja > _THETA_JA_MAX:
            issues.append({
                "level": "warning",
                "message": (
                    f"{package_label} thermal: theta_ja {theta_ja} C/W "
                    f"exceeds typical maximum ({_THETA_JA_MAX} C/W)"
                ),
            })

    # Also check theta_jc if present
    theta_jc = thermal_obj.get("theta_jc_c_per_w")
    if theta_jc is not None:
        if not isinstance(theta_jc, (int, float)):
            issues.append({
                "level": "error",
                "message": (
                    f"{package_label} thermal: theta_jc "
                    f"'{theta_jc}' is not numeric"
                ),
            })
        elif theta_jc < 0:
            issues.append({
                "level": "error",
                "message": (
                    f"{package_label} thermal: theta_jc {theta_jc} C/W "
                    f"is negative"
                ),
            })

    # Power dissipation sanity
    pwr = thermal_obj.get("power_dissipation_w")
    if pwr is not None:
        if not isinstance(pwr, (int, float)):
            issues.append({
                "level": "error",
                "message": (
                    f"{package_label} thermal: power_dissipation_w "
                    f"'{pwr}' is not numeric"
                ),
            })
        elif pwr <= 0:
            issues.append({
                "level": "warning",
                "message": (
                    f"{package_label} thermal: power_dissipation_w "
                    f"{pwr} W is non-positive"
                ),
            })

    return issues


def _validate_moisture_sensitivity(msl_obj, package_label):
    """Validate moisture sensitivity level data.

    Returns list of issue dicts.
    """
    issues = []
    if msl_obj is None or not isinstance(msl_obj, dict):
        return issues

    msl_level = msl_obj.get("msl_level")
    if msl_level is not None:
        # MSL levels are typically "MSL 1" through "MSL 6" or just "1"-"6"
        valid_levels = {
            "MSL 1", "MSL 2", "MSL 2a", "MSL 3", "MSL 4", "MSL 5", "MSL 5a", "MSL 6",
            "1", "2", "2a", "3", "4", "5", "5a", "6",
        }
        if msl_level not in valid_levels:
            issues.append({
                "level": "warning",
                "message": (
                    f"{package_label} MSL: unrecognized level "
                    f"'{msl_level}', expected one of MSL 1-6"
                ),
            })

    peak_temp = msl_obj.get("peak_reflow_temp_c")
    if peak_temp is not None:
        if isinstance(peak_temp, (int, float)):
            if peak_temp < _REFLOW_TEMP_MIN or peak_temp > _REFLOW_TEMP_MAX:
                issues.append({
                    "level": "warning",
                    "message": (
                        f"{package_label} MSL: peak_reflow_temp_c "
                        f"{peak_temp} C outside typical range "
                        f"({_REFLOW_TEMP_MIN}-{_REFLOW_TEMP_MAX} C)"
                    ),
                })

    return issues


# ============================================
# Summary builder
# ============================================

def _build_package_summary(packages):
    """Build a package_summary dict from the packages list.

    Returns a summary dict with aggregated statistics.
    """
    if not packages:
        return {
            "total_packages": 0,
            "package_types": [],
            "has_exposed_pad": False,
            "has_land_pattern": False,
            "has_thermal_data": False,
            "has_ordering_info": False,
        }

    pkg_types = set()
    has_exposed = False
    has_land = False
    has_thermal = False
    has_ordering = False

    for pkg in packages:
        ptype = pkg.get("package_type")
        if ptype:
            pkg_types.add(ptype)

        ep = pkg.get("exposed_pad")
        if isinstance(ep, dict) and ep.get("present"):
            has_exposed = True

        lp = pkg.get("land_pattern")
        if isinstance(lp, dict) and any(
            lp.get(k) is not None
            for k in ("pad_length_mm", "pad_width_mm", "pad_pitch_mm")
        ):
            has_land = True

        tp = pkg.get("thermal_properties")
        if isinstance(tp, dict) and any(
            tp.get(k) is not None
            for k in ("theta_ja_c_per_w", "theta_jc_c_per_w", "power_dissipation_w")
        ):
            has_thermal = True

        oi = pkg.get("ordering_info")
        if isinstance(oi, list) and len(oi) > 0:
            has_ordering = True

    return {
        "total_packages": len(packages),
        "package_types": sorted(pkg_types),
        "has_exposed_pad": has_exposed,
        "has_land_pattern": has_land,
        "has_thermal_data": has_thermal,
        "has_ordering_info": has_ordering,
    }


# ============================================
# Extractor class
# ============================================

class PackageExtractor(BaseExtractor):
    """Extracts package and mechanical data from datasheet pages.

    Identifies pages containing package outlines, mechanical drawings,
    dimension tables, land patterns, thermal properties, soldering/reflow
    profiles, moisture sensitivity levels, marking codes, and ordering
    information. Uses Gemini Vision API to extract structured package data.
    """

    DOMAIN_NAME = "package"

    def select_pages(self) -> list[int]:
        """Select pages that contain package/mechanical content.

        Scans page text previews for package-related patterns. A page is
        selected when it matches at least PACKAGE_PAGE_THRESHOLD (2) distinct
        patterns, reducing false positives from pages that merely mention a
        package name in passing.

        Returns:
            Sorted list of page numbers containing package/mechanical data.
        """
        package_pages = set()

        for page_info in self.page_classification:
            text = page_info.text_preview.lower() if page_info.text_preview else ""

            match_count = 0
            for pattern in PACKAGE_PAGE_PATTERNS:
                if pattern.search(text):
                    match_count += 1
                    if match_count >= PACKAGE_PAGE_THRESHOLD:
                        package_pages.add(page_info.page_num)
                        break

            # Also include pages that are explicitly classified as package/mechanical
            if hasattr(page_info, "category") and page_info.category in (
                "package", "mechanical", "ordering"
            ):
                # Still require at least one pattern match for these categories
                if match_count >= 1:
                    package_pages.add(page_info.page_num)

        return sorted(package_pages)

    def extract(self, rendered_images) -> dict:
        """Use Gemini Vision API to extract package data from page images.

        Args:
            rendered_images: Dict mapping page_num -> PNG bytes, or list of
                PNG bytes (ordered by page).

        Returns:
            Dict with 'packages' list and 'package_summary', containing
            all extracted package/mechanical information.
        """
        if isinstance(rendered_images, dict):
            images = list(rendered_images.values())
        else:
            images = rendered_images

        if not images:
            return {
                "packages": [],
                "package_summary": _build_package_summary([]),
            }

        result = _call_gemini_vision(
            self.client, self.model, images, PACKAGE_EXTRACTION_PROMPT
        )

        # If extraction failed, return error with empty structure
        if "error" in result:
            return result

        # Ensure packages list exists
        packages = result.get("packages", [])

        # Rebuild/verify the summary from actual extracted data
        result["package_summary"] = _build_package_summary(packages)

        return result

    def validate(self, extraction_result: dict) -> dict:
        """Validate extracted package/mechanical data.

        Checks:
        - package_type is from the valid enum (35+ types)
        - All dimensions are positive and min <= nom <= max
        - Pin pitch is within 0.2-5.0 mm (warns outside range)
        - Reflow peak temperature is within 220-280 C (warns outside range)
        - Theta_JA is within 1-500 C/W (warns outside range)
        - No duplicate package_name entries
        - Summary consistency with extracted data

        Args:
            extraction_result: Dict returned by extract().

        Returns:
            Dict with 'package_validation' list of issues and
            'package_count' integer.
        """
        issues = []

        if "error" in extraction_result:
            return {"package_validation": issues, "package_count": 0}

        packages = extraction_result.get("packages", [])

        if not packages:
            issues.append({
                "level": "warning",
                "message": "No packages found in extraction result",
            })
            return {"package_validation": issues, "package_count": 0}

        seen_names = {}

        for i, pkg in enumerate(packages):
            prefix = f"package[{i}]"
            pkg_name = pkg.get("package_name", "?")
            label = f"{prefix} '{pkg_name}'"

            # --- Check package_type enum ---
            pkg_type = pkg.get("package_type")
            if pkg_type is None:
                issues.append({
                    "level": "warning",
                    "message": f"{label}: missing package_type",
                })
            elif pkg_type not in VALID_PACKAGE_TYPES:
                issues.append({
                    "level": "warning",
                    "message": (
                        f"{label}: package_type '{pkg_type}' not in "
                        f"recognized set ({len(VALID_PACKAGE_TYPES)} known types)"
                    ),
                })

            # --- Check pin_count ---
            pin_count = pkg.get("pin_count")
            if pin_count is not None:
                if not isinstance(pin_count, int) or pin_count <= 0:
                    issues.append({
                        "level": "error",
                        "message": (
                            f"{label}: pin_count '{pin_count}' "
                            f"must be a positive integer"
                        ),
                    })

            # --- Validate dimensions (min/nom/max) ---
            dim_fields = [
                ("body_length_mm", "body_length_mm"),
                ("body_width_mm", "body_width_mm"),
                ("body_height_mm", "body_height_mm"),
                ("lead_span_mm", "lead_span_mm"),
                ("terminal_width_mm", "terminal_width_mm"),
                ("terminal_length_mm", "terminal_length_mm"),
            ]
            for field_key, dim_label in dim_fields:
                dim_obj = pkg.get(field_key)
                dim_issues = _check_dimension_minmax(dim_obj, dim_label, label)
                issues.extend(dim_issues)

            # --- Validate pitch ---
            pitch_issues = _validate_pitch(pkg.get("pitch_mm"), label)
            issues.extend(pitch_issues)

            # --- Validate exposed pad dimensions ---
            ep = pkg.get("exposed_pad")
            if isinstance(ep, dict) and ep.get("present"):
                for ep_dim in ("length_mm", "width_mm"):
                    val = ep.get(ep_dim)
                    if val is not None:
                        if not isinstance(val, (int, float)):
                            issues.append({
                                "level": "error",
                                "message": (
                                    f"{label} exposed_pad.{ep_dim}: "
                                    f"'{val}' is not numeric"
                                ),
                            })
                        elif val <= 0:
                            issues.append({
                                "level": "error",
                                "message": (
                                    f"{label} exposed_pad.{ep_dim}: "
                                    f"value {val} mm is non-positive"
                                ),
                            })

            # --- Validate reflow profile ---
            reflow_issues = _validate_reflow_temp(
                pkg.get("reflow_profile"), label
            )
            issues.extend(reflow_issues)

            # --- Validate thermal properties ---
            thermal_issues = _validate_thermal_properties(
                pkg.get("thermal_properties"), label
            )
            issues.extend(thermal_issues)

            # --- Validate moisture sensitivity ---
            msl_issues = _validate_moisture_sensitivity(
                pkg.get("moisture_sensitivity"), label
            )
            issues.extend(msl_issues)

            # --- Duplicate package_name detection ---
            if pkg_name and pkg_name != "?":
                name_normalized = pkg_name.strip().upper()
                if name_normalized in seen_names:
                    issues.append({
                        "level": "warning",
                        "message": (
                            f"{label}: duplicate package_name "
                            f"(also at package[{seen_names[name_normalized]}])"
                        ),
                    })
                else:
                    seen_names[name_normalized] = i

            # --- Validate ordering info ---
            oi = pkg.get("ordering_info")
            if isinstance(oi, list):
                seen_parts = set()
                for j, order in enumerate(oi):
                    pn = order.get("part_number")
                    if pn:
                        if pn in seen_parts:
                            issues.append({
                                "level": "warning",
                                "message": (
                                    f"{label} ordering_info[{j}]: "
                                    f"duplicate part_number '{pn}'"
                                ),
                            })
                        else:
                            seen_parts.add(pn)

        # --- Summary consistency check ---
        summary = extraction_result.get("package_summary", {})
        if summary:
            reported_total = summary.get("total_packages")
            if reported_total is not None and reported_total != len(packages):
                issues.append({
                    "level": "warning",
                    "message": (
                        f"package_summary.total_packages ({reported_total}) "
                        f"does not match actual count ({len(packages)})"
                    ),
                })

            # Check package_types consistency
            reported_types = summary.get("package_types", [])
            actual_types = set()
            for pkg in packages:
                pt = pkg.get("package_type")
                if pt:
                    actual_types.add(pt)
            if set(reported_types) != actual_types:
                issues.append({
                    "level": "warning",
                    "message": (
                        f"package_summary.package_types {sorted(reported_types)} "
                        f"does not match actual types {sorted(actual_types)}"
                    ),
                })

            # Check boolean flags consistency
            has_ep = any(
                isinstance(pkg.get("exposed_pad"), dict)
                and pkg["exposed_pad"].get("present")
                for pkg in packages
            )
            if summary.get("has_exposed_pad") != has_ep:
                issues.append({
                    "level": "warning",
                    "message": (
                        f"package_summary.has_exposed_pad "
                        f"({summary.get('has_exposed_pad')}) does not match "
                        f"actual data ({has_ep})"
                    ),
                })

        return {
            "package_validation": issues,
            "package_count": len(packages),
        }
