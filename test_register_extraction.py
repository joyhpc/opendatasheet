"""Tests for the register extraction module.

Tests the RegisterExtractor's page selection, validation logic, and
schema compliance. Does NOT require Gemini API access -- tests use
synthetic data that mimics API output.
"""
import pytest
import json
from pathlib import Path
from extractors.register import RegisterExtractor, _is_valid_hex_string, _parse_bit_range, _check_bit_field_overlap


# Test hex validation
class TestHexValidation:
    def test_valid_hex(self):
        assert _is_valid_hex_string("0x00") == True
        assert _is_valid_hex_string("0xFF") == True
        assert _is_valid_hex_string("0x1A2B") == True

    def test_invalid_hex(self):
        assert _is_valid_hex_string("") == False
        assert _is_valid_hex_string("0xGG") == False
        assert _is_valid_hex_string("hello") == False

    def test_without_prefix(self):
        # Should handle both with and without 0x prefix
        assert _is_valid_hex_string("FF") == True
        assert _is_valid_hex_string("00") == True

    def test_non_string_input(self):
        assert _is_valid_hex_string(None) == False
        assert _is_valid_hex_string(42) == False

    def test_whitespace_only(self):
        assert _is_valid_hex_string("   ") == False

    def test_0x_prefix_only(self):
        assert _is_valid_hex_string("0x") == False


# Test bit range parsing
class TestBitRangeParsing:
    def test_single_bit(self):
        assert _parse_bit_range("3") == (3, 3)
        assert _parse_bit_range("0") == (0, 0)

    def test_range(self):
        assert _parse_bit_range("7:4") == (7, 4)
        assert _parse_bit_range("15:8") == (15, 8)

    def test_invalid(self):
        assert _parse_bit_range("abc") is None
        assert _parse_bit_range("") is None

    def test_non_string_input(self):
        assert _parse_bit_range(None) is None
        assert _parse_bit_range(42) is None

    def test_range_with_whitespace(self):
        assert _parse_bit_range(" 7 : 4 ") == (7, 4)

    def test_too_many_colons(self):
        assert _parse_bit_range("7:4:0") is None


# Test bit field overlap detection
class TestBitFieldOverlap:
    def test_no_overlap(self):
        fields = [
            {"bits": "7:4", "name": "HIGH"},
            {"bits": "3:0", "name": "LOW"},
        ]
        issues = _check_bit_field_overlap(fields, 8)
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 0

    def test_overlap(self):
        fields = [
            {"bits": "7:4", "name": "A"},
            {"bits": "5:2", "name": "B"},  # overlaps bits 4-5
        ]
        issues = _check_bit_field_overlap(fields, 8)
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) > 0

    def test_exceeds_register_size(self):
        fields = [
            {"bits": "15:8", "name": "HIGH"},
        ]
        issues = _check_bit_field_overlap(fields, 8)
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) > 0

    def test_empty_fields(self):
        issues = _check_bit_field_overlap([], 8)
        assert len(issues) == 0

    def test_unparseable_bits(self):
        fields = [
            {"bits": "abc", "name": "BAD"},
        ]
        issues = _check_bit_field_overlap(fields, 8)
        warnings = [i for i in issues if i["level"] == "warning"]
        assert len(warnings) > 0

    def test_single_bit_no_overlap(self):
        fields = [
            {"bits": "7", "name": "BIT7"},
            {"bits": "6", "name": "BIT6"},
            {"bits": "5", "name": "BIT5"},
        ]
        issues = _check_bit_field_overlap(fields, 8)
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 0

    def test_single_bit_overlap(self):
        fields = [
            {"bits": "7", "name": "A"},
            {"bits": "7", "name": "B"},
        ]
        issues = _check_bit_field_overlap(fields, 8)
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) > 0


