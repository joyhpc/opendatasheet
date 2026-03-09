"""Tests for the power sequence extraction module.

Tests the PowerSequenceExtractor's validation logic, schema compliance, and
framework integration. Does NOT require Gemini API access -- tests use
synthetic data that mimics API output.
"""
import pytest
import json
from pathlib import Path
from extractors.power_sequence import (
    PowerSequenceExtractor,
    _check_sequence_order_gaps,
    _check_contradictory_rules,
    VALID_STARTUP_CATEGORIES,
    VALID_PROTECTION_CATEGORIES,
    VALID_SEQUENCING_TYPES,
)


# ─── Helper function tests ───────────────────────────────────────────


class TestCheckSequenceOrderGaps:
    def test_no_gaps(self):
        items = [
            {"stage_name": "A", "stage_order": 1},
            {"stage_name": "B", "stage_order": 2},
            {"stage_name": "C", "stage_order": 3},
        ]
        issues = _check_sequence_order_gaps(items, "stage_order")
        assert len(issues) == 0

    def test_gap_detected(self):
        items = [
            {"stage_name": "A", "stage_order": 1},
            {"stage_name": "C", "stage_order": 3},
        ]
        issues = _check_sequence_order_gaps(items, "stage_order")
        assert any("gaps" in i["message"] or "don't start at 1" in i["message"] for i in issues)

    def test_negative_order(self):
        items = [
            {"stage_name": "A", "stage_order": -1},
        ]
        issues = _check_sequence_order_gaps(items, "stage_order")
        assert any("positive integer" in i["message"] for i in issues)

    def test_null_orders_ok(self):
        items = [
            {"stage_name": "A", "stage_order": None},
            {"stage_name": "B", "stage_order": None},
        ]
        issues = _check_sequence_order_gaps(items, "stage_order")
        assert len(issues) == 0


class TestCheckContradictoryRules:
    def test_no_contradiction(self):
        rules = [
            {"rail_before": "VCC", "rail_after": "VDD_IO"},
            {"rail_before": "VDD_IO", "rail_after": "VOUT"},
        ]
        issues = _check_contradictory_rules(rules)
        assert len(issues) == 0

    def test_contradictory_detected(self):
        rules = [
            {"rail_before": "VCC", "rail_after": "VDD_IO"},
            {"rail_before": "VDD_IO", "rail_after": "VCC"},
        ]
        issues = _check_contradictory_rules(rules)
        assert any("Contradictory" in i["message"] for i in issues)


# ─── Validation logic tests ──────────────────────────────────────────


def _make_extractor():
    """Create a PowerSequenceExtractor with dummy init params (no API needed)."""
    return PowerSequenceExtractor(
        client=None, model=None, pdf_path="/tmp/fake.pdf",
        page_classification=[], is_fpga=False,
    )


