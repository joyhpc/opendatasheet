"""Power sequence extraction module.

Handles extraction of power-up/down sequencing, soft-start, inrush current,
enable/shutdown timing, UVLO thresholds, and power rail ordering from datasheets.
"""
import re

from extractors.base import BaseExtractor
from extractors.gemini_json import call_gemini_json_response


# ============================================
# Prompts
# ============================================

POWER_SEQUENCE_EXTRACTION_PROMPT = """You are an expert electronic component datasheet parser specializing in power sequencing.
Analyze the provided datasheet page images and extract ALL power sequence related information into a structured JSON format.

CRITICAL RULES:
1. Extract power-up and power-down stage sequences if described
2. Extract all power rails mentioned in sequencing context
3. Extract startup parameters: soft-start time, inrush current, enable delay, etc.
4. Extract protection thresholds: UVLO, OVP, OCP, OTP, POR
5. Extract sequencing rules (which rail must come before which)
6. If a value is not specified or not visible, use null
7. Output ONLY valid JSON, no markdown, no code fences

POWER STAGES TO EXTRACT:
- stage_name: Descriptive name (e.g., "VIN applied", "EN high", "Soft-start begin", "Output regulated")
- stage_order: Integer sequence order (1-based), or null if order is unclear
- description: Brief description of what happens at this stage
- trigger: What triggers this stage (e.g., "VIN exceeds UVLO threshold", "EN pin driven high")
- duration: Duration as {min, typ, max, unit} or null
- associated_rail: Which power rail this stage relates to, or null

POWER RAILS TO EXTRACT:
- name: Rail name exactly as shown (e.g., "VCCINT", "VDD_IO", "VOUT", "VIN")
- nominal_voltage: Nominal voltage as number, or null
- voltage_range: {min, max, unit} or null
- sequence_order: Integer order in power-up sequence, or null
- ramp_rate: Ramp rate as {min, typ, max, unit} or null
- max_current: Maximum current as {min, typ, max, unit} or null

STARTUP PARAMETERS TO EXTRACT:
- parameter: Name of the parameter
- category: One of: "soft_start_time", "inrush_current", "startup_time", "enable_delay", "shutdown_delay", "power_good_delay", "ramp_rate", "turn_on_time", "turn_off_time", "other"
- min/typ/max: Numeric values, use null if not specified
- unit: Unit string (e.g., "ms", "us", "mA", "V/ms")
- conditions: Test conditions, or null

PROTECTION THRESHOLDS TO EXTRACT:
- parameter: Name of the parameter
- category: One of: "UVLO_rising", "UVLO_falling", "UVLO_hysteresis", "OVP", "OCP", "OTP", "power_on_reset", "brownout", "other"
- min/typ/max: Numeric values, use null if not specified
- unit: Unit string (e.g., "V", "A", "°C")
- conditions: Test conditions, or null

SEQUENCING RULES TO EXTRACT:
- rail_before: Rail that must power up first
- rail_after: Rail that powers up after
- min_delay: Minimum delay as {min, typ, max, unit} or null
- max_delay: Maximum delay as {min, typ, max, unit} or null
- description: Description of the rule, or null

SUMMARY FLAGS:
- has_soft_start: true if the device has a soft-start feature
- has_power_good: true if the device has a power-good output (PGOOD)
- has_enable_pin: true if the device has an enable/shutdown pin
- has_uvlo: true if the device has under-voltage lockout
- rail_count: Number of distinct power rails identified
- sequencing_type: One of "fixed", "configurable", "independent", "simultaneous", or null

OUTPUT JSON SCHEMA:
{
  "power_stages": [
    {
      "stage_name": "VIN applied",
      "stage_order": 1,
      "description": "Input voltage applied to VIN pin",
      "trigger": "External power supply connected",
      "duration": null,
      "associated_rail": "VIN"
    }
  ],
  "power_rails": [
    {
      "name": "VOUT",
      "nominal_voltage": 3.3,
      "voltage_range": {"min": 3.2, "max": 3.4, "unit": "V"},
      "sequence_order": 1,
      "ramp_rate": {"min": null, "typ": 1.0, "max": null, "unit": "V/ms"},
      "max_current": {"min": null, "typ": null, "max": 500, "unit": "mA"}
    }
  ],
  "startup_parameters": [
    {
      "parameter": "Soft-Start Time",
      "category": "soft_start_time",
      "min": null,
      "typ": 2.0,
      "max": 5.0,
      "unit": "ms",
      "conditions": "CL = 10uF"
    }
  ],
  "protection_thresholds": [
    {
      "parameter": "UVLO Threshold Rising",
      "category": "UVLO_rising",
      "min": 2.5,
      "typ": 2.7,
      "max": 2.9,
      "unit": "V",
      "conditions": null
    }
  ],
  "sequencing_rules": [
    {
      "rail_before": "VCCINT",
      "rail_after": "VDD_IO",
      "min_delay": {"min": null, "typ": null, "max": null, "unit": "ms"},
      "max_delay": {"min": null, "typ": null, "max": 10, "unit": "ms"},
      "description": "Core voltage must be established before I/O voltage"
    }
  ],
  "power_sequence_summary": {
    "has_soft_start": true,
    "has_power_good": false,
    "has_enable_pin": true,
    "has_uvlo": true,
    "rail_count": 1,
    "sequencing_type": "fixed"
  }
}

IMPORTANT:
- Extract ALL power sequence information visible in the images
- If no power stages are explicitly shown, set "power_stages" to an empty array []
- If no sequencing rules are described, set "sequencing_rules" to an empty array []
- Look for timing diagrams showing power-up/down sequences
- Look for tables with startup/shutdown parameters
- UVLO and soft-start information may appear in electrical characteristics tables
- Preserve exact parameter names from the datasheet
"""


