"""Tests for the protocol extraction module.

Validates ProtocolExtractor integration with the framework, schema
compliance, and validation logic for all protocol types, I2C/SPI/UART
configurations, timing constraints, command sets, and edge cases.
Does NOT require Gemini API access.
"""
import json
import os
import pytest

from extractors.protocol import (
    ProtocolExtractor,
    VALID_PROTOCOL_TYPES,
    VALID_ROLES,
    VALID_SPI_MODES,
    VALID_PARITY_VALUES,
    VALID_FLOW_CONTROL_VALUES,
    VALID_SIGNAL_DIRECTIONS,
    _validate_hex,
    _is_valid_hex_format,
    _check_monotonicity,
)
from extractors.base import BaseExtractor


# ─── Helpers ────────────────────────────────────────────────────────

def _make_extractor():
    """Create a ProtocolExtractor instance with dummy parameters."""
    return ProtocolExtractor(
        client=None,
        model=None,
        pdf_path="/tmp/test.pdf",
        page_classification=[],
        is_fpga=False,
    )


def _make_i2c_interface(**overrides):
    """Build a valid I2C interface dict, with optional overrides."""
    iface = {
        "protocol_type": "I2C",
        "role": "slave",
        "instance_name": None,
        "i2c_config": {
            "slave_address_hex": "0x48",
            "address_configurable": True,
            "address_pins": ["A0", "A1"],
            "address_bits": 7,
            "max_clock_hz": 400000,
            "supports_clock_stretching": True,
            "supports_repeated_start": True,
        },
        "spi_config": None,
        "uart_config": None,
        "signals": [
            {"name": "SDA", "direction": "bidirectional", "description": "Serial data line"},
            {"name": "SCL", "direction": "input", "description": "Serial clock line"},
        ],
        "timing_constraints": [
            {
                "parameter": "SCL Clock Frequency",
                "symbol": "fSCL",
                "min": 0,
                "typ": None,
                "max": 400000,
                "unit": "Hz",
                "conditions": "Fast mode",
            }
        ],
        "command_set": [],
        "notes": None,
    }
    iface.update(overrides)
    return iface


def _make_spi_interface(**overrides):
    """Build a valid SPI interface dict, with optional overrides."""
    iface = {
        "protocol_type": "SPI",
        "role": "slave",
        "instance_name": "SPI0",
        "i2c_config": None,
        "spi_config": {
            "mode": 0,
            "cpol": 0,
            "cpha": 0,
            "max_clock_hz": 10000000,
            "bit_order": "MSB",
            "data_width": 8,
            "cs_active_low": True,
        },
        "uart_config": None,
        "signals": [
            {"name": "MOSI", "direction": "input", "description": "Master out slave in"},
            {"name": "MISO", "direction": "output", "description": "Master in slave out"},
            {"name": "SCLK", "direction": "input", "description": "SPI clock"},
            {"name": "CS", "direction": "input", "description": "Chip select"},
        ],
        "timing_constraints": [],
        "command_set": [
            {
                "name": "Read Data",
                "opcode_hex": "0x03",
                "description": "Read data from register",
                "access": "read",
                "byte_count": 2,
            }
        ],
        "notes": None,
    }
    iface.update(overrides)
    return iface


def _make_uart_interface(**overrides):
    """Build a valid UART interface dict."""
    iface = {
        "protocol_type": "UART",
        "role": "both",
        "instance_name": None,
        "i2c_config": None,
        "spi_config": None,
        "uart_config": {
            "baud_rates": [9600, 115200],
            "max_baud_rate": 115200,
            "data_bits": 8,
            "stop_bits": 1,
            "parity": "none",
            "flow_control": "none",
        },
        "signals": [
            {"name": "TX", "direction": "output", "description": "Transmit data"},
            {"name": "RX", "direction": "input", "description": "Receive data"},
        ],
        "timing_constraints": [],
        "command_set": [],
        "notes": None,
    }
    iface.update(overrides)
    return iface


def _make_extraction(*interfaces):
    """Build a full extraction result with given interfaces and auto-summary."""
    ext = _make_extractor()
    iface_list = list(interfaces)
    return {
        "interfaces": iface_list,
        "protocol_summary": ext._build_summary(iface_list),
    }


