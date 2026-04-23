"""Timing parameter extraction module.

Handles extraction of timing specifications from datasheets including
propagation delays, setup/hold times, rise/fall times, clock specifications,
and switching characteristics. Identifies AC timing pages and extracts
structured timing data via Gemini Vision API.
"""
import re

from extractors.base import BaseExtractor
from extractors.gemini_json import call_gemini_json_response


# ============================================
# Prompts
# ============================================

TIMING_EXTRACTION_PROMPT = """You are an expert electronic component datasheet parser specializing in timing specifications.
Analyze the provided datasheet page images and extract ALL timing parameters into a structured JSON format.

CRITICAL RULES:
1. Extract every timing parameter shown in AC characteristics, switching characteristics, or timing specification tables
2. For each parameter, capture the full min/typ/max values with units
3. Identify signal relationships (from/to) for propagation delays
4. If a value is not specified or not visible, use null
5. Output ONLY valid JSON, no markdown, no code fences

TIMING PARAMETER FIELDS TO EXTRACT:
- parameter: Parameter name exactly as shown in the datasheet (e.g., "Propagation Delay Low-to-High", "Setup Time")
- symbol: Symbol if shown (e.g., "tPLH", "tsu", "tpd"), or null
- category: Classify each parameter into exactly one of these categories:
  "propagation_delay" - signal propagation delays (tpd, tPLH, tPHL)
  "setup_time" - setup time requirements (tsu, tsetup)
  "hold_time" - hold time requirements (th, thold)
  "rise_time" - output rise time (tr, trise)
  "fall_time" - output fall time (tf, tfall)
  "pulse_width" - minimum/maximum pulse widths (tw, tpw)
  "clock_frequency" - maximum clock frequency (fmax, fCLK)
  "clock_period" - clock period specifications (tCLK, tCYC)
  "skew" - timing skew between signals (tskew)
  "jitter" - clock or signal jitter (tj)
  "duty_cycle" - duty cycle specifications
  "other" - any timing parameter that doesn't fit the above categories
- min: Minimum value as a number, or null
- typ: Typical value as a number, or null
- max: Maximum value as a number, or null
- unit: Unit string (e.g., "ns", "ps", "us", "ms", "MHz", "GHz", "kHz", "%")
- conditions: Test conditions as a string (e.g., "VCC = 3.3V, CL = 15pF, TA = 25C"), or null
- signal_from: Source signal or pin name for delays (e.g., "CLK", "A", "INPUT"), or null
- signal_to: Destination signal or pin name for delays (e.g., "Q", "Y", "OUTPUT"), or null
- edge: Signal edge context. Use exactly one of: "rising", "falling", "both", or null
- load_conditions: Load capacitance/resistance conditions (e.g., "CL = 50pF", "RL = 1kOhm"), or null

SUMMARY FIELDS:
- total_parameters: Integer count of all timing parameters extracted
- categories: Array of unique category strings found in the extracted parameters
- has_timing_diagram: Boolean - true if the pages contain a timing diagram illustration

OUTPUT JSON SCHEMA:
{
  "timing_parameters": [
    {
      "parameter": "Propagation Delay Low-to-High",
      "symbol": "tPLH",
      "category": "propagation_delay",
      "min": 1.5,
      "typ": 3.0,
      "max": 5.5,
      "unit": "ns",
      "conditions": "VCC = 5V, TA = 25C",
      "signal_from": "A",
      "signal_to": "Y",
      "edge": "rising",
      "load_conditions": "CL = 15pF"
    },
    {
      "parameter": "Setup Time",
      "symbol": "tsu",
      "category": "setup_time",
      "min": 5.0,
      "typ": null,
      "max": null,
      "unit": "ns",
      "conditions": "VCC = 3.3V",
      "signal_from": "D",
      "signal_to": "CLK",
      "edge": "rising",
      "load_conditions": null
    }
  ],
  "timing_summary": {
    "total_parameters": 12,
    "categories": ["propagation_delay", "setup_time", "hold_time", "rise_time", "fall_time"],
    "has_timing_diagram": true
  }
}

IMPORTANT:
- Extract ALL timing parameters visible in the images, not just the first few
- If the same parameter is specified at different supply voltages or temperatures, create separate entries
- For propagation delay parameters, always try to identify signal_from and signal_to
- Preserve the exact parameter names from the datasheet (do not rename)
- If a timing diagram is present, set has_timing_diagram to true even if you cannot extract values from it
- Include parameters from "AC Characteristics", "Switching Characteristics", "Dynamic Characteristics", and "Timing Specifications" sections
"""


