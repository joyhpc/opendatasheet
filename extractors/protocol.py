"""Protocol extraction module.

Handles extraction of communication interface/protocol definitions from
datasheets including I2C, SPI, UART, JTAG, USB, and other serial or bus
protocols. Identifies protocol description pages and extracts structured
data via Gemini Vision API covering interface configuration, signal
definitions, timing constraints, and command sets.
"""
import json
import re
import time

from google.genai import types

from extractors.base import BaseExtractor


# ============================================
# Constants — valid enum sets
# ============================================

VALID_PROTOCOL_TYPES = {
    "I2C", "SPI", "UART", "JTAG", "SDIO", "USB",
    "MIPI", "GMII", "RGMII", "PCIe", "MDIO",
    "PMBus", "SMBus", "LIN", "CAN", "other",
}

VALID_ROLES = {"master", "slave", "both"}

VALID_SPI_MODES = {0, 1, 2, 3}

VALID_PARITY_VALUES = {"none", "even", "odd", "mark", "space"}

VALID_FLOW_CONTROL_VALUES = {"none", "hardware", "software", "both"}

VALID_SIGNAL_DIRECTIONS = {"input", "output", "bidirectional", "power", "ground", "open-drain"}


# ============================================
# Prompts
# ============================================

PROTOCOL_EXTRACTION_PROMPT = """You are an expert electronic component datasheet parser specializing in communication interfaces and bus protocols.
Analyze the provided datasheet page images and extract ALL communication interface definitions into a structured JSON format.

CRITICAL RULES:
1. Extract every communication interface described in the pages (I2C, SPI, UART, JTAG, USB, MIPI, etc.)
2. For each interface, extract protocol-specific configuration details
3. Extract signal/pin descriptions, timing constraints, and command sets if present
4. Use hex notation for addresses and opcodes (e.g., "0x48", "0xA0")
5. If a value is not specified or not visible, use null
6. Output ONLY valid JSON, no markdown, no code fences

INTERFACE FIELDS TO EXTRACT:
- protocol_type: One of "I2C", "SPI", "UART", "JTAG", "SDIO", "USB", "MIPI", "GMII", "RGMII", "PCIe", "MDIO", "PMBus", "SMBus", "LIN", "CAN", "other"
- role: "master", "slave", "both", or null
- instance_name: Name or identifier for this interface instance (e.g., "I2C0", "SPI1"), or null

I2C-SPECIFIC CONFIGURATION (if protocol_type is "I2C", "PMBus", or "SMBus"):
- i2c_config.slave_address_hex: 7-bit slave address in hex (e.g., "0x48"), or null
- i2c_config.address_configurable: Boolean, true if address can be changed via pins
- i2c_config.address_pins: Array of pin names used to configure the address (e.g., ["A0", "A1"]), or []
- i2c_config.address_bits: Number of address bits (7 or 10), default 7
- i2c_config.max_clock_hz: Maximum supported SCL clock frequency in Hz (e.g., 400000 for 400kHz), or null
- i2c_config.supports_clock_stretching: Boolean or null
- i2c_config.supports_repeated_start: Boolean or null

SPI-SPECIFIC CONFIGURATION (if protocol_type is "SPI"):
- spi_config.mode: SPI mode 0-3 (integer), or null
- spi_config.cpol: Clock polarity 0 or 1, or null
- spi_config.cpha: Clock phase 0 or 1, or null
- spi_config.max_clock_hz: Maximum SPI clock frequency in Hz, or null
- spi_config.bit_order: "MSB" or "LSB" first, or null
- spi_config.data_width: Data width in bits (e.g., 8, 16), or null
- spi_config.cs_active_low: Boolean, true if chip select is active low, or null

UART-SPECIFIC CONFIGURATION (if protocol_type is "UART"):
- uart_config.baud_rates: Array of supported baud rates as integers (e.g., [9600, 115200]), or []
- uart_config.max_baud_rate: Maximum baud rate in bps, or null
- uart_config.data_bits: Number of data bits (5, 6, 7, 8, 9), or null
- uart_config.stop_bits: Number of stop bits (1, 1.5, 2), or null
- uart_config.parity: "none", "even", "odd", "mark", "space", or null
- uart_config.flow_control: "none", "hardware", "software", "both", or null

SIGNAL DESCRIPTIONS (for each interface):
- signals[].name: Signal/pin name (e.g., "SDA", "SCL", "MOSI", "TX")
- signals[].direction: "input", "output", "bidirectional", "open-drain", or null
- signals[].description: Brief description of the signal's function

TIMING CONSTRAINTS (protocol-specific timing):
- timing_constraints[].parameter: Parameter name (e.g., "SCL Clock Frequency", "Data Setup Time")
- timing_constraints[].symbol: Symbol if shown (e.g., "fSCL", "tSU;DAT"), or null
- timing_constraints[].min: Minimum value as a number, or null
- timing_constraints[].typ: Typical value as a number, or null
- timing_constraints[].max: Maximum value as a number, or null
- timing_constraints[].unit: Unit string (e.g., "kHz", "ns", "us")
- timing_constraints[].conditions: Test conditions string, or null

COMMAND SET (register commands, opcodes):
- command_set[].name: Command name (e.g., "Read Data", "Write Config")
- command_set[].opcode_hex: Opcode in hex (e.g., "0x03", "0xF0"), or null
- command_set[].description: What the command does
- command_set[].access: "R", "W", "RW", or null
- command_set[].byte_count: Number of data bytes for this command, or null

NOTES:
- notes: Any additional notes about the interface, or null

SUMMARY FIELDS:
- total_interfaces: Integer count of all interfaces extracted
- has_i2c: Boolean, true if any interface is I2C, PMBus, or SMBus
- has_spi: Boolean, true if any interface is SPI
- has_uart: Boolean, true if any interface is UART
- primary_interface: The protocol_type of the primary/main communication interface, or null

OUTPUT JSON SCHEMA:
{
  "interfaces": [
    {
      "protocol_type": "I2C",
      "role": "slave",
      "instance_name": null,
      "i2c_config": {
        "slave_address_hex": "0x48",
        "address_configurable": true,
        "address_pins": ["A0", "A1"],
        "address_bits": 7,
        "max_clock_hz": 3400000,
        "supports_clock_stretching": true,
        "supports_repeated_start": true
      },
      "spi_config": null,
      "uart_config": null,
      "signals": [
        {
          "name": "SDA",
          "direction": "bidirectional",
          "description": "Serial data line"
        },
        {
          "name": "SCL",
          "direction": "input",
          "description": "Serial clock line"
        }
      ],
      "timing_constraints": [
        {
          "parameter": "SCL Clock Frequency",
          "symbol": "fSCL",
          "min": 0,
          "typ": null,
          "max": 3400000,
          "unit": "Hz",
          "conditions": "High-speed mode"
        }
      ],
      "command_set": [],
      "notes": null
    }
  ],
  "protocol_summary": {
    "total_interfaces": 1,
    "has_i2c": true,
    "has_spi": false,
    "has_uart": false,
    "primary_interface": "I2C"
  }
}

IMPORTANT:
- Extract ALL communication interfaces visible in the images, not just the first one
- If the device supports multiple modes of the same protocol (e.g., I2C standard and fast mode), note this in timing_constraints or notes
- For I2C devices, always try to extract the slave address and address configuration
- For SPI devices, always try to determine the SPI mode (CPOL/CPHA)
- Preserve the exact signal and command names from the datasheet (do not rename)
- If a command table or opcode table is present, extract all entries
- Include any protocol-specific timing from timing tables that relate to the interface
"""