# ─── Framework Integration ──────────────────────────────────────────


class TestFrameworkIntegration:
    def test_inherits_base_extractor(self):
        """ProtocolExtractor must inherit from BaseExtractor."""
        assert issubclass(ProtocolExtractor, BaseExtractor)

    def test_domain_name(self):
        """DOMAIN_NAME must be 'protocol'."""
        assert ProtocolExtractor.DOMAIN_NAME == "protocol"

    def test_in_registry(self):
        """ProtocolExtractor must be in the global EXTRACTOR_REGISTRY."""
        from extractors import EXTRACTOR_REGISTRY
        assert ProtocolExtractor in EXTRACTOR_REGISTRY

    def test_registry_position(self):
        """ProtocolExtractor should be the 9th entry (index 8) in the registry."""
        from extractors import EXTRACTOR_REGISTRY
        assert EXTRACTOR_REGISTRY[8] is ProtocolExtractor
        assert len(EXTRACTOR_REGISTRY) == 11

    def test_has_required_methods(self):
        """ProtocolExtractor must implement select_pages, extract, validate."""
        for method in ("select_pages", "extract", "validate"):
            assert hasattr(ProtocolExtractor, method)

    def test_instantiation(self):
        """ProtocolExtractor can be instantiated with dummy args."""
        ext = _make_extractor()
        assert ext.client is None
        assert ext.DOMAIN_NAME == "protocol"


# ─── Validation — protocol_type enum ────────────────────────────────


class TestProtocolTypeEnum:
    @pytest.mark.parametrize("ptype", sorted(VALID_PROTOCOL_TYPES))
    def test_valid_protocol_types(self, ptype):
        """All 16 valid protocol_type values should produce no type error."""
        ext = _make_extractor()
        data = _make_extraction({"protocol_type": ptype, "signals": [{"name": "SIG", "direction": "input", "description": "test"}]})
        result = ext.validate(data)
        type_errors = [
            i for i in result["protocol_validation"]
            if "invalid protocol_type" in i["message"]
        ]
        assert type_errors == [], f"Unexpected error for valid type '{ptype}': {type_errors}"

    def test_invalid_protocol_type(self):
        """An invalid protocol_type should produce a validation error."""
        ext = _make_extractor()
        data = _make_extraction({"protocol_type": "INVALID_BUS", "signals": []})
        result = ext.validate(data)
        type_errors = [
            i for i in result["protocol_validation"]
            if "invalid protocol_type" in i["message"]
        ]
        assert len(type_errors) == 1
        assert type_errors[0]["level"] == "error"


# ─── Validation — role enum ─────────────────────────────────────────


class TestRoleEnum:
    @pytest.mark.parametrize("role", sorted(VALID_ROLES))
    def test_valid_roles(self, role):
        """Each valid role should produce no role error."""
        ext = _make_extractor()
        iface = _make_i2c_interface(role=role)
        data = _make_extraction(iface)
        result = ext.validate(data)
        role_errors = [
            i for i in result["protocol_validation"]
            if "invalid role" in i["message"]
        ]
        assert role_errors == []

    def test_null_role_is_acceptable(self):
        """A null role should not trigger an error."""
        ext = _make_extractor()
        iface = _make_i2c_interface(role=None)
        data = _make_extraction(iface)
        result = ext.validate(data)
        role_errors = [
            i for i in result["protocol_validation"]
            if "invalid role" in i["message"]
        ]
        assert role_errors == []

    def test_invalid_role(self):
        """An invalid role value should produce an error."""
        ext = _make_extractor()
        iface = _make_i2c_interface(role="controller")
        data = _make_extraction(iface)
        result = ext.validate(data)
        role_errors = [
            i for i in result["protocol_validation"]
            if "invalid role" in i["message"]
        ]
        assert len(role_errors) == 1
        assert role_errors[0]["level"] == "error"


# ─── Validation — I2C address ───────────────────────────────────────