# Patterns used to identify pages that contain power sequence content
POWER_SEQUENCE_PAGE_PATTERNS = [
    re.compile(r'(?i)power[\s-]*up\s+sequence'),
    re.compile(r'(?i)power[\s-]*down\s+sequence'),
    re.compile(r'(?i)power\s+sequencing'),
    re.compile(r'(?i)soft[\s-]*start'),
    re.compile(r'(?i)inrush\s+current'),
    re.compile(r'(?i)\benable\b.*\b(pin|input|threshold|delay|timing)\b'),
    re.compile(r'(?i)\bshutdown\b.*\b(pin|input|threshold|delay|timing|mode)\b'),
    re.compile(r'(?i)\bUVLO\b'),
    re.compile(r'(?i)under[\s-]*voltage\s+lock[\s-]*out'),
    re.compile(r'(?i)power[\s-]*on[\s-]*reset'),
    re.compile(r'(?i)\bPOR\b'),
    re.compile(r'(?i)power[\s-]*good'),
    re.compile(r'(?i)\bPGOOD\b'),
    re.compile(r'(?i)start[\s-]*up\s+(time|sequence|delay|behavior|characteristic)'),
    re.compile(r'(?i)turn[\s-]*on\s+(time|delay|sequence|characteristic)'),
    re.compile(r'(?i)turn[\s-]*off\s+(time|delay|sequence|characteristic)'),
    re.compile(r'(?i)ramp\s+(rate|time)'),
    re.compile(r'(?i)slew\s+rate.*power'),
    re.compile(r'(?i)power\s+supply\s+(ramp|sequenc)'),
]

# Valid startup parameter categories (matches schema enum)
VALID_STARTUP_CATEGORIES = {
    "soft_start_time", "inrush_current", "startup_time", "enable_delay",
    "shutdown_delay", "power_good_delay", "ramp_rate", "turn_on_time",
    "turn_off_time", "other",
}

# Valid protection threshold categories (matches schema enum)
VALID_PROTECTION_CATEGORIES = {
    "UVLO_rising", "UVLO_falling", "UVLO_hysteresis", "OVP", "OCP",
    "OTP", "power_on_reset", "brownout", "other",
}

# Valid sequencing types (matches schema enum)
VALID_SEQUENCING_TYPES = {"fixed", "configurable", "independent", "simultaneous", None}


# ============================================
# Gemini API call helper
# ============================================

def _call_gemini_vision(client, model, images, prompt, max_retries=2):
    """Call Gemini Vision API with retry logic. Returns parsed dict or error dict."""
    return call_gemini_json_response(
        client,
        model,
        images,
        prompt,
        max_retries=max_retries,
        key_aliases={
            "power_stages": ("powerStages", "stages", "power_up_stages"),
            "power_rails": ("powerRails", "rails", "supply_rails"),
            "startup_parameters": (
                "startupParameters",
                "startup_params",
                "timing_parameters",
            ),
            "protection_thresholds": (
                "protectionThresholds",
                "thresholds",
                "protection",
            ),
            "sequencing_rules": ("sequencingRules", "rules", "ordering_rules"),
            "power_sequence_summary": (
                "summary",
                "powerSequenceSummary",
                "sequence_summary",
            ),
        },
    )


