"""Design guide extraction module.

Extracts structured hardware design rules from manufacturer design guide
documents (e.g., FPGA schematic design guides like Gowin UG984).

Unlike standard datasheet extractors that work on a single datasheet PDF,
this extractor targets dedicated design guide PDFs and uses Vision+Text
hybrid extraction to capture:
- Power domain maps and sequencing constraints
- Pin connection rules (pull-up/down, must-connect, no-float)
- Decoupling and filtering requirements
- Clock design rules (AC coupling, termination)
- Configuration mode support tables
- IO standard rules (LVDS, SSTL, HSTL)
- Rail merge guidelines
"""
import re

import fitz

from extractors.base import BaseExtractor
from extractors.gemini_json import call_gemini_json_response


# ============================================
# Page classification patterns for design guides
# ============================================

DESIGN_GUIDE_SECTION_PATTERNS = {
    "power": [
        re.compile(r'(?i)电源设计|power\s+supply\s+design|power\s+rail|power\s+domain'),
        re.compile(r'(?i)上电顺序|power[- ]up\s+sequence|power\s+sequenc'),
        re.compile(r'(?i)纹波|ripple|decoupl|bypass\s+cap'),
        re.compile(r'(?i)隔离滤波|ferrite\s+bead|filter'),
        re.compile(r'(?i)电源合并|rail\s+merg|power\s+consolidat'),
        re.compile(r'(?i)斜率|slew\s+rate|ramp\s+rate'),
    ],
    "pin_config": [
        re.compile(r'(?i)配置管脚|configuration\s+pin|config\s+pin'),
        re.compile(r'(?i)RECONFIG|READY|DONE|CFGBVS|PUDC_B|MODE\['),
        re.compile(r'(?i)上拉|下拉|pull[- ]?up|pull[- ]?down|must\s+not\s+float'),
        re.compile(r'(?i)不允许悬空|must\s+be\s+connected|do\s+not\s+leave\s+float'),
    ],
    "configuration": [
        re.compile(r'(?i)配置模式|configuration\s+mode|programming\s+mode'),
        re.compile(r'(?i)JTAG|MSPI|SSPI|Slave\s+Serial|Slave\s+CPU'),
        re.compile(r'(?i)比特流|bitstream|program\s+flash'),
    ],
    "clock": [
        re.compile(r'(?i)时钟设计|clock\s+design|clock\s+resource'),
        re.compile(r'(?i)GCLK|HCLK|PLL|DQS'),
        re.compile(r'(?i)晶振|oscillat|crystal|reference\s+clock'),
        re.compile(r'(?i)SerDes.*时钟|SerDes.*clock|refclk'),
    ],
    "io_standard": [
        re.compile(r'(?i)差分管脚|differential\s+pair|LVDS|SSTL|HSTL'),
        re.compile(r'(?i)匹配电阻|termination|impedance\s+match'),
        re.compile(r'(?i)IO\s+standard|I/O\s+standard|VREF'),
    ],
    "layout": [
        re.compile(r'(?i)PCB\s+layout|布局|layout\s+guideline'),
        re.compile(r'(?i)thermal\s+via|散热|ground\s+plane'),
    ],
}

# Pages to exclude from design guide extraction
DESIGN_GUIDE_EXCLUDE_PATTERNS = [
    re.compile(r'(?i)目录|table\s+of\s+contents|revision\s+history'),
    re.compile(r'(?i)修订历史|change\s+log|document\s+revision'),
    re.compile(r'(?i)copyright|disclaimer|legal\s+notice'),
]


# ============================================
# Vision extraction prompt
# ============================================