# ============================================
# Page selection patterns
# ============================================

PROTOCOL_PAGE_PATTERNS = [
    # I2C interface patterns
    re.compile(r'I2C', re.IGNORECASE),
    re.compile(r'I\u00b2C', re.IGNORECASE),
    re.compile(r'inter-integrated\s+circuit', re.IGNORECASE),
    re.compile(r'slave\s+address', re.IGNORECASE),
    re.compile(r'\bSCL\b', re.IGNORECASE),
    re.compile(r'\bSDA\b', re.IGNORECASE),
    # SPI interface patterns
    re.compile(r'\bSPI\b', re.IGNORECASE),
    re.compile(r'serial\s+peripheral', re.IGNORECASE),
    re.compile(r'\bMOSI\b', re.IGNORECASE),
    re.compile(r'\bMISO\b', re.IGNORECASE),
    re.compile(r'\bSCLK\b', re.IGNORECASE),
    re.compile(r'chip\s+select', re.IGNORECASE),
    # UART / serial patterns
    re.compile(r'\bUART\b', re.IGNORECASE),
    re.compile(r'\bUSART\b', re.IGNORECASE),
    re.compile(r'serial\s+interface', re.IGNORECASE),
    re.compile(r'baud\s+rate', re.IGNORECASE),
    re.compile(r'RS-232', re.IGNORECASE),
    re.compile(r'RS-485', re.IGNORECASE),
    # General serial / protocol patterns
    re.compile(r'serial\s+communication', re.IGNORECASE),
    re.compile(r'digital\s+interface', re.IGNORECASE),
    re.compile(r'communication\s+interface', re.IGNORECASE),
    re.compile(r'host\s+interface', re.IGNORECASE),
    # Bus protocol patterns
    re.compile(r'\bPMBus\b', re.IGNORECASE),
    re.compile(r'\bSMBus\b', re.IGNORECASE),
    re.compile(r'\bMDIO\b', re.IGNORECASE),
    re.compile(r'\bJTAG\b', re.IGNORECASE),
    re.compile(r'command\s+protocol', re.IGNORECASE),
    # Protocol timing patterns
    re.compile(r'I2C\s+timing', re.IGNORECASE),
    re.compile(r'SPI\s+timing', re.IGNORECASE),
    re.compile(r'serial\s+timing', re.IGNORECASE),
    re.compile(r'bus\s+timing', re.IGNORECASE),
    # Command / opcode table patterns
    re.compile(r'command\s+register', re.IGNORECASE),
    re.compile(r'command\s+set', re.IGNORECASE),
    re.compile(r'\bopcode\b', re.IGNORECASE),
    re.compile(r'command\s+code', re.IGNORECASE),
    re.compile(r'instruction\s+set', re.IGNORECASE),
]