class TestI2CAddress:
    def test_valid_hex_address(self):
        """Valid 7-bit hex address 0x48 should pass validation."""
        ext = _make_extractor()
        data = _make_extraction(_make_i2c_interface())
        result = ext.validate(data)
        addr_errors = [
            i for i in result["protocol_validation"]
            if "invalid I2C" in i["message"] and "slave_address_hex" in i["message"]
        ]
        assert addr_errors == []

    def test_invalid_hex_address(self):
        """Non-hex address should fail validation."""
        ext = _make_extractor()
        iface = _make_i2c_interface()
        iface["i2c_config"]["slave_address_hex"] = "0xGG"
        data = _make_extraction(iface)
        result = ext.validate(data)
        addr_errors = [
            i for i in result["protocol_validation"]
            if "invalid I2C" in i["message"]
        ]
        assert len(addr_errors) == 1

    def test_out_of_range_7bit(self):
        """Address above 0x7F for 7-bit mode should fail."""
        ext = _make_extractor()
        iface = _make_i2c_interface()
        iface["i2c_config"]["slave_address_hex"] = "0xFF"
        iface["i2c_config"]["address_bits"] = 7
        data = _make_extraction(iface)
        result = ext.validate(data)
        addr_errors = [
            i for i in result["protocol_validation"]
            if "invalid I2C" in i["message"]
        ]
        assert len(addr_errors) == 1

    def test_10bit_address_within_range(self):
        """Address 0xFF with address_bits=10 should pass (max 0x3FF)."""
        ext = _make_extractor()
        iface = _make_i2c_interface()
        iface["i2c_config"]["slave_address_hex"] = "0xFF"
        iface["i2c_config"]["address_bits"] = 10
        data = _make_extraction(iface)
        result = ext.validate(data)
        addr_errors = [
            i for i in result["protocol_validation"]
            if "invalid I2C" in i["message"] and "slave_address" in i["message"]
        ]
        assert addr_errors == []

    def test_validate_hex_function(self):
        """Direct tests on _validate_hex helper."""
        assert _validate_hex("0x48") is True
        assert _validate_hex("0x00") is True
        assert _validate_hex("0x7F") is True
        assert _validate_hex("0x80") is False  # Out of 7-bit range
        assert _validate_hex("0x80", max_val=0xFF) is True
        assert _validate_hex("0xGG") is False
        assert _validate_hex("") is False
        assert _validate_hex(None) is False


# ─── Validation — SPI mode consistency ──────────────────────────────


class TestSPIModeConsistency:
    def test_mode_0_cpol_0_cpha_0(self):
        """SPI mode=0 with cpol=0, cpha=0 should be consistent."""
        ext = _make_extractor()
        iface = _make_spi_interface()
        # mode=0, cpol=0, cpha=0 is the default from helper
        data = _make_extraction(iface)
        result = ext.validate(data)
        spi_errors = [
            i for i in result["protocol_validation"]
            if "SPI mode" in i["message"] and "inconsistent" in i["message"]
        ]
        assert spi_errors == []

    def test_mode_0_cpol_1_mismatch(self):
        """SPI mode=0 with cpol=1, cpha=0 should produce mismatch error."""
        ext = _make_extractor()
        iface = _make_spi_interface()
        iface["spi_config"]["mode"] = 0
        iface["spi_config"]["cpol"] = 1
        iface["spi_config"]["cpha"] = 0
        data = _make_extraction(iface)
        result = ext.validate(data)
        spi_errors = [
            i for i in result["protocol_validation"]
            if "SPI mode" in i["message"] and "inconsistent" in i["message"]
        ]
        assert len(spi_errors) == 1
        assert spi_errors[0]["level"] == "error"

    def test_mode_3_cpol_1_cpha_1(self):
        """SPI mode=3 with cpol=1, cpha=1 should be consistent."""
        ext = _make_extractor()
        iface = _make_spi_interface()
        iface["spi_config"]["mode"] = 3
        iface["spi_config"]["cpol"] = 1
        iface["spi_config"]["cpha"] = 1
        data = _make_extraction(iface)
        result = ext.validate(data)
        spi_errors = [
            i for i in result["protocol_validation"]
            if "SPI mode" in i["message"] and "inconsistent" in i["message"]
        ]
        assert spi_errors == []

    def test_invalid_spi_mode(self):
        """SPI mode=5 (out of 0-3 range) should produce error."""
        ext = _make_extractor()
        iface = _make_spi_interface()
        iface["spi_config"]["mode"] = 5
        iface["spi_config"]["cpol"] = None
        iface["spi_config"]["cpha"] = None
        data = _make_extraction(iface)
        result = ext.validate(data)
        mode_errors = [
            i for i in result["protocol_validation"]
            if "invalid SPI mode" in i["message"]
        ]
        assert len(mode_errors) == 1