# Test RegisterExtractor validation
class TestRegisterValidation:
    def _make_extractor(self):
        """Create a RegisterExtractor with dummy params (no API calls needed)."""
        return RegisterExtractor(
            client=None, model=None, pdf_path="",
            page_classification=[], is_fpga=False
        )

    def test_valid_registers(self):
        ext = self._make_extractor()
        data = {
            "registers": [
                {
                    "address": "0x00",
                    "name": "CONFIG",
                    "description": "Configuration register",
                    "size_bits": 8,
                    "access": "RW",
                    "reset_value": "0x00",
                    "fields": [
                        {"bits": "7:4", "name": "MODE", "access": "RW", "description": "Mode select", "reset_value": "0", "enum_values": None},
                        {"bits": "3:0", "name": "GAIN", "access": "RW", "description": "Gain select", "reset_value": "0", "enum_values": None},
                    ]
                }
            ],
            "register_map_summary": {
                "total_registers": 1,
                "address_range": "0x00-0x00",
                "bus_type": "I2C"
            }
        }
        result = ext.validate(data)
        issues = result.get("register_validation_issues", [])
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 0
        assert result["register_count"] == 1

    def test_duplicate_address(self):
        ext = self._make_extractor()
        data = {
            "registers": [
                {"address": "0x00", "name": "REG_A", "access": "RW", "fields": []},
                {"address": "0x00", "name": "REG_B", "access": "RW", "fields": []},
            ]
        }
        result = ext.validate(data)
        issues = result.get("register_validation_issues", [])
        warnings = [i for i in issues if i["level"] == "warning"]
        assert any("duplicate" in w["message"].lower() for w in warnings)

    def test_invalid_access_mode(self):
        ext = self._make_extractor()
        data = {
            "registers": [
                {"address": "0x00", "name": "REG_A", "access": "INVALID", "fields": []},
            ]
        }
        result = ext.validate(data)
        issues = result.get("register_validation_issues", [])
        errors = [i for i in issues if i["level"] == "error"]
        assert any("access" in e["message"].lower() for e in errors)

    def test_missing_address(self):
        ext = self._make_extractor()
        data = {
            "registers": [
                {"address": "", "name": "REG_A", "access": "RW", "fields": []},
            ]
        }
        result = ext.validate(data)
        issues = result.get("register_validation_issues", [])
        errors = [i for i in issues if i["level"] == "error"]
        assert any("missing" in e["message"].lower() for e in errors)

    def test_invalid_hex_address(self):
        ext = self._make_extractor()
        data = {
            "registers": [
                {"address": "0xZZ", "name": "REG_A", "access": "RW", "fields": []},
            ]
        }
        result = ext.validate(data)
        issues = result.get("register_validation_issues", [])
        errors = [i for i in issues if i["level"] == "error"]
        assert any("invalid hex" in e["message"].lower() for e in errors)

    def test_error_in_extraction_result(self):
        ext = self._make_extractor()
        data = {"error": "API failed"}
        result = ext.validate(data)
        assert result["register_count"] == 0

    def test_no_registers(self):
        ext = self._make_extractor()
        data = {"registers": []}
        result = ext.validate(data)
        issues = result.get("register_validation_issues", [])
        assert result["register_count"] == 0
        warnings = [i for i in issues if i["level"] == "warning"]
        assert any("no registers" in w["message"].lower() for w in warnings)

    def test_unusual_register_size(self):
        ext = self._make_extractor()
        data = {
            "registers": [
                {"address": "0x00", "name": "REG_A", "size_bits": 24, "access": "RW", "fields": []},
            ]
        }
        result = ext.validate(data)
        issues = result.get("register_validation_issues", [])
        warnings = [i for i in issues if i["level"] == "warning"]
        assert any("unusual" in w["message"].lower() or "size" in w["message"].lower() for w in warnings)

    def test_invalid_reset_value(self):
        ext = self._make_extractor()
        data = {
            "registers": [
                {"address": "0x00", "name": "REG_A", "access": "RW", "reset_value": "not_hex", "fields": []},
            ]
        }
        result = ext.validate(data)
        issues = result.get("register_validation_issues", [])
        warnings = [i for i in issues if i["level"] == "warning"]
        assert any("reset_value" in w["message"].lower() for w in warnings)

    def test_invalid_field_access_mode(self):
        ext = self._make_extractor()
        data = {
            "registers": [
                {
                    "address": "0x00",
                    "name": "REG_A",
                    "access": "RW",
                    "fields": [
                        {"bits": "7:0", "name": "DATA", "access": "BADMODE"},
                    ]
                },
            ]
        }
        result = ext.validate(data)
        issues = result.get("register_validation_issues", [])
        errors = [i for i in issues if i["level"] == "error"]
        assert any("access" in e["message"].lower() for e in errors)

    def test_unknown_bus_type(self):
        ext = self._make_extractor()
        data = {
            "registers": [
                {"address": "0x00", "name": "REG_A", "access": "RW", "fields": []},
            ],
            "register_map_summary": {
                "bus_type": "CAN"
            }
        }
        result = ext.validate(data)
        issues = result.get("register_validation_issues", [])
        warnings = [i for i in issues if i["level"] == "warning"]
        assert any("bus_type" in w["message"].lower() for w in warnings)

    def test_multiple_registers_all_valid(self):
        ext = self._make_extractor()
        data = {
            "registers": [
                {
                    "address": "0x00", "name": "CONFIG", "access": "RW",
                    "size_bits": 8, "reset_value": "0x00",
                    "fields": [
                        {"bits": "7:4", "name": "MODE", "access": "RW"},
                        {"bits": "3:0", "name": "GAIN", "access": "RW"},
                    ]
                },
                {
                    "address": "0x01", "name": "STATUS", "access": "RO",
                    "size_bits": 8, "reset_value": "0xFF",
                    "fields": [
                        {"bits": "7", "name": "READY", "access": "RO"},
                        {"bits": "6:0", "name": "COUNT", "access": "RO"},
                    ]
                },
            ],
            "register_map_summary": {
                "total_registers": 2,
                "address_range": "0x00-0x01",
                "bus_type": "SPI"
            }
        }
        result = ext.validate(data)
        issues = result.get("register_validation_issues", [])
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 0
        assert result["register_count"] == 2


