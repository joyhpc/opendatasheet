"""Tests for the timing extraction module.

Tests the TimingExtractor's validation logic, schema compliance, and
framework integration. Does NOT require Gemini API access -- tests use
synthetic data that mimics API output.
"""
import pytest
import json
from pathlib import Path
from extractors.timing import (
    TimingExtractor,
    _check_monotonicity,
    _is_valid_timing_unit,
    VALID_CATEGORIES,
    VALID_TIMING_UNITS,
)


# ─── Helper function tests ───────────────────────────────────────────


class TestCheckMonotonicity:
    def test_valid_ascending(self):
        assert _check_monotonicity(1.0, 2.0, 3.0) is True

    def test_valid_equal(self):
        assert _check_monotonicity(2.0, 2.0, 2.0) is True

    def test_valid_min_max_only(self):
        assert _check_monotonicity(1.0, None, 3.0) is True

    def test_invalid_min_greater_than_max(self):
        assert _check_monotonicity(5.0, None, 3.0) is False

    def test_invalid_min_greater_than_typ(self):
        assert _check_monotonicity(5.0, 3.0, None) is False

    def test_invalid_typ_greater_than_max(self):
        assert _check_monotonicity(None, 5.0, 3.0) is False

    def test_single_value_returns_none(self):
        assert _check_monotonicity(1.0, None, None) is None

    def test_all_none_returns_none(self):
        assert _check_monotonicity(None, None, None) is None


class TestIsValidTimingUnit:
    def test_valid_units(self):
        for unit in ["ns", "ps", "us", "ms", "s", "Hz", "kHz", "MHz", "GHz", "%"]:
            assert _is_valid_timing_unit(unit) is True, f"Expected '{unit}' to be valid"

    def test_none_is_acceptable(self):
        assert _is_valid_timing_unit(None) is True

    def test_empty_string_is_acceptable(self):
        assert _is_valid_timing_unit("") is True

    def test_invalid_unit(self):
        assert _is_valid_timing_unit("volts") is False
        assert _is_valid_timing_unit("dBm") is False
        assert _is_valid_timing_unit("Amperes") is False

    def test_case_insensitive(self):
        assert _is_valid_timing_unit("NS") is True
        assert _is_valid_timing_unit("mhz") is True


# ─── Validation logic tests ──────────────────────────────────────────


def _make_extractor():
    """Create a TimingExtractor with dummy init params (no API needed)."""
    return TimingExtractor(
        client=None, model=None, pdf_path="/tmp/fake.pdf",
        page_classification=[], is_fpga=False,
    )


