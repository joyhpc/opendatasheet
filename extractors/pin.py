"""Pin extraction module.

Handles L1b pin extraction (standard IC and FPGA modes), pin validation,
and transform_pins_to_package_indexed.
"""

from extractors.base import BaseExtractor
from extractors.gemini_json import call_gemini_json_response


# ============================================
# Prompts
# ============================================

PIN_PROMPT_ID = "opendatasheet.pin.standard"
FPGA_PIN_PROMPT_ID = "opendatasheet.pin.fpga"
PIN_PROMPT_VERSION = "1.0.0"
FPGA_PIN_PROMPT_VERSION = "1.0.0"

PIN_EXTRACTION_PROMPT = """You are an expert electronic component datasheet parser specializing in pin definitions.
Analyze the provided datasheet page images and extract ALL pin information into a structured JSON format.

CRITICAL RULES:
1. Extract every unique logical pin (by function name, not physical number)
2. For each logical pin, map it to ALL packages shown in the datasheet
3. If a logical pin appears on multiple physical pins in one package (e.g., multiple GND pads), list ALL pin numbers in the array
4. Use ONLY the allowed enum values listed below \u2014 no variations, no abbreviations

ALLOWED VALUES:

direction (REQUIRED, exactly one of):
  INPUT          \u2014 signal flows into the device
  OUTPUT         \u2014 signal flows out of the device
  BIDIRECTIONAL  \u2014 signal flows both ways (e.g., I2C SDA, GPIO)
  POWER_IN       \u2014 power supply input (VCC, VDD, VIN)
  POWER_OUT      \u2014 regulated/buffered power output (VOUT, LDO output)
  PASSIVE        \u2014 passive connection (e.g., bypass cap pin, crystal, EP/thermal pad)
  NC             \u2014 no internal connection

signal_type (REQUIRED, exactly one of):
  DIGITAL  \u2014 digital logic signal
  ANALOG   \u2014 analog signal (feedback, sense, reference)
  POWER    \u2014 power rail or ground
  NONE     \u2014 no signal (NC pins, thermal pads with no electrical function)

unused_treatment (one of, or null if datasheet does not specify):
  FLOAT     \u2014 leave unconnected / floating is OK
  GND       \u2014 connect to ground when unused
  VCC       \u2014 connect to power supply when unused
  PULL_UP   \u2014 connect through pull-up resistor when unused
  PULL_DOWN \u2014 connect through pull-down resistor when unused
  CUSTOM    \u2014 special handling described in description
  null      \u2014 datasheet does not specify

OUTPUT FORMAT \u2014 output ONLY valid JSON, no markdown, no code fences:
{
  "logical_pins": [
    {
      "name": "VIN",
      "direction": "POWER_IN",
      "signal_type": "POWER",
      "description": "Power supply input",
      "packages": {
        "SOT-23-5": [1],
        "WDFN-6L": [3]
      },
      "unused_treatment": null
    }
  ]
}

IMPORTANT:
- Pin numbers should be integers when possible, strings only for special cases like "EP" (exposed pad)
- "packages" must be a dict where keys are package names and values are arrays of pin numbers
- If only one package is shown, still use the dict format
- Include ALL pins: power, ground, signal, NC, exposed pad
- For NC pins: direction="NC", signal_type="NONE"
- For GND pins: direction="POWER_IN", signal_type="POWER"
- For exposed/thermal pads: direction="PASSIVE", signal_type="POWER" (if connected to GND) or "NONE"
- description should be concise but informative (from the pin description table or diagram labels)
"""