# Minimum number of pattern matches required per page
PROTOCOL_PAGE_MATCH_THRESHOLD = 2


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
            if "interfaces" not in result:
                for key in ["communication_interfaces", "protocols",
                            "protocol_interfaces", "interface_list"]:
                    if key in result:
                        result["interfaces"] = result.pop(key)
                        break
            if "protocol_summary" not in result:
                for key in ["summary", "protocolSummary", "protocol_info"]:
                    if key in result:
                        result["protocol_summary"] = result.pop(key)
                        break
            return result
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                time.sleep(3)
                continue
            return {"error": f"JSON parse failed: {str(e)}",
                    "raw": raw[:500] if 'raw' in dir() else ""}
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

def _validate_hex(value, max_val=0x7F):
    """Validate a hex address string.

    Args:
        value: Hex string to validate (e.g., "0x48").
        max_val: Maximum allowed integer value (default 0x7F for 7-bit I2C).

    Returns:
        True if the value is a valid hex string within range, False otherwise.
    """
    if not isinstance(value, str) or not value.strip():
        return False
    s = value.strip()
    if s.lower().startswith("0x"):
        s = s[2:]
    if not s:
        return False
    if not all(c in "0123456789abcdefABCDEF" for c in s):
        return False
    try:
        int_val = int(s, 16)
        return 0 <= int_val <= max_val
    except ValueError:
        return False


def _is_valid_hex_format(value):
    """Check if a string is valid hex format (any range), for opcode validation."""
    if not isinstance(value, str) or not value.strip():
        return False
    s = value.strip()
    if s.lower().startswith("0x"):
        s = s[2:]
    if not s:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in s)


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


# ============================================
# Extractor class
# ============================================