DESIGN_GUIDE_EXTRACTION_PROMPT = """You are an expert FPGA/IC hardware design guide parser.
Analyze the provided design guide page images and extract ALL hardware design rules and constraints into structured JSON.

These pages come from a manufacturer's hardware design guide (NOT a standard datasheet).
Focus on extracting ACTIONABLE design rules that hardware engineers need to follow.

CRITICAL RULES:
1. Extract power domain classification with rail names and descriptions
2. Extract power-up sequencing rules (which rail before which)
3. Extract power ramp rate / slew rate constraints for each rail
4. Extract pin connection rules (pull-up/down requirements, must-not-float, tie-high/low)
5. Extract decoupling/filtering requirements (ripple limits, ferrite bead, cap values)
6. Extract clock design rules (AC coupling, input preferences)
7. Extract configuration mode support (which modes supported per package)
8. Extract IO standard rules (termination, differential matching)
9. Extract rail merge guidelines (which rails can be combined)
10. Preserve exact values (resistance, capacitance, voltage, frequency)
11. Output ONLY valid JSON, no markdown, no code fences

SEVERITY LEVELS:
- "ERROR": Violation will damage the chip or prevent operation (must fix before tapeout/fabrication)
- "WARNING": Important recommendation, should follow but won't cause immediate failure
- "INFO": Optional optimization or design tip

OUTPUT JSON SCHEMA:
{
  "source_document": {
    "title": "string or null",
    "document_id": "string or null (e.g. UG984)",
    "version": "string or null",
    "device_family": "string or null (e.g. GW5AT)"
  },
  "power_domain_map": [
    {
      "group": "string (e.g. FPGA, SerDes, MIPI)",
      "rail_name": "string (e.g. VCC, VCCIO)",
      "description": "string or null",
      "nominal_voltage": null or number,
      "ripple_max_pct": null or number
    }
  ],
  "power_sequencing_rules": [
    {
      "rule": "string (human-readable rule)",
      "rail_before": "string or null",
      "rail_after": "string or null",
      "severity": "ERROR|WARNING|INFO"
    }
  ],
  "power_ramp_constraints": [
    {
      "rail": "string",
      "slew_rate_min": null or number,
      "slew_rate_max": null or number,
      "unit": "mV/us"
    }
  ],
  "rail_merge_guidelines": [
    {
      "rails": ["string", "string"],
      "can_merge": true/false,
      "conditions": "string or null",
      "recommendation": "string or null (e.g. use LDO, use ferrite bead)",
      "severity": "ERROR|WARNING|INFO"
    }
  ],
  "pin_connection_rules": [
    {
      "pin": "string (exact pin name)",
      "rule": "string (what to do with this pin)",
      "connection_type": "must_connect|must_not_float|pull_up|pull_down|tie_high|tie_low|external_component|conditional|other",
      "external_component": "string or null (e.g. 4.7K pull-up to 3.3V)",
      "condition": "string or null",
      "severity": "ERROR|WARNING|INFO"
    }
  ],
  "decoupling_requirements": [
    {
      "rail": "string",
      "ripple_max_pct": null or number,
      "filter_type": "string or null (e.g. ferrite bead + ceramic cap)",
      "capacitor_tolerance": "string or null",
      "notes": "string or null",
      "severity": "ERROR|WARNING|INFO"
    }
  ],
  "clock_design_rules": [
    {
      "signal": "string (clock signal name or group)",
      "requirement": "string",
      "external_component": "string or null",
      "notes": "string or null",
      "severity": "ERROR|WARNING|INFO"
    }
  ],
  "configuration_mode_support": [
    {
      "device": "string or null",
      "package": "string or null",
      "mode": "string (e.g. JTAG, MSPI, SSPI)",
      "supported": true/false,
      "max_clock_freq": "string or null",
      "signals": ["string"],
      "notes": "string or null"
    }
  ],
  "io_standard_rules": [
    {
      "standard": "string (e.g. LVDS, SSTL, HSTL)",
      "requirement": "string",
      "termination": "string or null",
      "applies_to": "string or null (which banks/partitions)",
      "severity": "ERROR|WARNING|INFO"
    }
  ],
  "design_guideline_text": [
    {
      "category": "power|clock|io|config|layout|other",
      "guideline": "string"
    }
  ]
}

IMPORTANT:
- Extract ALL rules visible in the images, even if they seem obvious
- For Chinese-language documents, translate rule descriptions to English but keep pin/signal names as-is
- Include the original language context in the rule where helpful
- If a rule mentions specific component values (4.7K, 0.1uF, etc.), include them exactly
- Pin names must match exactly as shown in the document (e.g., RECONFIG_N, not reconfig_n)
"""


# ============================================
# Text-based extraction helpers
# ============================================

# Regex patterns for extracting structured data from text
RAMP_RATE_RE = re.compile(
    r'(\w+)\s*(?:上升斜率|ramp\s+rate|slew\s+rate)\s*[:：]\s*'
    r'([\d.]+)\s*[~～\-to]+\s*([\d.]+)\s*(mV/us|V/ms|mV/µs)',
    re.IGNORECASE
)

RIPPLE_RE = re.compile(
    r'(\w+)\s*[:：]\s*[≤<]\s*([\d.]+)\s*%',
    re.IGNORECASE
)

PULL_UP_RE = re.compile(
    r'(\w+)\s*.*?(?:需要|需|requires?)\s*(?:外部\s*)?'
    r'([\d.]+[kKΩ]?)\s*(?:上拉|pull[- ]?up)\s*(?:到|to)\s*([\d.]+V)',
    re.IGNORECASE
)

