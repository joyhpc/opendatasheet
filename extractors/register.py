"""Register map extraction module.

Handles extraction of register definitions from datasheets that contain
I2C/SPI/memory-mapped register maps. Identifies register description pages
and extracts address, bit fields, access modes, and reset values.
"""
import json
import re
import time

from google.genai import types

from extractors.base import BaseExtractor


# ============================================
# Prompts
# ============================================

REGISTER_EXTRACTION_PROMPT = """You are an expert electronic component datasheet parser specializing in register maps.
Analyze the provided datasheet page images and extract ALL register definitions into a structured JSON format.

CRITICAL RULES:
1. Extract every register shown in the register map or register description sections
2. For each register, extract its full bit field breakdown if available
3. Use hex notation for addresses and reset values (e.g., "0x00", "0xFF")
4. If a value is not specified or not visible, use null
5. Output ONLY valid JSON, no markdown, no code fences

REGISTER FIELDS TO EXTRACT:
- address: Hex address string (e.g., "0x00", "0x1A"). Include the "0x" prefix.
- name: Register name exactly as shown (e.g., "CONFIG", "STATUS", "CONTROL_REG")
- description: Brief description of the register's purpose
- size_bits: Register width in bits (8, 16, or 32). Default to 8 if not stated.
- access: Overall register access mode. Use exactly one of: "R", "W", "RW", "RO", "WO", "W1C"
  - "R" or "RO" = read-only
  - "W" or "WO" = write-only
  - "RW" = read/write
  - "W1C" = write-1-to-clear
- reset_value: Default/reset value as hex string (e.g., "0x00"), or null if not specified

BIT FIELD DETAILS (for each field within a register):
- bits: Bit position as string. Use "7:4" for multi-bit fields, "3" for single-bit fields.
  The MSB should come first (e.g., "15:8", not "8:15").
- name: Field name exactly as shown (e.g., "EN", "MODE", "RESERVED")
- description: What this field controls or indicates
- access: Field-level access mode ("R", "W", "RW", "RO", "WO", "W1C", or null if same as register)
- reset_value: Field reset value as string (e.g., "0", "1", "0b00"), or null
- enum_values: Optional mapping of field values to descriptions.
  Example: {"0": "Disabled", "1": "Enabled"} or {"00": "Mode A", "01": "Mode B", "10": "Mode C"}
  Use null if no enumeration is defined.

SUMMARY FIELDS:
- total_registers: Integer count of all registers extracted
- address_range: String showing the address range, e.g., "0x00-0x0F"
- bus_type: Communication bus type. Use exactly one of: "I2C", "SPI", "memory_mapped", "AHB", "APB", "AXI", "PCIe", "other"
  Infer from context: if the datasheet mentions I2C slave address, use "I2C". If it mentions SPI commands, use "SPI".

OUTPUT JSON SCHEMA:
{
  "registers": [
    {
      "address": "0x00",
      "name": "CONFIG",
      "description": "Configuration register",
      "size_bits": 16,
      "access": "RW",
      "reset_value": "0x0000",
      "fields": [
        {
          "bits": "15:12",
          "name": "OS",
          "description": "Operational status / single-shot conversion start",
          "access": "RW",
          "reset_value": "0",
          "enum_values": {"0": "No effect", "1": "Start conversion"}
        },
        {
          "bits": "11:9",
          "name": "MUX",
          "description": "Input multiplexer configuration",
          "access": "RW",
          "reset_value": "000",
          "enum_values": null
        }
      ]
    }
  ],
  "register_map_summary": {
    "total_registers": 4,
    "address_range": "0x00-0x03",
    "bus_type": "I2C"
  }
}

IMPORTANT:
- Extract ALL registers visible in the images, not just the first few
- Include reserved/unused fields — mark them with name "RESERVED" or "RSVD"
- If a register has no bit field breakdown shown, set "fields" to an empty array []
- If the same register appears at multiple addresses (aliased), create separate entries
- For registers wider than 8 bits, ensure field bit ranges cover the full width
- Preserve the exact register and field names from the datasheet (do not rename)
"""


# Patterns used to identify pages that contain register content
REGISTER_PAGE_PATTERNS = [
    re.compile(r'(?i)register\s+map'),
    re.compile(r'(?i)register\s+description'),
    re.compile(r'(?i)register\s+address'),
    re.compile(r'(?i)register\s+summary'),
    re.compile(r'(?i)register\s+table'),
    re.compile(r'(?i)register\s+definitions?'),
    re.compile(r'(?i)register\s+details?'),
    re.compile(r'(?i)register\s+overview'),
    re.compile(r'(?i)register\s+set'),
    re.compile(r'(?i)register\s+listing'),
    re.compile(r'(?i)bit\s+field\s+description'),
    re.compile(r'(?i)address\s+offset'),
    re.compile(r'(?i)reset\s+value'),
    re.compile(r'(?i)default\s+value.*0x'),
    re.compile(r'(?i)\bR/?W\b.*\bbit\b'),
    re.compile(r'(?i)\b0x[0-9A-Fa-f]{2,4}\b.*\b(read|write|R/?W|RO|WO)\b'),
    re.compile(r'(?i)(configuration|control|status|command)\s+register'),
    re.compile(r'(?i)pointer\s+register'),
    re.compile(r'(?i)memory\s+map'),
]