# Test register schema compliance
class TestRegisterSchemaCompliance:
    def test_register_domain_schema_exists(self):
        schema_path = Path(__file__).parent / "schemas/domains/register.schema.json"
        assert schema_path.exists()
        schema = json.loads(schema_path.read_text())
        assert "$schema" in schema
        assert "registers" in schema.get("properties", {})

    def test_valid_register_data_against_schema(self):
        """Validate synthetic register data against the domain schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = Path(__file__).parent / "schemas/domains/register.schema.json"
        schema = json.loads(schema_path.read_text())

        data = {
            "registers": [
                {
                    "address": "0x00",
                    "name": "CONFIG",
                    "description": "Configuration register",
                    "size_bits": 8,
                    "access": "RW",
                    "reset_value": "0x00",
                    "fields": [
                        {
                            "bits": "7:4",
                            "name": "MODE",
                            "description": "Mode selection",
                            "access": "RW",
                            "reset_value": "0",
                            "enum_values": {"0": "Normal", "1": "Standby"}
                        }
                    ]
                }
            ],
            "register_map_summary": {
                "total_registers": 1,
                "address_range": "0x00-0x00",
                "bus_type": "I2C"
            }
        }

        jsonschema.validate(data, schema)  # Should not raise

    def test_minimal_register_data_against_schema(self):
        """Validate minimal register data (only required fields) against schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = Path(__file__).parent / "schemas/domains/register.schema.json"
        schema = json.loads(schema_path.read_text())

        data = {
            "registers": [
                {
                    "address": "0x00",
                    "name": "REG_A",
                }
            ]
        }

        jsonschema.validate(data, schema)  # Should not raise

    def test_invalid_register_data_rejected_by_schema(self):
        """Schema should reject data with invalid access mode."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = Path(__file__).parent / "schemas/domains/register.schema.json"
        schema = json.loads(schema_path.read_text())

        data = {
            "registers": [
                {
                    "address": "0x00",
                    "name": "REG_A",
                    "access": "BADMODE",
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(data, schema)

    def test_schema_rejects_extra_top_level_keys(self):
        """Schema has additionalProperties: false at top level."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = Path(__file__).parent / "schemas/domains/register.schema.json"
        schema = json.loads(schema_path.read_text())

        data = {
            "registers": [],
            "unexpected_key": "should fail"
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(data, schema)