# ============================================
# Validation helpers
# ============================================

def _check_sequence_order_gaps(items, order_key="stage_order"):
    """Check that sequence orders are positive integers without gaps.

    Returns list of issue dicts.
    """
    issues = []
    orders = []
    for item in items:
        order = item.get(order_key)
        if order is not None:
            if not isinstance(order, int) or order < 1:
                name = item.get("stage_name") or item.get("name", "?")
                issues.append({
                    "level": "error",
                    "message": f"'{name}': {order_key} must be a positive integer, got {order}"
                })
            else:
                orders.append(order)

    if orders:
        orders_sorted = sorted(orders)
        expected = list(range(1, len(orders_sorted) + 1))
        if orders_sorted != expected:
            issues.append({
                "level": "warning",
                "message": f"Sequence orders {orders_sorted} have gaps or don't start at 1 (expected {expected})"
            })

    return issues


def _check_contradictory_rules(rules):
    """Check for contradictory sequencing rules (A before B and B before A).

    Returns list of issue dicts.
    """
    issues = []
    pairs = set()
    for rule in rules:
        before = rule.get("rail_before", "")
        after = rule.get("rail_after", "")
        if not before or not after:
            continue
        pair = (before, after)
        reverse = (after, before)
        if reverse in pairs:
            issues.append({
                "level": "error",
                "message": f"Contradictory sequencing rules: '{before}' before '{after}' AND '{after}' before '{before}'"
            })
        pairs.add(pair)

    return issues