# Patterns used to identify pages that contain timing content
TIMING_PAGE_PATTERNS = [
    re.compile(r'(?i)switching\s+characteristics'),
    re.compile(r'(?i)timing\s+specifications?'),
    re.compile(r'(?i)timing\s+diagrams?'),
    re.compile(r'(?i)timing\s+parameters?'),
    re.compile(r'(?i)timing\s+requirements?'),
    re.compile(r'(?i)timing\s+definitions?'),
    re.compile(r'(?i)timing\s+characteristics'),
    re.compile(r'(?i)AC\s+characteristics'),
    re.compile(r'(?i)AC\s+switching'),
    re.compile(r'(?i)AC\s+specifications?'),
    re.compile(r'(?i)AC\s+electrical'),
    re.compile(r'(?i)dynamic\s+characteristics'),
    re.compile(r'(?i)propagation\s+delay'),
    re.compile(r'(?i)setup\s+(and\s+)?hold\s+time'),
    re.compile(r'(?i)setup\s+time'),
    re.compile(r'(?i)hold\s+time'),
    re.compile(r'(?i)rise\s+(and\s+)?fall\s+time'),
    re.compile(r'(?i)rise\s+time'),
    re.compile(r'(?i)fall\s+time'),
    re.compile(r'(?i)clock\s+frequency'),
    re.compile(r'(?i)clock\s+specifications?'),
    re.compile(r'(?i)\bt[pP][dDLlHh]{1,3}\b'),   # tpd, tPLH, tPHL symbols
    re.compile(r'(?i)\bt[sS][uU]\b'),              # tsu symbol
    re.compile(r'(?i)\bt[hH]\b.*(?:hold|time|ns)'), # th symbol in timing context
]

# Valid timing categories (matches schema enum)
VALID_CATEGORIES = {
    "propagation_delay", "setup_time", "hold_time",
    "rise_time", "fall_time", "pulse_width",
    "clock_frequency", "clock_period", "skew",
    "jitter", "duty_cycle", "other",
}

# Valid timing units
VALID_TIMING_UNITS = {
    "ps", "ns", "us", "ms", "s",           # time units
    "Hz", "kHz", "MHz", "GHz",             # frequency units
    "%",                                     # duty cycle
}


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
            "timing_parameters": (
                "timingParameters",
                "timing_specs",
                "timing_data",
                "parameters",
                "timing",
            ),
            "timing_summary": ("summary", "timingSummary", "timing_summary_info"),
        },
    )


# ============================================
# Validation helpers
# ============================================

def _check_monotonicity(min_val, typ_val, max_val):
    """Check that min <= typ <= max (where provided).

    Returns True if monotonicity holds, False if violated.
    Returns None if there are fewer than 2 values to compare.
    """
    vals = [(label, v) for label, v in [("min", min_val), ("typ", typ_val), ("max", max_val)]
            if v is not None]
    if len(vals) < 2:
        return None
    for i in range(len(vals) - 1):
        if vals[i][1] > vals[i + 1][1]:
            return False
    return True


def _is_valid_timing_unit(unit):
    """Check whether a unit string is reasonable for timing parameters."""
    if not unit:
        return True  # null units are acceptable
    # Normalize common variations
    normalized = unit.strip()
    # Check direct match
    if normalized in VALID_TIMING_UNITS:
        return True
    # Check case-insensitive for some units
    lower = normalized.lower()
    if lower in {"ps", "ns", "us", "ms", "s", "hz", "khz", "mhz", "ghz", "%"}:
        return True
    # Allow micro-second variants
    if lower in {"\u00b5s", "\u03bcs"}:
        return True
    return False