# ─── Validation — timing monotonicity ──────────────────────────────


class TestTimingMonotonicity:
    def test_min_lte_typ_lte_max(self):
        """Valid monotonic timing (min <= typ <= max) should produce no error."""
        ext = _make_extractor()
        iface = _make_i2c_interface()
        iface["timing_constraints"] = [{
            "parameter": "Setup Time",
            "symbol": "tSU",
            "min": 100,
            "typ": 200,
            "max": 300,
            "unit": "ns",
            "conditions": None,
        }]
        data = _make_extraction(iface)
        result = ext.validate(data)
        mono_errors = [
            i for i in result["protocol_validation"]
            if "not monotonic" in i["message"]
        ]
        assert mono_errors == []

    def test_violated_monotonicity(self):
        """min > max should produce a monotonicity error."""
        ext = _make_extractor()
        iface = _make_i2c_interface()
        iface["timing_constraints"] = [{
            "parameter": "Hold Time",
            "symbol": "tHD",
            "min": 500,
            "typ": 200,
            "max": 100,
            "unit": "ns",
            "conditions": None,
        }]
        data = _make_extraction(iface)
        result = ext.validate(data)
        mono_errors = [
            i for i in result["protocol_validation"]
            if "not monotonic" in i["message"]
        ]
        assert len(mono_errors) == 1
        assert mono_errors[0]["level"] == "error"

    def test_check_monotonicity_function(self):
        """Direct tests on _check_monotonicity helper."""
        assert _check_monotonicity(1, 2, 3) is True
        assert _check_monotonicity(1, None, 3) is True
        assert _check_monotonicity(3, 2, 1) is False
        assert _check_monotonicity(None, None, None) is None
        assert _check_monotonicity(5, None, None) is None
        assert _check_monotonicity(1, 1, 1) is True  # equal values OK


# ─── Validation — command opcode ────────────────────────────────────


class TestCommandOpcode:
    def test_valid_hex_opcode(self):
        """Valid hex opcode '0x03' should pass."""
        ext = _make_extractor()
        iface = _make_spi_interface()
        data = _make_extraction(iface)
        result = ext.validate(data)
        opcode_errors = [
            i for i in result["protocol_validation"]
            if "opcode_hex" in i["message"]
        ]
        assert opcode_errors == []

    def test_invalid_opcode_format(self):
        """Non-hex opcode 'ZZZZ' should produce error."""
        ext = _make_extractor()
        iface = _make_spi_interface()
        iface["command_set"] = [{
            "name": "Bad Command",
            "opcode_hex": "ZZZZ",
            "description": "test",
            "access": "read",
            "byte_count": 1,
        }]
        data = _make_extraction(iface)
        result = ext.validate(data)
        opcode_errors = [
            i for i in result["protocol_validation"]
            if "opcode_hex" in i["message"]
        ]
        assert len(opcode_errors) == 1
        assert opcode_errors[0]["level"] == "error"

    def test_is_valid_hex_format_function(self):
        """Direct tests on _is_valid_hex_format helper."""
        assert _is_valid_hex_format("0x03") is True
        assert _is_valid_hex_format("0xFF") is True
        assert _is_valid_hex_format("AB") is True
        assert _is_valid_hex_format("0xGG") is False
        assert _is_valid_hex_format("") is False
        assert _is_valid_hex_format(None) is False


# ─── Validation — duplicate interfaces ──────────────────────────────