class TestPowerSequenceValidation:
    def test_valid_power_sequence_data(self):
        ext = _make_extractor()
        data = {
            "power_stages": [
                {
                    "stage_name": "VIN applied",
                    "stage_order": 1,
                    "description": "Input voltage applied",
                    "trigger": "External supply connected",
                    "duration": None,
                    "associated_rail": "VIN",
                },
                {
                    "stage_name": "EN high",
                    "stage_order": 2,
                    "description": "Enable pin driven high",
                    "trigger": "EN pin exceeds threshold",
                    "duration": None,
                    "associated_rail": None,
                },
            ],
            "power_rails": [
                {
                    "name": "VOUT",
                    "nominal_voltage": 3.3,
                    "voltage_range": {"min": 3.2, "max": 3.4, "unit": "V"},
                    "sequence_order": 1,
                    "ramp_rate": None,
                    "max_current": None,
                },
            ],
            "startup_parameters": [
                {
                    "parameter": "Soft-Start Time",
                    "category": "soft_start_time",
                    "min": None,
                    "typ": 2.0,
                    "max": 5.0,
                    "unit": "ms",
                    "conditions": None,
                },
            ],
            "protection_thresholds": [
                {
                    "parameter": "UVLO Threshold Rising",
                    "category": "UVLO_rising",
                    "min": 2.5,
                    "typ": 2.7,
                    "max": 2.9,
                    "unit": "V",
                    "conditions": None,
                },
            ],
            "sequencing_rules": [],
            "power_sequence_summary": {
                "has_soft_start": True,
                "has_power_good": False,
                "has_enable_pin": True,
                "has_uvlo": True,
                "rail_count": 1,
                "sequencing_type": "fixed",
            },
        }
        result = ext.validate(data)
        assert result["stage_count"] == 2
        assert result["rail_count"] == 1
        assert result["startup_param_count"] == 1
        assert result["protection_threshold_count"] == 1
        assert len(result["power_sequence_validation_issues"]) == 0

    def test_invalid_startup_category_caught(self):
        ext = _make_extractor()
        data = {
            "power_stages": [],
            "power_rails": [],
            "startup_parameters": [
                {
                    "parameter": "Bad Param",
                    "category": "bogus_startup_category",
                    "min": None,
                    "typ": 1.0,
                    "max": None,
                    "unit": "ms",
                    "conditions": None,
                },
            ],
            "protection_thresholds": [],
            "sequencing_rules": [],
            "power_sequence_summary": {},
        }
        result = ext.validate(data)
        issues = result["power_sequence_validation_issues"]
        assert any("invalid category" in i["message"] for i in issues)

    def test_invalid_protection_category_caught(self):
        ext = _make_extractor()
        data = {
            "power_stages": [],
            "power_rails": [],
            "startup_parameters": [],
            "protection_thresholds": [
                {
                    "parameter": "Bad Threshold",
                    "category": "bogus_protection_category",
                    "min": None,
                    "typ": 5.0,
                    "max": None,
                    "unit": "V",
                    "conditions": None,
                },
            ],
            "sequencing_rules": [],
            "power_sequence_summary": {},
        }
        result = ext.validate(data)
        issues = result["power_sequence_validation_issues"]
        assert any("invalid category" in i["message"] for i in issues)

    def test_sequence_order_gaps_detected(self):
        ext = _make_extractor()
        data = {
            "power_stages": [
                {"stage_name": "A", "stage_order": 1},
                {"stage_name": "C", "stage_order": 3},
            ],
            "power_rails": [],
            "startup_parameters": [],
            "protection_thresholds": [],
            "sequencing_rules": [],
            "power_sequence_summary": {},
        }
        result = ext.validate(data)
        issues = result["power_sequence_validation_issues"]
        assert any("gaps" in i["message"] or "don't start at 1" in i["message"] for i in issues)

    def test_contradictory_rules_caught(self):
        ext = _make_extractor()
        data = {
            "power_stages": [],
            "power_rails": [],
            "startup_parameters": [],
            "protection_thresholds": [],
            "sequencing_rules": [
                {"rail_before": "VCC", "rail_after": "VDD_IO"},
                {"rail_before": "VDD_IO", "rail_after": "VCC"},
            ],
            "power_sequence_summary": {},
        }
        result = ext.validate(data)
        issues = result["power_sequence_validation_issues"]
        assert any("Contradictory" in i["message"] for i in issues)

    def test_uvlo_threshold_sanity_warning(self):
        """UVLO typ > 100V should trigger a warning."""
        ext = _make_extractor()
        data = {
            "power_stages": [],
            "power_rails": [],
            "startup_parameters": [],
            "protection_thresholds": [
                {
                    "parameter": "UVLO Rising",
                    "category": "UVLO_rising",
                    "min": None,
                    "typ": 150.0,
                    "max": None,
                    "unit": "V",
                    "conditions": None,
                },
            ],
            "sequencing_rules": [],
            "power_sequence_summary": {},
        }
        result = ext.validate(data)
        issues = result["power_sequence_validation_issues"]
        assert any("UVLO" in i["message"] and "outside typical range" in i["message"] for i in issues)

    def test_otp_threshold_sanity_warning(self):
        """OTP typ > 200C should trigger a warning."""
        ext = _make_extractor()
        data = {
            "power_stages": [],
            "power_rails": [],
            "startup_parameters": [],
            "protection_thresholds": [
                {
                    "parameter": "Over-Temperature Protection",
                    "category": "OTP",
                    "min": None,
                    "typ": 250.0,
                    "max": None,
                    "unit": "°C",
                    "conditions": None,
                },
            ],
            "sequencing_rules": [],
            "power_sequence_summary": {},
        }
        result = ext.validate(data)
        issues = result["power_sequence_validation_issues"]
        assert any("OTP" in i["message"] and "outside typical range" in i["message"] for i in issues)

    def test_error_result_returns_no_issues(self):
        ext = _make_extractor()
        data = {"error": "API failed"}
        result = ext.validate(data)
        assert result["stage_count"] == 0
        assert len(result["power_sequence_validation_issues"]) == 0


# ─── Schema compliance tests ─────────────────────────────────────────


class TestPowerSequenceSchemaCompliance:
    def test_schema_file_exists(self):
        schema_path = Path(__file__).parent / "schemas" / "domains" / "power_sequence.schema.json"
        assert schema_path.exists(), f"power_sequence.schema.json not found at {schema_path}"

    def test_schema_is_valid_json(self):
        schema_path = Path(__file__).parent / "schemas" / "domains" / "power_sequence.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)
        assert "$schema" in schema
        assert "properties" in schema

    def test_valid_data_validates_against_schema(self):
        """Validate synthetic power sequence data against the schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = Path(__file__).parent / "schemas" / "domains" / "power_sequence.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        valid_data = {
            "power_stages": [
                {
                    "stage_name": "VIN applied",
                    "stage_order": 1,
                    "description": "Input voltage applied",
                    "trigger": "External supply",
                    "associated_rail": "VIN",
                },
            ],
            "power_rails": [
                {
                    "name": "VOUT",
                    "nominal_voltage": 3.3,
                    "sequence_order": 1,
                },
            ],
            "startup_parameters": [
                {
                    "parameter": "Soft-Start Time",
                    "category": "soft_start_time",
                    "min": None,
                    "typ": 2.0,
                    "max": 5.0,
                    "unit": "ms",
                    "conditions": None,
                },
            ],
            "protection_thresholds": [
                {
                    "parameter": "UVLO Rising",
                    "category": "UVLO_rising",
                    "min": 2.5,
                    "typ": 2.7,
                    "max": 2.9,
                    "unit": "V",
                    "conditions": None,
                },
            ],
            "sequencing_rules": [],
            "power_sequence_summary": {
                "has_soft_start": True,
                "has_power_good": False,
                "has_enable_pin": True,
                "has_uvlo": True,
                "rail_count": 1,
                "sequencing_type": "fixed",
            },
        }
        # Should not raise
        jsonschema.validate(instance=valid_data, schema=schema)


# ─── Extractor framework tests ───────────────────────────────────────


class TestPowerSequenceExtractorFramework:
    def test_domain_name(self):
        assert PowerSequenceExtractor.DOMAIN_NAME == "power_sequence"

    def test_inherits_base_extractor(self):
        from extractors.base import BaseExtractor
        assert issubclass(PowerSequenceExtractor, BaseExtractor)

    def test_select_pages_empty_classification(self):
        ext = _make_extractor()
        assert ext.select_pages() == []

    def test_has_required_methods(self):
        for method in ["select_pages", "extract", "validate"]:
            assert hasattr(PowerSequenceExtractor, method), f"Missing method '{method}'"