FPGA_PIN_EXTRACTION_PROMPT = """You are an expert FPGA datasheet parser. These images show pages from an FPGA DC/AC switching characteristics datasheet.

FPGA datasheets do NOT have traditional pin definition tables like simple ICs. Instead, extract:

1. POWER SUPPLY PINS \u2014 all supply rails with their voltage ranges and descriptions
2. CONFIGURATION INTERFACE PINS \u2014 pins mentioned in configuration switching tables (CCLK, DONE, INIT_B, PROGRAM_B, M[2:0], D[31:00], etc.)
3. TRANSCEIVER PINS \u2014 RXP/RXN, TXP/TXN and reference clock pins
4. SYSTEM MONITOR PINS \u2014 VP/VN, VREFP/VREFN, DXP/DXN analog input pins

For each pin/pin group, extract:
- name: pin or bus name (e.g., "VCCINT", "D[31:00]", "RXP/RXN")
- direction: INPUT/OUTPUT/BIDIRECTIONAL/POWER_IN/PASSIVE
- signal_type: DIGITAL/ANALOG/POWER/NONE
- description: what this pin does, include voltage range if it's a power pin
- pin_group: one of "POWER_SUPPLY", "CONFIGURATION", "TRANSCEIVER", "SYSTEM_MONITOR", "CLOCK", "OTHER"
- packages: {} (leave empty \u2014 FPGA pin mapping is in separate pinout documents)
- unused_treatment: null (unless explicitly stated)

CRITICAL RULES:
- Do NOT invent pin numbers \u2014 FPGA pin numbers vary by package and are NOT in DC/AC datasheets
- Extract ALL power supply rails mentioned (VCCINT, VCCBRAM, VCCAUX, VCCO, VMGTAVCC, VMGTAVTT, etc.)
- For bus pins like D[31:00], keep the bus notation, don't expand individual bits
- Include voltage specifications in the description (e.g., "Internal supply voltage, 0.85V typical")

OUTPUT FORMAT \u2014 output ONLY valid JSON, no markdown, no code fences:
{
  "logical_pins": [
    {
      "name": "VCCINT",
      "direction": "POWER_IN",
      "signal_type": "POWER",
      "description": "Internal supply voltage, 0.825-0.876V typical",
      "pin_group": "POWER_SUPPLY",
      "packages": {},
      "unused_treatment": null
    }
  ]
}
"""

# Enum sets for validation
VALID_DIRECTIONS = {"INPUT", "OUTPUT", "BIDIRECTIONAL", "POWER_IN", "POWER_OUT", "PASSIVE", "NC"}
VALID_SIGNAL_TYPES = {"DIGITAL", "ANALOG", "POWER", "NONE"}
VALID_UNUSED_TREATMENTS = {"FLOAT", "GND", "VCC", "PULL_UP", "PULL_DOWN", "CUSTOM", None}
VALID_FPGA_PIN_GROUPS = {"POWER_SUPPLY", "CONFIGURATION", "TRANSCEIVER", "SYSTEM_MONITOR", "CLOCK", "OTHER"}


# ============================================
# Gemini API call helpers
# ============================================

def _call_gemini_pin_vision(
    client,
    model,
    images,
    prompt,
    *,
    prompt_id,
    prompt_version,
    max_retries=2,
):
    """Call Gemini Vision API for pin extraction with retry logic."""
    return call_gemini_json_response(
        client,
        model,
        images,
        prompt,
        max_retries=max_retries,
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        key_aliases={
            "logical_pins": ("pins", "pin_definitions", "logicalPins"),
        },
        required_keys=("logical_pins",),
    )


# ============================================
# Pin transform / validation helpers
# ============================================