class TestTimingValidation:
    def test_valid_timing_parameters(self):
        ext = _make_extractor()
        data = {
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
                    "load_conditions": "CL = 15pF",
                },
                {
                    "parameter": "Setup Time",
                    "symbol": "tsu",
                    "category": "setup_time",
                    "min": 5.0,
                    "typ": None,
                    "max": None,
                    "unit": "ns",
                    "conditions": "VCC = 3.3V",
                    "signal_from": "D",
                    "signal_to": "CLK",
                    "edge": "rising",
                    "load_conditions": None,
                },
            ],
            "timing_summary": {
                "total_parameters": 2,
                "categories": ["propagation_delay", "setup_time"],
                "has_timing_diagram": False,
            },
        }
        result = ext.validate(data)
        assert result["timing_parameter_count"] == 2
        assert len(result["timing_validation_issues"]) == 0

    def test_invalid_category_is_caught(self):
        ext = _make_extractor()
        data = {
            "timing_parameters": [
                {
                    "parameter": "Some Timing Param",
                    "category": "bogus_category",
                    "min": None,
                    "typ": 1.0,
                    "max": None,
                    "unit": "ns",
                },
            ],
        }
        result = ext.validate(data)
        issues = result["timing_validation_issues"]
        assert any("invalid category" in i["message"] for i in issues)

    def test_invalid_unit_is_caught(self):
        ext = _make_extractor()
        data = {
            "timing_parameters": [
                {
                    "parameter": "Delay",
                    "category": "propagation_delay",
                    "min": None,
                    "typ": 1.0,
                    "max": None,
                    "unit": "volts",
                },
            ],
        }
        result = ext.validate(data)
        issues = result["timing_validation_issues"]
        assert any("suspicious timing unit" in i["message"] for i in issues)

    def test_monotonicity_violation_caught(self):
        ext = _make_extractor()
        data = {
            "timing_parameters": [
                {
                    "parameter": "Rise Time",
                    "category": "rise_time",
                    "min": 10.0,
                    "typ": None,
                    "max": 5.0,
                    "unit": "ns",
                },
            ],
        }
        result = ext.validate(data)
        issues = result["timing_validation_issues"]
        assert any("not monotonic" in i["message"] for i in issues)

    def test_duplicate_parameters_detected(self):
        ext = _make_extractor()
        data = {
            "timing_parameters": [
                {
                    "parameter": "Setup Time",
                    "category": "setup_time",
                    "min": 5.0,
                    "typ": None,
                    "max": None,
                    "unit": "ns",
                    "conditions": "VCC = 3.3V",
                },
                {
                    "parameter": "Setup Time",
                    "category": "setup_time",
                    "min": 5.0,
                    "typ": None,
                    "max": None,
                    "unit": "ns",
                    "conditions": "VCC = 3.3V",
                },
            ],
        }
        result = ext.validate(data)
        issues = result["timing_validation_issues"]
        assert any("duplicate" in i["message"].lower() for i in issues)

    def test_invalid_edge_value_caught(self):
        ext = _make_extractor()
        data = {
            "timing_parameters": [
                {
                    "parameter": "Delay",
                    "category": "propagation_delay",
                    "min": None,
                    "typ": 1.0,
                    "max": None,
                    "unit": "ns",
                    "edge": "sideways",
                },
            ],
        }
        result = ext.validate(data)
        issues = result["timing_validation_issues"]
        assert any("invalid edge" in i["message"] for i in issues)

    def test_error_result_returns_no_issues(self):
        ext = _make_extractor()
        data = {"error": "API failed"}
        result = ext.validate(data)
        assert result["timing_parameter_count"] == 0
        assert len(result["timing_validation_issues"]) == 0

    def test_empty_parameters_gives_warning(self):
        ext = _make_extractor()
        data = {"timing_parameters": []}
        result = ext.validate(data)
        issues = result["timing_validation_issues"]
        assert any("No timing parameters found" in i["message"] for i in issues)


# ─── Schema compliance tests ─────────────────────────────────────────


class TestTimingSchemaCompliance:
    def test_schema_file_exists(self):
        schema_path = Path(__file__).parent / "schemas" / "domains" / "timing.schema.json"
        assert schema_path.exists(), f"timing.schema.json not found at {schema_path}"

    def test_schema_is_valid_json(self):
        schema_path = Path(__file__).parent / "schemas" / "domains" / "timing.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)
        assert "$schema" in schema
        assert "properties" in schema

    def test_valid_timing_data_validates_against_schema(self):
        """Validate synthetic timing data against timing.schema.json using jsonschema if available."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = Path(__file__).parent / "schemas" / "domains" / "timing.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        valid_data = {
            "timing_parameters": [
                {
                    "parameter": "Propagation Delay",
                    "symbol": "tPLH",
                    "category": "propagation_delay",
                    "min": 1.0,
                    "typ": 2.0,
                    "max": 3.0,
                    "unit": "ns",
                    "conditions": None,
                    "signal_from": "A",
                    "signal_to": "Y",
                    "edge": "rising",
                    "load_conditions": None,
                },
            ],
            "timing_summary": {
                "total_parameters": 1,
                "categories": ["propagation_delay"],
                "has_timing_diagram": False,
            },
        }
        # Should not raise
        jsonschema.validate(instance=valid_data, schema=schema)


# ─── Extractor framework tests ───────────────────────────────────────


class TestTimingExtractorFramework:
    def test_domain_name(self):
        assert TimingExtractor.DOMAIN_NAME == "timing"

    def test_inherits_base_extractor(self):
        from extractors.base import BaseExtractor
        assert issubclass(TimingExtractor, BaseExtractor)

    def test_select_pages_empty_classification(self):
        ext = _make_extractor()
        assert ext.select_pages() == []

    def test_has_required_methods(self):
        for method in ["select_pages", "extract", "validate"]:
            assert hasattr(TimingExtractor, method), f"Missing method '{method}'"