class TestDuplicateInterfaces:
    def test_duplicate_protocol_type_and_instance(self):
        """Two interfaces with same protocol_type + instance_name produce warning."""
        ext = _make_extractor()
        iface1 = _make_i2c_interface()
        iface2 = _make_i2c_interface()
        data = _make_extraction(iface1, iface2)
        result = ext.validate(data)
        dup_errors = [
            i for i in result["protocol_validation"]
            if "duplicate interface" in i["message"]
        ]
        assert len(dup_errors) == 1
        assert dup_errors[0]["level"] == "warning"

    def test_same_type_different_instance(self):
        """Same protocol_type but different instance_name should not warn."""
        ext = _make_extractor()
        iface1 = _make_spi_interface(instance_name="SPI0")
        iface2 = _make_spi_interface(instance_name="SPI1")
        data = _make_extraction(iface1, iface2)
        result = ext.validate(data)
        dup_errors = [
            i for i in result["protocol_validation"]
            if "duplicate interface" in i["message"]
        ]
        assert dup_errors == []


# ─── Validation — empty interface warning ───────────────────────────


class TestEmptyInterface:
    def test_empty_interface_warning(self):
        """Interface with no config, signals, commands, or timing should warn."""
        ext = _make_extractor()
        iface = {
            "protocol_type": "JTAG",
            "role": None,
            "instance_name": None,
            "i2c_config": None,
            "spi_config": None,
            "uart_config": None,
            "signals": [],
            "timing_constraints": [],
            "command_set": [],
            "notes": None,
        }
        data = _make_extraction(iface)
        result = ext.validate(data)
        empty_warnings = [
            i for i in result["protocol_validation"]
            if "empty interface" in i["message"]
        ]
        assert len(empty_warnings) == 1
        assert empty_warnings[0]["level"] == "warning"


# ─── Validation — summary consistency ──────────────────────────────


class TestSummaryConsistency:
    def test_has_i2c_true_but_no_i2c_interface(self):
        """Summary says has_i2c=true but no I2C interface should warn."""
        ext = _make_extractor()
        spi_iface = _make_spi_interface()
        data = {
            "interfaces": [spi_iface],
            "protocol_summary": {
                "total_interfaces": 1,
                "has_i2c": True,   # Wrong: no I2C interface
                "has_spi": True,
                "has_uart": False,
                "primary_interface": "SPI",
            },
        }
        result = ext.validate(data)
        summary_warnings = [
            i for i in result["protocol_validation"]
            if "protocol_summary.has_i2c" in i["message"]
        ]
        assert len(summary_warnings) == 1
        assert summary_warnings[0]["level"] == "warning"

    def test_consistent_summary_no_warning(self):
        """Consistent summary should produce no summary warnings."""
        ext = _make_extractor()
        data = _make_extraction(_make_i2c_interface(), _make_spi_interface())
        result = ext.validate(data)
        summary_warnings = [
            i for i in result["protocol_validation"]
            if "protocol_summary" in i["message"]
        ]
        assert summary_warnings == []


# ─── Schema compliance ──────────────────────────────────────────────


class TestSchemaCompliance:
    def test_sample_output_validates_against_schema(self):
        """A well-formed extraction output should validate against protocol.schema.json."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = os.path.join(
            os.path.dirname(__file__),
            "schemas", "domains", "protocol.schema.json"
        )
        with open(schema_path) as f:
            schema = json.load(f)

        sample = {
            "interfaces": [
                {
                    "protocol_type": "I2C",
                    "role": "slave",
                    "instance_name": None,
                    "i2c_config": {
                        "slave_address_hex": "0x48",
                        "address_configurable": True,
                        "address_pins": ["A0", "A1"],
                        "address_bits": 7,
                        "max_clock_hz": 400000,
                        "supports_clock_stretching": True,
                        "supports_repeated_start": True,
                    },
                    "spi_config": None,
                    "uart_config": None,
                    "signals": [
                        {"name": "SDA", "direction": "bidirectional", "description": "Serial data"},
                        {"name": "SCL", "direction": "input", "description": "Clock"},
                    ],
                    "timing_constraints": [
                        {
                            "parameter": "SCL Clock Frequency",
                            "symbol": "fSCL",
                            "min": 0,
                            "typ": None,
                            "max": 400000,
                            "unit": "Hz",
                            "conditions": None,
                        }
                    ],
                    "command_set": [],
                    "notes": None,
                }
            ],
            "protocol_summary": {
                "total_interfaces": 1,
                "has_i2c": True,
                "has_spi": False,
                "has_uart": False,
                "primary_interface": "I2C",
            },
        }

        # Should not raise
        jsonschema.validate(sample, schema)

    def test_unknown_i2c_address_configurable_validates_against_schema(self):
        """Unknown address configurability is represented as null in checked-in exports."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = os.path.join(
            os.path.dirname(__file__),
            "schemas", "domains", "protocol.schema.json"
        )
        with open(schema_path) as f:
            schema = json.load(f)

        sample = {
            "interfaces": [
                {
                    "protocol_type": "I2C",
                    "role": "slave",
                    "instance_name": "I2C",
                    "i2c_config": {
                        "slave_address_hex": None,
                        "address_configurable": None,
                        "address_pins": [],
                        "address_bits": 7,
                        "max_clock_hz": None,
                        "supports_clock_stretching": None,
                        "supports_repeated_start": None,
                    },
                    "spi_config": None,
                    "uart_config": None,
                    "signals": [],
                    "timing_constraints": [],
                    "command_set": [],
                    "notes": None,
                }
            ],
            "protocol_summary": {
                "total_interfaces": 1,
                "has_i2c": True,
                "has_spi": False,
                "has_uart": False,
                "primary_interface": "I2C",
            },
        }

        jsonschema.validate(sample, schema)