def transform_pins_to_package_indexed(logical_pins: list) -> dict:
    """Transform logical_pins list into package-indexed structure.

    Input: logical_pins list (Gemini raw output)
    Output: {"packages": {"pkg_name": {"pin_number_str": {name, direction, signal_type, description, unused_treatment}}}}

    Conflict handling: when the same physical pin is claimed by multiple logical pins,
    keep the first and append a note to description.
    """
    packages = {}

    for lp in logical_pins:
        name = lp.get("name", "")
        direction = lp.get("direction", "")
        signal_type = lp.get("signal_type", "")
        description = lp.get("description", "")
        unused_treatment = lp.get("unused_treatment")
        pkg_map = lp.get("packages", {})

        if not isinstance(pkg_map, dict):
            continue

        for pkg_name, pin_nums in pkg_map.items():
            if pkg_name not in packages:
                packages[pkg_name] = {}
            if not isinstance(pin_nums, list):
                continue
            for pn in pin_nums:
                pn_str = str(pn)
                entry = {
                    "name": name,
                    "direction": direction,
                    "signal_type": signal_type,
                    "description": description,
                    "unused_treatment": unused_treatment,
                }
                if pn_str in packages[pkg_name]:
                    existing = packages[pkg_name][pn_str]
                    existing["description"] += f" (also: {name} \u2014 {description})"
                else:
                    packages[pkg_name][pn_str] = entry

    return {"packages": packages}


def validate_pins(pin_data: dict) -> list[dict]:
    """Validate standard IC pin extraction results, return issues list."""
    issues = []
    pins = pin_data.get("logical_pins", [])

    if not pins:
        issues.append({"level": "error", "message": "No logical_pins found"})
        return issues

    seen_names = set()
    package_pin_map = {}

    for i, pin in enumerate(pins):
        prefix = f"pin[{i}]"

        name = pin.get("name", "")
        if not name or not str(name).strip():
            issues.append({"level": "error", "message": f"{prefix}: empty name"})
            continue

        name = str(name).strip()

        if name in seen_names:
            issues.append({"level": "warning", "message": f"{prefix}: duplicate pin name '{name}'"})
        seen_names.add(name)

        direction = pin.get("direction", "")
        if direction not in VALID_DIRECTIONS:
            issues.append({"level": "error", "message": f"{prefix} '{name}': invalid direction '{direction}', must be one of {sorted(VALID_DIRECTIONS)}"})

        signal_type = pin.get("signal_type", "")
        if signal_type not in VALID_SIGNAL_TYPES:
            issues.append({"level": "error", "message": f"{prefix} '{name}': invalid signal_type '{signal_type}', must be one of {sorted(VALID_SIGNAL_TYPES)}"})

        unused = pin.get("unused_treatment")
        if unused not in VALID_UNUSED_TREATMENTS:
            issues.append({"level": "error", "message": f"{prefix} '{name}': invalid unused_treatment '{unused}', must be one of {sorted(str(v) for v in VALID_UNUSED_TREATMENTS)}"})

        packages = pin.get("packages")
        if not isinstance(packages, dict):
            issues.append({"level": "error", "message": f"{prefix} '{name}': packages must be a dict, got {type(packages).__name__}"})
        elif not packages:
            issues.append({"level": "error", "message": f"{prefix} '{name}': packages dict is empty"})
        else:
            for pkg_name, pin_nums in packages.items():
                if not isinstance(pin_nums, list):
                    issues.append({"level": "error", "message": f"{prefix} '{name}': packages['{pkg_name}'] must be a list, got {type(pin_nums).__name__}"})
                else:
                    if pkg_name not in package_pin_map:
                        package_pin_map[pkg_name] = {}
                    for pn in pin_nums:
                        pn_key = str(pn)
                        if pn_key not in package_pin_map[pkg_name]:
                            package_pin_map[pkg_name][pn_key] = []
                        package_pin_map[pkg_name][pn_key].append(name)

    for pkg_name, pn_map in package_pin_map.items():
        for pn, names in pn_map.items():
            if len(names) > 1:
                issues.append({"level": "warning", "message": f"package '{pkg_name}' pin {pn} claimed by multiple logical pins: {names}"})

    return issues