NOT_FLOAT_RE = re.compile(
    r'(\w+)\s*.*?(?:不允许悬空|不能悬空|must\s+not\s+float|do\s+not\s+leave\s+float)',
    re.IGNORECASE
)

SEQUENCING_RE = re.compile(
    r'(?:推荐|建议|requires?|must)\s*(\w+)\s*(?:在|before)\s*(\w+)\s*(?:之前|上电|power[- ]up)',
    re.IGNORECASE
)


def _extract_text_rules(doc):
    """Extract design rules from PDF text using regex patterns.

    This provides a text-based extraction layer that works even without
    Vision API, and can be used to cross-validate Vision results.

    Returns a dict with partial design guide data.
    """
    all_text = ""
    for i in range(len(doc)):
        all_text += doc[i].get_text() + "\n"

    result = {
        "power_ramp_constraints": [],
        "decoupling_requirements": [],
        "pin_connection_rules": [],
        "power_sequencing_rules": [],
    }

    # Extract ramp rate constraints
    for m in RAMP_RATE_RE.finditer(all_text):
        result["power_ramp_constraints"].append({
            "rail": m.group(1),
            "slew_rate_min": float(m.group(2)),
            "slew_rate_max": float(m.group(3)),
            "unit": m.group(4),
        })

    # Extract ripple requirements
    for m in RIPPLE_RE.finditer(all_text):
        rail = m.group(1).strip()
        # Filter out non-rail matches
        if any(rail.upper().startswith(p) for p in ["VCC", "VDD", "VCCO"]):
            result["decoupling_requirements"].append({
                "rail": rail,
                "ripple_max_pct": float(m.group(2)),
                "severity": "WARNING",
            })

    # Extract pull-up requirements
    for m in PULL_UP_RE.finditer(all_text):
        result["pin_connection_rules"].append({
            "pin": m.group(1),
            "rule": f"Requires {m.group(2)} pull-up to {m.group(3)}",
            "connection_type": "pull_up",
            "external_component": f"{m.group(2)} pull-up to {m.group(3)}",
            "severity": "ERROR",
        })

    # Extract must-not-float pins
    for m in NOT_FLOAT_RE.finditer(all_text):
        pin = m.group(1).strip()
        if len(pin) <= 20:  # Sanity check on pin name length
            result["pin_connection_rules"].append({
                "pin": pin,
                "rule": "Must not be left floating",
                "connection_type": "must_not_float",
                "severity": "ERROR",
            })

    # Extract sequencing rules
    for m in SEQUENCING_RE.finditer(all_text):
        result["power_sequencing_rules"].append({
            "rule": f"{m.group(1)} must power up before {m.group(2)}",
            "rail_before": m.group(1),
            "rail_after": m.group(2),
            "severity": "ERROR",
        })

    return result


def _classify_design_guide_pages(doc):
    """Classify design guide pages into sections.

    Returns list of (page_num, section_type, text) tuples.
    """
    classified = []
    for i in range(len(doc)):
        text = doc[i].get_text()

        # Skip excluded pages
        if any(pat.search(text) for pat in DESIGN_GUIDE_EXCLUDE_PATTERNS):
            continue

        # Skip very short pages (mostly images without text)
        if len(text.strip()) < 50:
            continue

        # Classify by section
        section = "other"
        max_hits = 0
        for sec_name, patterns in DESIGN_GUIDE_SECTION_PATTERNS.items():
            hits = sum(1 for pat in patterns if pat.search(text))
            if hits > max_hits:
                max_hits = hits
                section = sec_name

        if max_hits > 0:
            classified.append((i, section, text))

    return classified


# ============================================
# Gemini Vision call helper
# ============================================

def _call_gemini_vision(client, model, images, prompt, max_retries=2):
    """Call Gemini Vision API with retry logic. Returns parsed dict or error dict."""
    return call_gemini_json_response(
        client,
        model,
        images,
        prompt,
        max_retries=max_retries,
    )


# ============================================
# Validation helpers
# ============================================

VALID_SEVERITIES = {"ERROR", "WARNING", "INFO"}
VALID_CONNECTION_TYPES = {
    "must_connect", "must_not_float", "pull_up", "pull_down",
    "tie_high", "tie_low", "external_component", "conditional", "other"
}
VALID_GUIDELINE_CATEGORIES = {"power", "clock", "io", "config", "layout", "other"}