# Allowed access mode values (matches schema enum)
VALID_ACCESS_MODES = {"R", "W", "RW", "RO", "WO", "W1C"}

# Valid bus types (matches schema enum)
VALID_BUS_TYPES = {"I2C", "SPI", "memory_mapped", "AHB", "APB", "AXI", "PCIe", "other"}


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
                raw = raw[start:end+1]
            result = json.loads(raw.strip())
            if isinstance(result, list):
                result = result[0] if result else {"error": "Empty list"}
            if not isinstance(result, dict):
                return {"error": f"Unexpected type: {type(result).__name__}"}
            # Normalize key names — the model might use alternate keys
            if "registers" not in result:
                for key in ["register_map", "registerMap", "register_list"]:
                    if key in result:
                        result["registers"] = result.pop(key)
                        break
            if "register_map_summary" not in result:
                for key in ["summary", "registerMapSummary", "map_summary"]:
                    if key in result:
                        result["register_map_summary"] = result.pop(key)
                        break
            return result
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                time.sleep(3)
                continue
            return {"error": f"JSON parse failed: {str(e)}", "raw": raw[:500] if 'raw' in dir() else ""}
        except Exception as e:
            if attempt < max_retries and ("503" in str(e) or "429" in str(e) or "504" in str(e) or "timeout" in str(e).lower() or "ReadTimeout" in str(type(e).__name__) or "ConnectTimeout" in str(type(e).__name__)):
                time.sleep(10)
                continue
            return {"error": str(e)}


# ============================================
# Validation helpers
# ============================================

def _is_valid_hex_string(s):
    """Check if a string is a valid hex value (with or without 0x prefix)."""
    if not isinstance(s, str) or not s.strip():
        return False
    s = s.strip()
    if s.lower().startswith("0x"):
        s = s[2:]
    if not s:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in s)


def _parse_bit_range(bits_str):
    """Parse a bit range string like '7:4' or '3' into (high_bit, low_bit).

    Returns (high, low) tuple, or None if parsing fails.
    """
    if not isinstance(bits_str, str):
        return None
    bits_str = bits_str.strip()
    if ":" in bits_str:
        parts = bits_str.split(":")
        if len(parts) != 2:
            return None
        try:
            high = int(parts[0].strip())
            low = int(parts[1].strip())
            return (high, low)
        except ValueError:
            return None
    else:
        try:
            bit = int(bits_str)
            return (bit, bit)
        except ValueError:
            return None


def _check_bit_field_overlap(fields, register_size):
    """Check for overlapping bit fields within a register.

    Returns list of issue dicts.
    """
    issues = []
    if not fields:
        return issues

    # Build a bitmap to detect overlaps
    bit_usage = {}  # bit_position -> field_name

    for field in fields:
        bits_str = field.get("bits", "")
        name = field.get("name", "?")
        parsed = _parse_bit_range(bits_str)
        if parsed is None:
            issues.append({
                "level": "warning",
                "message": f"Field '{name}': unable to parse bit range '{bits_str}'"
            })
            continue

        high, low = parsed

        # Validate bit range fits within register size
        if register_size and high >= register_size:
            issues.append({
                "level": "error",
                "message": f"Field '{name}' bit range [{high}:{low}] exceeds register size ({register_size} bits)"
            })

        if low > high:
            issues.append({
                "level": "error",
                "message": f"Field '{name}' bit range '{bits_str}' has low > high"
            })
            continue

        for bit in range(low, high + 1):
            if bit in bit_usage:
                issues.append({
                    "level": "error",
                    "message": f"Bit {bit} overlap: field '{name}' conflicts with '{bit_usage[bit]}'"
                })
            else:
                bit_usage[bit] = name

    return issues