class ProtocolExtractor(BaseExtractor):
    """Extracts communication interface and protocol definitions from datasheet pages.

    Identifies pages containing I2C, SPI, UART, JTAG, and other communication
    interface descriptions. Uses Gemini Vision API to extract structured protocol
    data including interface configuration, signal definitions, timing constraints,
    and command sets.
    """

    DOMAIN_NAME = "protocol"

    def select_pages(self) -> list[int]:
        """Select pages that contain protocol / communication interface content.

        Scans page text previews for protocol-related patterns. A page must
        match at least PROTOCOL_PAGE_MATCH_THRESHOLD patterns to be selected,
        reducing false positives from incidental mentions.
        """
        protocol_pages = set()

        for page_info in self.page_classification:
            text = page_info.text_preview.lower() if page_info.text_preview else ""

            # Count how many patterns match on this page
            match_count = 0
            for pattern in PROTOCOL_PAGE_PATTERNS:
                if pattern.search(text):
                    match_count += 1
                    if match_count >= PROTOCOL_PAGE_MATCH_THRESHOLD:
                        protocol_pages.add(page_info.page_num)
                        break

            # Also check pages classified with related categories that
            # may contain protocol information in their body text
            if page_info.page_num not in protocol_pages:
                if page_info.category in ("other", "electrical", "register"):
                    protocol_keywords = [
                        "i2c", "spi", "uart", "serial interface",
                        "slave address", "communication interface",
                        "host interface", "bus protocol", "command set",
                        "smbus", "pmbus", "mdio", "jtag",
                    ]
                    kw_hits = sum(1 for kw in protocol_keywords if kw in text)
                    if kw_hits >= PROTOCOL_PAGE_MATCH_THRESHOLD:
                        protocol_pages.add(page_info.page_num)

        return sorted(protocol_pages)

    def extract(self, rendered_images) -> dict:
        """Use Gemini Vision API to extract protocol definitions from page images.

        Args:
            rendered_images: Dict mapping page_num -> PNG bytes, or list of PNG bytes.

        Returns:
            Dict with 'interfaces' list and 'protocol_summary', matching the
            protocol.schema.json structure.
        """
        if isinstance(rendered_images, dict):
            images = list(rendered_images.values())
        else:
            images = rendered_images

        if not images:
            return {"interfaces": [], "protocol_summary": {}}

        result = _call_gemini_vision(
            self.client, self.model, images, PROTOCOL_EXTRACTION_PROMPT
        )

        # Build or rebuild protocol_summary from actual interface data
        interfaces = result.get("interfaces", [])
        if interfaces and "error" not in result:
            result["protocol_summary"] = self._build_summary(interfaces)

        return result

    def validate(self, extraction_result: dict) -> dict:
        """Validate extracted protocol data.

        Checks:
        - protocol_type is from the allowed enum
        - role is valid if present
        - I2C address is valid hex in 7-bit range
        - SPI mode matches cpol/cpha consistency
        - No duplicate interfaces (same protocol_type + instance_name)
        - Timing constraint monotonicity (min <= typ <= max)
        - Command opcode hex format
        - Empty interface detection (no signals, no config, no commands)
        - Summary consistency with actual interface data

        Returns:
            Dict with 'protocol_validation' list and 'protocol_interface_count' int.
        """
        issues = []

        if "error" in extraction_result:
            return {"protocol_validation": issues, "protocol_interface_count": 0}

        interfaces = extraction_result.get("interfaces", [])

        if not interfaces:
            issues.append({
                "level": "warning",
                "message": "No interfaces found in extraction result"
            })
            return {"protocol_validation": issues, "protocol_interface_count": 0}

        seen_interfaces = {}

        for i, iface in enumerate(interfaces):
            prefix = f"interface[{i}]"
            protocol_type = iface.get("protocol_type", "?")
            instance_name = iface.get("instance_name")

            # --- Check protocol_type enum ---
            if protocol_type not in VALID_PROTOCOL_TYPES:
                issues.append({
                    "level": "error",
                    "message": (
                        f"{prefix}: invalid protocol_type '{protocol_type}', "
                        f"must be one of {sorted(VALID_PROTOCOL_TYPES)}"
                    )
                })

            # --- Check role enum ---
            role = iface.get("role")
            if role is not None and role not in VALID_ROLES:
                issues.append({
                    "level": "error",
                    "message": (
                        f"{prefix} '{protocol_type}': invalid role '{role}', "
                        f"must be one of {sorted(VALID_ROLES)}"
                    )
                })

            # --- Duplicate interface detection ---
            dedup_key = (
                protocol_type.strip().lower() if isinstance(protocol_type, str) else "?",
                (instance_name or "").strip().lower(),
            )
            if dedup_key in seen_interfaces:
                issues.append({
                    "level": "warning",
                    "message": (
                        f"{prefix} '{protocol_type}': duplicate interface "
                        f"(same protocol_type + instance_name as "
                        f"interface[{seen_interfaces[dedup_key]}])"
                    )
                })
            else:
                seen_interfaces[dedup_key] = i

            # --- I2C config validation ---
            i2c_config = iface.get("i2c_config")
            if i2c_config and isinstance(i2c_config, dict):
                addr = i2c_config.get("slave_address_hex")
                if addr is not None:
                    addr_bits = i2c_config.get("address_bits", 7)
                    max_addr = 0x3FF if addr_bits == 10 else 0x7F
                    if not _validate_hex(addr, max_val=max_addr):
                        issues.append({
                            "level": "error",
                            "message": (
                                f"{prefix} '{protocol_type}': invalid I2C "
                                f"slave_address_hex '{addr}' "
                                f"(must be 0x00-0x{max_addr:02X})"
                            )
                        })

                addr_bits = i2c_config.get("address_bits")
                if addr_bits is not None and addr_bits not in (7, 10):
                    issues.append({
                        "level": "warning",
                        "message": (
                            f"{prefix} '{protocol_type}': unusual "
                            f"address_bits value {addr_bits} (expected 7 or 10)"
                        )
                    })

            # --- SPI config validation ---
            spi_config = iface.get("spi_config")
            if spi_config and isinstance(spi_config, dict):
                mode = spi_config.get("mode")
                cpol = spi_config.get("cpol")
                cpha = spi_config.get("cpha")

                if mode is not None and mode not in VALID_SPI_MODES:
                    issues.append({
                        "level": "error",
                        "message": (
                            f"{prefix} '{protocol_type}': invalid SPI mode "
                            f"{mode}, must be 0, 1, 2, or 3"
                        )
                    })

                if cpol is not None and cpol not in (0, 1):
                    issues.append({
                        "level": "error",
                        "message": (
                            f"{prefix} '{protocol_type}': invalid SPI cpol "
                            f"{cpol}, must be 0 or 1"
                        )
                    })

                if cpha is not None and cpha not in (0, 1):
                    issues.append({
                        "level": "error",
                        "message": (
                            f"{prefix} '{protocol_type}': invalid SPI cpha "
                            f"{cpha}, must be 0 or 1"
                        )
                    })

                # Cross-check: mode should equal cpol*2 + cpha
                if (mode is not None and cpol is not None and cpha is not None):
                    expected_mode = cpol * 2 + cpha
                    if mode != expected_mode:
                        issues.append({
                            "level": "error",
                            "message": (
                                f"{prefix} '{protocol_type}': SPI mode "
                                f"{mode} inconsistent with cpol={cpol}, "
                                f"cpha={cpha} (expected mode={expected_mode})"
                            )
                        })

            # --- UART config validation ---
            uart_config = iface.get("uart_config")
            if uart_config and isinstance(uart_config, dict):
                parity = uart_config.get("parity")
                if parity is not None and parity not in VALID_PARITY_VALUES:
                    issues.append({
                        "level": "warning",
                        "message": (
                            f"{prefix} '{protocol_type}': invalid parity "
                            f"'{parity}', expected one of "
                            f"{sorted(VALID_PARITY_VALUES)}"
                        )
                    })

                flow_control = uart_config.get("flow_control")
                if flow_control is not None and flow_control not in VALID_FLOW_CONTROL_VALUES:
                    issues.append({
                        "level": "warning",
                        "message": (
                            f"{prefix} '{protocol_type}': invalid "
                            f"flow_control '{flow_control}', expected one of "
                            f"{sorted(VALID_FLOW_CONTROL_VALUES)}"
                        )
                    })

            # --- Timing constraint validation ---
            timing_constraints = iface.get("timing_constraints", [])
            if isinstance(timing_constraints, list):
                for t_idx, tc in enumerate(timing_constraints):
                    t_name = tc.get("parameter", "?")
                    min_val = tc.get("min")
                    typ_val = tc.get("typ")
                    max_val = tc.get("max")
                    mono = _check_monotonicity(min_val, typ_val, max_val)
                    if mono is False:
                        issues.append({
                            "level": "error",
                            "message": (
                                f"{prefix} '{protocol_type}' "
                                f"timing_constraint[{t_idx}] '{t_name}': "
                                f"min/typ/max not monotonic: "
                                f"{min_val}/{typ_val}/{max_val}"
                            )
                        })

            # --- Command set validation ---
            command_set = iface.get("command_set", [])
            if isinstance(command_set, list):
                for c_idx, cmd in enumerate(command_set):
                    c_name = cmd.get("name", "?")
                    opcode = cmd.get("opcode_hex")
                    if opcode is not None and not _is_valid_hex_format(opcode):
                        issues.append({
                            "level": "error",
                            "message": (
                                f"{prefix} '{protocol_type}' "
                                f"command_set[{c_idx}] '{c_name}': invalid "
                                f"opcode_hex '{opcode}'"
                            )
                        })

            # --- Empty interface warning ---
            signals = iface.get("signals", [])
            has_config = bool(i2c_config or spi_config or uart_config)
            has_signals = bool(signals) if isinstance(signals, list) else False
            has_commands = bool(command_set) if isinstance(command_set, list) else False
            has_timing = bool(timing_constraints) if isinstance(timing_constraints, list) else False
            if not has_config and not has_signals and not has_commands and not has_timing:
                issues.append({
                    "level": "warning",
                    "message": (
                        f"{prefix} '{protocol_type}': empty interface — "
                        f"no config, signals, commands, or timing extracted"
                    )
                })

        # --- Summary consistency checks ---
        summary = extraction_result.get("protocol_summary", {})
        if summary and isinstance(summary, dict):
            actual_summary = self._build_summary(interfaces)

            if summary.get("has_i2c") != actual_summary["has_i2c"]:
                issues.append({
                    "level": "warning",
                    "message": (
                        f"protocol_summary.has_i2c is "
                        f"{summary.get('has_i2c')} but actual is "
                        f"{actual_summary['has_i2c']}"
                    )
                })
            if summary.get("has_spi") != actual_summary["has_spi"]:
                issues.append({
                    "level": "warning",
                    "message": (
                        f"protocol_summary.has_spi is "
                        f"{summary.get('has_spi')} but actual is "
                        f"{actual_summary['has_spi']}"
                    )
                })
            if summary.get("has_uart") != actual_summary["has_uart"]:
                issues.append({
                    "level": "warning",
                    "message": (
                        f"protocol_summary.has_uart is "
                        f"{summary.get('has_uart')} but actual is "
                        f"{actual_summary['has_uart']}"
                    )
                })

        return {
            "protocol_validation": issues,
            "protocol_interface_count": len(interfaces),
        }

    # ============================================
    # Helper methods
    # ============================================

    def _parse_response(self, raw_text: str) -> dict:
        """Extract JSON from a Gemini response string.

        Handles markdown code fences and searches for JSON object boundaries.

        Args:
            raw_text: Raw text response from Gemini.

        Returns:
            Parsed dict, or dict with 'error' key on failure.
        """
        raw = raw_text
        # Strip markdown fences
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        # Find JSON boundaries
        start = raw.find('{')
        end = raw.rfind('}')
        if start >= 0 and end > start:
            raw = raw[start:end + 1]
        try:
            result = json.loads(raw.strip())
            if isinstance(result, list):
                result = result[0] if result else {"error": "Empty list"}
            if not isinstance(result, dict):
                return {"error": f"Unexpected type: {type(result).__name__}"}
            return result
        except json.JSONDecodeError as e:
            return {"error": f"JSON parse failed: {str(e)}",
                    "raw": raw[:500]}

    def _build_summary(self, interfaces: list) -> dict:
        """Build protocol_summary from the extracted interfaces list.

        Args:
            interfaces: List of interface dicts with protocol_type fields.

        Returns:
            Dict with total_interfaces, has_i2c, has_spi, has_uart,
            and primary_interface fields.
        """
        i2c_types = {"I2C", "PMBus", "SMBus"}
        protocol_types = [
            iface.get("protocol_type", "other") for iface in interfaces
        ]

        has_i2c = any(pt in i2c_types for pt in protocol_types)
        has_spi = any(pt == "SPI" for pt in protocol_types)
        has_uart = any(pt == "UART" for pt in protocol_types)

        # Primary interface: first listed, or the one with most detail
        primary = protocol_types[0] if protocol_types else None

        return {
            "total_interfaces": len(interfaces),
            "has_i2c": has_i2c,
            "has_spi": has_spi,
            "has_uart": has_uart,
            "primary_interface": primary,
        }