def _validate_severity(items, field_name):
    """Check that severity fields have valid values."""
    issues = []
    for i, item in enumerate(items):
        sev = item.get("severity")
        if sev is not None and sev not in VALID_SEVERITIES:
            issues.append({
                "level": "error",
                "message": f"{field_name}[{i}]: invalid severity '{sev}', must be ERROR/WARNING/INFO"
            })
    return issues


def _check_contradictory_sequencing(rules):
    """Check for contradictory power sequencing rules."""
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
                "message": f"Contradictory sequencing: '{before}' before '{after}' AND '{after}' before '{before}'"
            })
        pairs.add(pair)
    return issues


def _check_ramp_rate_sanity(constraints):
    """Check that ramp rate values are physically reasonable."""
    issues = []
    for i, c in enumerate(constraints):
        rail = c.get("rail", "?")
        sr_min = c.get("slew_rate_min")
        sr_max = c.get("slew_rate_max")
        if sr_min is not None and sr_max is not None:
            if sr_min > sr_max:
                issues.append({
                    "level": "error",
                    "message": f"power_ramp_constraints[{i}] '{rail}': slew_rate_min ({sr_min}) > slew_rate_max ({sr_max})"
                })
            if sr_min < 0:
                issues.append({
                    "level": "error",
                    "message": f"power_ramp_constraints[{i}] '{rail}': negative slew_rate_min ({sr_min})"
                })
    return issues


# ============================================
# Merge helper
# ============================================

def _merge_text_and_vision(text_result, vision_result):
    """Merge text-based extraction with Vision extraction.

    Vision results take priority. Text results fill in gaps and provide
    cross-validation data.
    """
    merged = dict(vision_result)

    for key in ["power_ramp_constraints", "decoupling_requirements",
                 "pin_connection_rules", "power_sequencing_rules"]:
        vision_items = vision_result.get(key, [])
        text_items = text_result.get(key, [])

        if not vision_items and text_items:
            # Vision missed this entirely, use text results
            merged[key] = text_items
        elif vision_items and text_items:
            # Both have results — add text items that aren't covered by vision
            vision_keys = set()
            for item in vision_items:
                # Build a dedup key from the most identifying fields
                if key == "pin_connection_rules":
                    vision_keys.add(item.get("pin", "").upper())
                elif key == "power_ramp_constraints":
                    vision_keys.add(item.get("rail", "").upper())
                elif key == "decoupling_requirements":
                    vision_keys.add(item.get("rail", "").upper())
                elif key == "power_sequencing_rules":
                    vision_keys.add((
                        (item.get("rail_before") or "").upper(),
                        (item.get("rail_after") or "").upper()
                    ))

            for item in text_items:
                if key == "pin_connection_rules":
                    dedup_key = item.get("pin", "").upper()
                elif key == "power_ramp_constraints":
                    dedup_key = item.get("rail", "").upper()
                elif key == "decoupling_requirements":
                    dedup_key = item.get("rail", "").upper()
                elif key == "power_sequencing_rules":
                    dedup_key = (
                        (item.get("rail_before") or "").upper(),
                        (item.get("rail_after") or "").upper()
                    )
                else:
                    dedup_key = None

                if dedup_key not in vision_keys:
                    merged[key].append(item)

    return merged


# ============================================
# Main extractor class
# ============================================