class RegisterExtractor(BaseExtractor):
    """Extracts register map definitions from datasheet pages.

    Identifies pages containing register maps, register descriptions,
    and bit field tables. Uses Gemini Vision API to extract structured
    register data including addresses, fields, access modes, and reset values.
    """

    DOMAIN_NAME = "register"

    def select_pages(self) -> list[int]:
        """Select pages that contain register map content.

        Scans page text previews for register-related patterns. Also considers
        pages classified as 'electrical' or 'other' that might contain register
        tables embedded in general specification pages.
        """
        register_pages = set()

        for page_info in self.page_classification:
            text = page_info.text_preview.lower() if page_info.text_preview else ""

            # Check text preview against register patterns
            for pattern in REGISTER_PAGE_PATTERNS:
                if pattern.search(text):
                    register_pages.add(page_info.page_num)
                    break

            # Also check pages that might be "other" or "electrical" with
            # register-related content not caught by the short preview.
            # Look for strong indicators in the preview text.
            if page_info.category in ("other", "electrical"):
                if any(kw in text for kw in ["register", "0x0", "bit field", "address offset"]):
                    register_pages.add(page_info.page_num)

        return sorted(register_pages)

    def extract(self, rendered_images) -> dict:
        """Use Gemini Vision API to extract register definitions from page images.

        Args:
            rendered_images: Dict mapping page_num -> PNG bytes, or list of PNG bytes.

        Returns:
            Dict with 'registers' list and 'register_map_summary', matching the
            register.schema.json structure.
        """
        if isinstance(rendered_images, dict):
            images = list(rendered_images.values())
        else:
            images = rendered_images

        if not images:
            return {"registers": [], "register_map_summary": {}}

        return _call_gemini_vision(self.client, self.model, images, REGISTER_EXTRACTION_PROMPT)

    def validate(self, extraction_result: dict) -> dict:
        """Validate extracted register data.

        Checks:
        - Addresses are valid hex strings
        - No duplicate register addresses
        - Bit fields don't overlap within a register
        - Access modes are from the allowed enum
        - Field bit ranges fit within register size

        Returns:
            Dict with 'register_validation_issues' list and 'register_count' int.
        """
        issues = []

        if "error" in extraction_result:
            return {"register_validation_issues": issues, "register_count": 0}

        registers = extraction_result.get("registers", [])

        if not registers:
            issues.append({
                "level": "warning",
                "message": "No registers found in extraction result"
            })
            return {"register_validation_issues": issues, "register_count": 0}

        seen_addresses = {}

        for i, reg in enumerate(registers):
            prefix = f"register[{i}]"
            name = reg.get("name", "?")
            address = reg.get("address", "")

            # --- Check address format ---
            if not address:
                issues.append({
                    "level": "error",
                    "message": f"{prefix} '{name}': missing address"
                })
            elif not _is_valid_hex_string(address):
                issues.append({
                    "level": "error",
                    "message": f"{prefix} '{name}': invalid hex address '{address}'"
                })

            # --- Check for duplicate addresses ---
            if address:
                addr_normalized = address.strip().lower()
                if addr_normalized in seen_addresses:
                    issues.append({
                        "level": "warning",
                        "message": f"{prefix} '{name}': duplicate address {address} (also used by '{seen_addresses[addr_normalized]}')"
                    })
                else:
                    seen_addresses[addr_normalized] = name

            # --- Check register-level access mode ---
            access = reg.get("access")
            if access is not None and access not in VALID_ACCESS_MODES:
                issues.append({
                    "level": "error",
                    "message": f"{prefix} '{name}': invalid access mode '{access}', must be one of {sorted(VALID_ACCESS_MODES)}"
                })

            # --- Check reset_value format ---
            reset_value = reg.get("reset_value")
            if reset_value is not None and not _is_valid_hex_string(reset_value):
                issues.append({
                    "level": "warning",
                    "message": f"{prefix} '{name}': reset_value '{reset_value}' is not a valid hex string"
                })

            # --- Check size_bits ---
            size_bits = reg.get("size_bits")
            if size_bits is not None and size_bits not in (8, 16, 32):
                issues.append({
                    "level": "warning",
                    "message": f"{prefix} '{name}': unusual register size {size_bits} bits (expected 8, 16, or 32)"
                })

            # --- Validate bit fields ---
            fields = reg.get("fields", [])
            if fields:
                # Check field access modes
                for j, field in enumerate(fields):
                    field_name = field.get("name", "?")
                    field_access = field.get("access")
                    if field_access is not None and field_access not in VALID_ACCESS_MODES:
                        issues.append({
                            "level": "error",
                            "message": f"{prefix} '{name}' field[{j}] '{field_name}': invalid access mode '{field_access}'"
                        })

                # Check for bit field overlaps
                overlap_issues = _check_bit_field_overlap(fields, size_bits)
                issues.extend(overlap_issues)

        # --- Validate summary ---
        summary = extraction_result.get("register_map_summary", {})
        bus_type = summary.get("bus_type")
        if bus_type is not None and bus_type not in VALID_BUS_TYPES:
            issues.append({
                "level": "warning",
                "message": f"register_map_summary: unknown bus_type '{bus_type}', expected one of {sorted(VALID_BUS_TYPES)}"
            })

        return {
            "register_validation_issues": issues,
            "register_count": len(registers),
        }