def validate_fpga_pins(pin_data: dict) -> list[dict]:
    """Validate FPGA pin extraction results. Packages are expected to be empty."""
    issues = []
    pins = pin_data.get("logical_pins", [])

    if not pins:
        issues.append({"level": "warning", "message": "No logical_pins found (may be normal for some FPGA datasheets)"})
        return issues

    seen_names = set()
    for i, pin in enumerate(pins):
        prefix = f"pin[{i}]"
        name = pin.get("name", "")
        if not name or not str(name).strip():
            issues.append({"level": "error", "message": f"{prefix}: empty name"})
            continue
        name = str(name).strip()

        if name in seen_names:
            issues.append({"level": "warning", "message": f"{prefix}: duplicate pin name '{name}'"})
        seen_names.add(name)

        direction = pin.get("direction", "")
        if direction not in VALID_DIRECTIONS:
            issues.append({"level": "error", "message": f"{prefix} '{name}': invalid direction '{direction}'"})

        signal_type = pin.get("signal_type", "")
        if signal_type not in VALID_SIGNAL_TYPES:
            issues.append({"level": "error", "message": f"{prefix} '{name}': invalid signal_type '{signal_type}'"})

        pin_group = pin.get("pin_group", "")
        if pin_group not in VALID_FPGA_PIN_GROUPS:
            issues.append({"level": "warning", "message": f"{prefix} '{name}': unknown pin_group '{pin_group}'"})

        packages = pin.get("packages", {})
        if packages and isinstance(packages, dict) and any(v for v in packages.values()):
            issues.append({"level": "warning", "message": f"{prefix} '{name}': unexpected non-empty packages (FPGA DC/AC datasheets don't have pin mapping)"})

    found_groups = set(p.get("pin_group", "") for p in pins)
    if "POWER_SUPPLY" not in found_groups:
        issues.append({"level": "warning", "message": "No POWER_SUPPLY pins found \u2014 expected for FPGA datasheets"})
    if "CONFIGURATION" not in found_groups:
        issues.append({"level": "warning", "message": "No CONFIGURATION pins found \u2014 expected for FPGA datasheets"})

    return issues


class PinExtractor(BaseExtractor):
    """Extracts pin definitions from datasheet pages.

    Supports both standard IC mode (pin tables/diagrams) and FPGA mode
    (power supply groups, configuration pins, transceivers).
    """

    DOMAIN_NAME = "pin"

    def select_pages(self) -> list[int]:
        """Select pin + cover pages (or electrical + supply + cover for FPGA)."""
        cover_pages = [p.page_num for p in self.page_classification if p.category == "cover"]

        if self.is_fpga:
            electrical_pages = [p.page_num for p in self.page_classification if p.category == "electrical"]
            fpga_supply_pages = [p.page_num for p in self.page_classification if p.category == "fpga_supply"]
            return sorted(set(electrical_pages + fpga_supply_pages + cover_pages))
        else:
            pin_pages = [p.page_num for p in self.page_classification if p.category == "pin"]
            return sorted(set(pin_pages + cover_pages))

    def extract(self, rendered_images) -> dict:
        """L1b: Use Gemini Vision to extract pin definitions."""
        if isinstance(rendered_images, dict):
            images = list(rendered_images.values())
        else:
            images = rendered_images

        if not images:
            return {"error": "No images to extract from"}

        if self.is_fpga:
            prompt = FPGA_PIN_EXTRACTION_PROMPT
            prompt_id = FPGA_PIN_PROMPT_ID
            prompt_version = FPGA_PIN_PROMPT_VERSION
        else:
            prompt = PIN_EXTRACTION_PROMPT
            prompt_id = PIN_PROMPT_ID
            prompt_version = PIN_PROMPT_VERSION

        return _call_gemini_pin_vision(
            self.client,
            self.model,
            images,
            prompt,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
        )

    def validate(self, extraction_result: dict) -> dict:
        """Validate pin extraction results."""
        if "error" in extraction_result:
            return {"pin_validation_issues": []}

        if self.is_fpga:
            issues = validate_fpga_pins(extraction_result)
        else:
            issues = validate_pins(extraction_result)

        return {"pin_validation_issues": issues}