class DesignGuideExtractor(BaseExtractor):
    """Extracts hardware design rules from design guide documents.

    This extractor uses a hybrid Vision + Text approach:
    1. Text-based regex extraction for structured data (ramp rates, ripple, pull-up values)
    2. Vision API for complex tables, diagrams, and context-dependent rules
    3. Merge and cross-validate both results

    Unlike DesignContextExtractor (which extracts application hints from
    datasheets), this extracts mandatory design rules from standalone
    design guide documents.
    """

    DOMAIN_NAME = "design_guide"

    def select_pages(self) -> list[int]:
        """Select pages relevant to hardware design rules.

        Scans all pages for design guide section patterns and returns
        pages that contain power, pin config, clock, IO, or layout rules.
        """
        selected = set()

        for page_info in self.page_classification:
            text = page_info.text_preview.lower() if page_info.text_preview else ""

            # Check if this page matches any design guide section
            for sec_name, patterns in DESIGN_GUIDE_SECTION_PATTERNS.items():
                for pat in patterns:
                    if pat.search(text) or pat.search(page_info.text_preview or ""):
                        selected.add(page_info.page_num)
                        break

            # Also include application pages that might contain design rules
            if page_info.category == "application":
                selected.add(page_info.page_num)

        return sorted(selected)

    def extract(self, rendered_images) -> dict:
        """Extract design guide rules using Vision + Text hybrid approach.

        Args:
            rendered_images: Dict mapping page_num -> PNG bytes, or list of PNG bytes.

        Returns:
            Dict matching the design_guide.schema.json structure.
        """
        empty_result = {
            "source_document": {},
            "power_domain_map": [],
            "power_sequencing_rules": [],
            "power_ramp_constraints": [],
            "rail_merge_guidelines": [],
            "pin_connection_rules": [],
            "decoupling_requirements": [],
            "clock_design_rules": [],
            "configuration_mode_support": [],
            "io_standard_rules": [],
            "design_guideline_text": [],
        }

        # Step 1: Text-based extraction
        try:
            doc = fitz.open(self.pdf_path)
            text_result = _extract_text_rules(doc)
            doc.close()
        except Exception:
            text_result = {}

        # Step 2: Vision extraction
        if isinstance(rendered_images, dict):
            images = list(rendered_images.values())
        else:
            images = rendered_images

        if not images:
            # No images available — return text-only results
            for key, val in text_result.items():
                if val:
                    empty_result[key] = val
            return empty_result

        vision_result = _call_gemini_vision(
            self.client, self.model, images, DESIGN_GUIDE_EXTRACTION_PROMPT
        )

        if "error" in vision_result:
            # Vision failed — fall back to text-only results
            for key, val in text_result.items():
                if val:
                    empty_result[key] = val
            empty_result["_vision_error"] = vision_result["error"]
            return empty_result

        # Step 3: Merge text + vision results
        merged = _merge_text_and_vision(text_result, vision_result)

        # Ensure all expected keys exist
        for key in empty_result:
            if key not in merged:
                merged[key] = empty_result[key]

        return merged

    def validate(self, extraction_result: dict) -> dict:
        """Validate extracted design guide data.

        Checks:
        - Severity values are valid enums
        - No contradictory sequencing rules
        - Ramp rate values are physically reasonable
        - Pin connection types are from the valid enum
        - Required fields are present
        """
        issues = []

        if "error" in extraction_result:
            return {
                "design_guide_validation_issues": issues,
                "power_domain_count": 0,
                "sequencing_rule_count": 0,
                "pin_rule_count": 0,
                "clock_rule_count": 0,
            }

        # Validate severity on all rule arrays
        for field in ["power_sequencing_rules", "pin_connection_rules",
                       "decoupling_requirements", "clock_design_rules",
                       "rail_merge_guidelines", "io_standard_rules"]:
            items = extraction_result.get(field, [])
            issues.extend(_validate_severity(items, field))

        # Validate sequencing rules
        seq_rules = extraction_result.get("power_sequencing_rules", [])
        issues.extend(_check_contradictory_sequencing(seq_rules))

        # Validate ramp constraints
        ramp = extraction_result.get("power_ramp_constraints", [])
        issues.extend(_check_ramp_rate_sanity(ramp))

        # Validate pin connection types
        pin_rules = extraction_result.get("pin_connection_rules", [])
        for i, rule in enumerate(pin_rules):
            ct = rule.get("connection_type")
            if ct is not None and ct not in VALID_CONNECTION_TYPES:
                issues.append({
                    "level": "warning",
                    "message": f"pin_connection_rules[{i}] '{rule.get('pin', '?')}': "
                               f"unknown connection_type '{ct}'"
                })

        # Validate guideline categories
        guidelines = extraction_result.get("design_guideline_text", [])
        for i, g in enumerate(guidelines):
            cat = g.get("category")
            if cat is not None and cat not in VALID_GUIDELINE_CATEGORIES:
                issues.append({
                    "level": "info",
                    "message": f"design_guideline_text[{i}]: unknown category '{cat}'"
                })

        # Completeness check
        power_domains = extraction_result.get("power_domain_map", [])
        if not power_domains:
            issues.append({
                "level": "info",
                "message": "No power domain map extracted"
            })

        if not pin_rules:
            issues.append({
                "level": "info",
                "message": "No pin connection rules extracted"
            })

        return {
            "design_guide_validation_issues": issues,
            "power_domain_count": len(power_domains),
            "sequencing_rule_count": len(seq_rules),
            "pin_rule_count": len(pin_rules),
            "ramp_constraint_count": len(ramp),
            "clock_rule_count": len(extraction_result.get("clock_design_rules", [])),
            "config_mode_count": len(extraction_result.get("configuration_mode_support", [])),
            "io_standard_rule_count": len(extraction_result.get("io_standard_rules", [])),
            "merge_guideline_count": len(extraction_result.get("rail_merge_guidelines", [])),
            "guideline_text_count": len(guidelines),
        }