# ─── Edge cases ─────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_interfaces_list(self):
        """Empty interfaces list should produce a warning and count=0."""
        ext = _make_extractor()
        data = {"interfaces": [], "protocol_summary": {}}
        result = ext.validate(data)
        assert result["protocol_interface_count"] == 0
        warnings = [
            i for i in result["protocol_validation"]
            if "No interfaces found" in i["message"]
        ]
        assert len(warnings) == 1

    def test_null_configs(self):
        """Null config values should not crash validation."""
        ext = _make_extractor()
        iface = {
            "protocol_type": "I2C",
            "role": "slave",
            "instance_name": None,
            "i2c_config": None,
            "spi_config": None,
            "uart_config": None,
            "signals": [{"name": "SDA", "direction": "bidirectional", "description": "data"}],
            "timing_constraints": [],
            "command_set": [],
            "notes": None,
        }
        data = _make_extraction(iface)
        result = ext.validate(data)
        # Should not crash; no I2C config errors since config is null
        assert result["protocol_interface_count"] == 1

    def test_error_in_extraction_result(self):
        """Extraction result with 'error' key should short-circuit validation."""
        ext = _make_extractor()
        data = {"error": "API timeout", "interfaces": []}
        result = ext.validate(data)
        assert result["protocol_interface_count"] == 0
        assert result["protocol_validation"] == []

    def test_interface_count_returned(self):
        """Validation should return correct interface count."""
        ext = _make_extractor()
        data = _make_extraction(
            _make_i2c_interface(),
            _make_spi_interface(),
            _make_uart_interface(),
        )
        result = ext.validate(data)
        assert result["protocol_interface_count"] == 3

    def test_build_summary_helper(self):
        """_build_summary should correctly detect protocol types."""
        ext = _make_extractor()
        interfaces = [
            {"protocol_type": "I2C"},
            {"protocol_type": "SPI"},
            {"protocol_type": "PMBus"},
        ]
        summary = ext._build_summary(interfaces)
        assert summary["total_interfaces"] == 3
        assert summary["has_i2c"] is True  # I2C and PMBus count
        assert summary["has_spi"] is True
        assert summary["has_uart"] is False
        assert summary["primary_interface"] == "I2C"

    def test_build_summary_empty(self):
        """_build_summary with empty list should return zeros/False."""
        ext = _make_extractor()
        summary = ext._build_summary([])
        assert summary["total_interfaces"] == 0
        assert summary["has_i2c"] is False
        assert summary["has_spi"] is False
        assert summary["has_uart"] is False
        assert summary["primary_interface"] is None

    def test_smbus_counts_as_i2c(self):
        """SMBus protocol should set has_i2c to True in summary."""
        ext = _make_extractor()
        interfaces = [{"protocol_type": "SMBus"}]
        summary = ext._build_summary(interfaces)
        assert summary["has_i2c"] is True