class TimingExtractor(BaseExtractor):
    """Extracts timing specifications from datasheet pages.

    Identifies pages containing AC characteristics, switching characteristics,
    timing diagrams, and timing specification tables. Uses Gemini Vision API
    to extract structured timing data including propagation delays, setup/hold
    times, rise/fall times, and clock specifications.
    """

    DOMAIN_NAME = "timing"

    def select_pages(self) -> list[int]:
        """Select pages that contain timing specification content.

        Scans page text previews for timing-related patterns. Also considers
        pages classified as 'electrical' that might contain AC/switching
        characteristics embedded in general electrical specification pages.
        """
        timing_pages = set()

        for page_info in self.page_classification:
            text = page_info.text_preview.lower() if page_info.text_preview else ""

            # Check text preview against timing patterns
            for pattern in TIMING_PAGE_PATTERNS:
                if pattern.search(text):
                    timing_pages.add(page_info.page_num)
                    break

            # Also check pages classified as "electrical" or "other" that
            # contain timing-related content not caught by the short preview
            if page_info.category in ("electrical", "other"):
                timing_keywords = [
                    "propagation delay", "setup time", "hold time",
                    "rise time", "fall time", "switching",
                    "ac characteristics", "timing", "tpd", "tplh", "tphl",
                    "dynamic characteristics", "clock frequency",
                ]
                if any(kw in text for kw in timing_keywords):
                    timing_pages.add(page_info.page_num)

        return sorted(timing_pages)

    def extract(self, rendered_images) -> dict:
        """Use Gemini Vision API to extract timing parameters from page images.

        Args:
            rendered_images: Dict mapping page_num -> PNG bytes, or list of PNG bytes.

        Returns:
            Dict with 'timing_parameters' list and 'timing_summary', matching the
            timing.schema.json structure.
        """
        if isinstance(rendered_images, dict):
            images = list(rendered_images.values())
        else:
            images = rendered_images

        if not images:
            return {"timing_parameters": [], "timing_summary": {}}

        return _call_gemini_vision(self.client, self.model, images, TIMING_EXTRACTION_PROMPT)

    def validate(self, extraction_result: dict) -> dict:
        """Validate extracted timing data.

        Checks:
        - Category is from the allowed enum
        - Units are reasonable for timing parameters (ns, ps, us, MHz, etc.)
        - min <= typ <= max monotonicity
        - No duplicate parameters (same name + conditions)

        Returns:
            Dict with 'timing_validation_issues' list and 'timing_parameter_count' int.
        """
        issues = []

        if "error" in extraction_result:
            return {"timing_validation_issues": issues, "timing_parameter_count": 0}

        parameters = extraction_result.get("timing_parameters", [])

        if not parameters:
            issues.append({
                "level": "warning",
                "message": "No timing parameters found in extraction result"
            })
            return {"timing_validation_issues": issues, "timing_parameter_count": 0}

        seen_params = {}

        for i, param in enumerate(parameters):
            prefix = f"timing_parameter[{i}]"
            name = param.get("parameter", "?")

            # --- Check category is from allowed enum ---
            category = param.get("category")
            if category is None:
                issues.append({
                    "level": "error",
                    "message": f"{prefix} '{name}': missing required 'category' field"
                })
            elif category not in VALID_CATEGORIES:
                issues.append({
                    "level": "error",
                    "message": f"{prefix} '{name}': invalid category '{category}', must be one of {sorted(VALID_CATEGORIES)}"
                })

            # --- Check unit is reasonable for timing ---
            unit = param.get("unit")
            if unit is not None and not _is_valid_timing_unit(unit):
                issues.append({
                    "level": "warning",
                    "message": f"{prefix} '{name}': suspicious timing unit '{unit}', expected one of {sorted(VALID_TIMING_UNITS)}"
                })

            # --- Check min/typ/max monotonicity ---
            min_val = param.get("min")
            typ_val = param.get("typ")
            max_val = param.get("max")
            mono_result = _check_monotonicity(min_val, typ_val, max_val)
            if mono_result is False:
                issues.append({
                    "level": "error",
                    "message": f"{prefix} '{name}': min/typ/max not monotonic: {min_val}/{typ_val}/{max_val}"
                })

            # --- Check edge is from allowed enum ---
            edge = param.get("edge")
            if edge is not None and edge not in ("rising", "falling", "both"):
                issues.append({
                    "level": "warning",
                    "message": f"{prefix} '{name}': invalid edge '{edge}', must be one of ['rising', 'falling', 'both']"
                })

            # --- Check for duplicate parameters (same name + conditions) ---
            conditions = param.get("conditions") or ""
            dedup_key = (name.strip().lower(), conditions.strip().lower())
            if dedup_key in seen_params:
                issues.append({
                    "level": "warning",
                    "message": f"{prefix} '{name}': duplicate parameter (same name and conditions as timing_parameter[{seen_params[dedup_key]}])"
                })
            else:
                seen_params[dedup_key] = i

        return {
            "timing_validation_issues": issues,
            "timing_parameter_count": len(parameters),
        }