class PowerSequenceExtractor(BaseExtractor):
    """Extracts power sequencing information from datasheet pages.

    Identifies pages containing power-up/down sequences, soft-start parameters,
    UVLO thresholds, enable/shutdown timing, and rail ordering constraints.
    Uses Gemini Vision API to extract structured power sequence data.
    """

    DOMAIN_NAME = "power_sequence"

    def select_pages(self) -> list[int]:
        """Select pages that contain power sequence content.

        Scans page text previews for power sequencing patterns. Also considers
        pages classified as 'electrical' or 'application' that may contain
        startup/shutdown parameters or power sequencing information.
        """
        power_seq_pages = set()

        for page_info in self.page_classification:
            text = page_info.text_preview.lower() if page_info.text_preview else ""

            # Check text preview against power sequence patterns
            for pattern in POWER_SEQUENCE_PAGE_PATTERNS:
                if pattern.search(text):
                    power_seq_pages.add(page_info.page_num)
                    break

            # Also check pages classified as 'electrical', 'application', or 'other'
            # that might contain power sequence content not caught by the short preview.
            if page_info.category in ("electrical", "application", "other"):
                if any(kw in text for kw in [
                    "soft start", "soft-start", "inrush", "uvlo",
                    "power good", "pgood", "enable", "shutdown",
                    "startup", "start-up", "power-on reset", "por",
                    "power up", "power down", "turn-on", "turn-off",
                ]):
                    power_seq_pages.add(page_info.page_num)

        return sorted(power_seq_pages)

    def extract(self, rendered_images) -> dict:
        """Use Gemini Vision API to extract power sequence data from page images.

        Args:
            rendered_images: Dict mapping page_num -> PNG bytes, or list of PNG bytes.

        Returns:
            Dict with power_stages, power_rails, startup_parameters,
            protection_thresholds, sequencing_rules, and power_sequence_summary,
            matching the power_sequence.schema.json structure.
        """
        if isinstance(rendered_images, dict):
            images = list(rendered_images.values())
        else:
            images = rendered_images

        if not images:
            return {
                "power_stages": [],
                "power_rails": [],
                "startup_parameters": [],
                "protection_thresholds": [],
                "sequencing_rules": [],
                "power_sequence_summary": {},
            }

        return _call_gemini_vision(self.client, self.model, images, POWER_SEQUENCE_EXTRACTION_PROMPT)

    def validate(self, extraction_result: dict) -> dict:
        """Validate extracted power sequence data.

        Checks:
        - Startup parameter categories are from the allowed enum
        - Protection threshold categories are from the allowed enum
        - Sequence orders are positive integers without gaps
        - Protection thresholds have reasonable values
          (UVLO typically 1-60V, OTP typically 100-175 deg C)
        - Startup times are positive
        - No contradictory sequencing rules (A before B and B before A)
        - Sequencing type is from the allowed enum

        Returns:
            Dict with 'power_sequence_validation_issues' list and summary counts.
        """
        issues = []

        if "error" in extraction_result:
            return {
                "power_sequence_validation_issues": issues,
                "stage_count": 0,
                "rail_count": 0,
                "startup_param_count": 0,
                "protection_threshold_count": 0,
                "sequencing_rule_count": 0,
            }

        # --- Validate power stages ---
        stages = extraction_result.get("power_stages", [])
        if stages:
            stage_issues = _check_sequence_order_gaps(stages, "stage_order")
            issues.extend(stage_issues)

        # --- Validate power rails ---
        rails = extraction_result.get("power_rails", [])
        if rails:
            rail_issues = _check_sequence_order_gaps(rails, "sequence_order")
            issues.extend(rail_issues)

        # --- Validate startup parameters ---
        startup_params = extraction_result.get("startup_parameters", [])
        for i, param in enumerate(startup_params):
            prefix = f"startup_parameters[{i}]"
            name = param.get("parameter", "?")
            category = param.get("category")

            # Check category enum
            if category is not None and category not in VALID_STARTUP_CATEGORIES:
                issues.append({
                    "level": "error",
                    "message": f"{prefix} '{name}': invalid category '{category}', must be one of {sorted(VALID_STARTUP_CATEGORIES)}"
                })

            # Check that timing values are positive
            for field in ["min", "typ", "max"]:
                val = param.get(field)
                if val is not None and isinstance(val, (int, float)):
                    unit = (param.get("unit") or "").lower()
                    # Time-based parameters should be positive
                    if category in ("soft_start_time", "startup_time", "enable_delay",
                                    "shutdown_delay", "power_good_delay", "turn_on_time",
                                    "turn_off_time") and val < 0:
                        issues.append({
                            "level": "error",
                            "message": f"{prefix} '{name}': {field}={val} is negative for a time parameter"
                        })
                    # Inrush current should be positive
                    if category == "inrush_current" and val < 0:
                        issues.append({
                            "level": "warning",
                            "message": f"{prefix} '{name}': {field}={val} is negative for inrush current"
                        })

        # --- Validate protection thresholds ---
        thresholds = extraction_result.get("protection_thresholds", [])
        for i, thresh in enumerate(thresholds):
            prefix = f"protection_thresholds[{i}]"
            name = thresh.get("parameter", "?")
            category = thresh.get("category")

            # Check category enum
            if category is not None and category not in VALID_PROTECTION_CATEGORIES:
                issues.append({
                    "level": "error",
                    "message": f"{prefix} '{name}': invalid category '{category}', must be one of {sorted(VALID_PROTECTION_CATEGORIES)}"
                })

            # Sanity-check threshold values
            typ = thresh.get("typ")
            unit = (thresh.get("unit") or "").upper()

            if typ is not None and isinstance(typ, (int, float)):
                # UVLO thresholds typically 1-60V
                if category in ("UVLO_rising", "UVLO_falling") and "V" in unit:
                    if typ < 0.5 or typ > 100:
                        issues.append({
                            "level": "warning",
                            "message": f"{prefix} '{name}': UVLO typ={typ}{unit} outside typical range (0.5-100V)"
                        })

                # OTP thresholds typically 100-175 deg C
                if category == "OTP" and ("C" in unit or "°" in unit):
                    if typ < 50 or typ > 200:
                        issues.append({
                            "level": "warning",
                            "message": f"{prefix} '{name}': OTP typ={typ}{unit} outside typical range (50-200°C)"
                        })

        # --- Validate sequencing rules ---
        rules = extraction_result.get("sequencing_rules", [])
        if rules:
            contradiction_issues = _check_contradictory_rules(rules)
            issues.extend(contradiction_issues)

        # --- Validate summary ---
        summary = extraction_result.get("power_sequence_summary", {})
        seq_type = summary.get("sequencing_type")
        if seq_type is not None and seq_type not in VALID_SEQUENCING_TYPES:
            issues.append({
                "level": "warning",
                "message": f"power_sequence_summary: unknown sequencing_type '{seq_type}', expected one of {sorted(str(v) for v in VALID_SEQUENCING_TYPES if v is not None)}"
            })

        return {
            "power_sequence_validation_issues": issues,
            "stage_count": len(stages),
            "rail_count": len(rails),
            "startup_param_count": len(startup_params),
            "protection_threshold_count": len(thresholds),
            "sequencing_rule_count": len(rules),
        }
