"""Tests for the parametric extraction module.

Validates spec-type classification, operating conditions extraction,
validation logic, edge cases, schema compliance, framework integration,
and deduplication behavior.
"""
import json
import pytest
from pathlib import Path

from extractors.parametric import (
    ParametricExtractor,
    SPEC_TYPE_PATTERNS,
    VALID_SPEC_TYPES,
    _classify_spec_type,
    _has_numeric_value,
    _safe_num,
)
from extractors.base import BaseExtractor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_extractor() -> ParametricExtractor:
    """Create a ParametricExtractor with dummy constructor args."""
    return ParametricExtractor(
        client=None,
        model=None,
        pdf_path="/tmp/test.pdf",
        page_classification=[],
        is_fpga=False,
    )


def _make_param(
    parameter: str = "",
    symbol: str = "",
    raw_name: str = "",
    min_val=None,
    typ_val=None,
    max_val=None,
    unit: str | None = None,
    conditions: str | None = None,
) -> dict:
    """Build a parameter dict suitable for the parametric extractor."""
    d = {
        "parameter": parameter,
        "symbol": symbol,
        "raw_name": raw_name,
    }
    if min_val is not None:
        d["min"] = min_val
    if typ_val is not None:
        d["typ"] = typ_val
    if max_val is not None:
        d["max"] = max_val
    if unit is not None:
        d["unit"] = unit
    if conditions is not None:
        d["conditions"] = conditions
    return d


# ======================================================================
# Spec-type classification tests
# ======================================================================

class TestSpecTypeClassification:
    """Test each of the 17 spec_types with sample parameters."""

    def test_input_voltage_by_name(self):
        p = _make_param(parameter="Input Voltage Range", min_val=3.0, max_val=36.0)
        assert _classify_spec_type(p) == "input_voltage"

    def test_input_voltage_by_symbol(self):
        p = _make_param(symbol="VIN", min_val=3.0, max_val=36.0)
        assert _classify_spec_type(p) == "input_voltage"

    def test_input_voltage_vcc(self):
        p = _make_param(symbol="VCC", min_val=2.7, max_val=5.5)
        assert _classify_spec_type(p) == "input_voltage"

    def test_input_voltage_vdd(self):
        p = _make_param(symbol="VDD", min_val=1.6, max_val=3.6)
        assert _classify_spec_type(p) == "input_voltage"

    def test_output_voltage_by_name(self):
        p = _make_param(parameter="Output Voltage", min_val=0.8, max_val=5.0)
        assert _classify_spec_type(p) == "output_voltage"

    def test_output_voltage_by_symbol(self):
        p = _make_param(symbol="VOUT", min_val=0.8, max_val=5.0)
        assert _classify_spec_type(p) == "output_voltage"

    def test_output_current_by_name(self):
        p = _make_param(parameter="Output Current", max_val=3.0)
        assert _classify_spec_type(p) == "output_current"

    def test_output_current_by_symbol(self):
        p = _make_param(symbol="IOUT", max_val=3.0)
        assert _classify_spec_type(p) == "output_current"

    def test_quiescent_current(self):
        p = _make_param(parameter="Quiescent Current", typ_val=0.5)
        assert _classify_spec_type(p) == "quiescent_current"

    def test_quiescent_current_iq(self):
        p = _make_param(symbol="IQ", typ_val=0.5)
        assert _classify_spec_type(p) == "quiescent_current"

    def test_switching_frequency(self):
        p = _make_param(parameter="Switch Freq", typ_val=500.0, unit="kHz")
        assert _classify_spec_type(p) == "switching_frequency"

    def test_switching_frequency_fsw(self):
        p = _make_param(symbol="fSW", typ_val=500.0)
        assert _classify_spec_type(p) == "switching_frequency"

    def test_dropout_voltage(self):
        p = _make_param(parameter="Drop Out Voltage", max_val=0.3)
        assert _classify_spec_type(p) == "dropout_voltage"

    def test_dropout_voltage_vdo(self):
        p = _make_param(symbol="VDO", max_val=0.3)
        assert _classify_spec_type(p) == "dropout_voltage"

    def test_accuracy(self):
        p = _make_param(parameter="Voltage Accuracy", typ_val=1.0, unit="%")
        assert _classify_spec_type(p) == "accuracy"

    def test_accuracy_regulation(self):
        p = _make_param(parameter="Line Regulation", typ_val=0.01, unit="%/V")
        assert _classify_spec_type(p) == "accuracy"

    def test_efficiency(self):
        p = _make_param(parameter="Efficiency", typ_val=92.0, unit="%")
        assert _classify_spec_type(p) == "efficiency"

    def test_bandwidth(self):
        p = _make_param(parameter="Unity Gain Bandwidth", typ_val=10.0, unit="MHz")
        assert _classify_spec_type(p) == "bandwidth"

    def test_bandwidth_gbw(self):
        p = _make_param(symbol="GBW", typ_val=10.0)
        assert _classify_spec_type(p) == "bandwidth"

    def test_slew_rate(self):
        p = _make_param(parameter="Slew Rate", typ_val=13.0, unit="V/us")
        assert _classify_spec_type(p) == "slew_rate"

    def test_slew_rate_sr(self):
        p = _make_param(symbol="SR", typ_val=13.0)
        assert _classify_spec_type(p) == "slew_rate"

    def test_input_offset(self):
        p = _make_param(parameter="Input Offset Voltage", typ_val=0.1, unit="mV")
        assert _classify_spec_type(p) == "input_offset"

    def test_input_offset_vos(self):
        p = _make_param(symbol="VOS", typ_val=0.1)
        assert _classify_spec_type(p) == "input_offset"

    def test_supply_current(self):
        p = _make_param(parameter="Supply Current", typ_val=1.5, unit="mA")
        assert _classify_spec_type(p) == "supply_current"

    def test_supply_current_icc(self):
        p = _make_param(symbol="ICC", typ_val=1.5)
        assert _classify_spec_type(p) == "supply_current"

    def test_leakage_current(self):
        p = _make_param(parameter="Leakage Current", max_val=1.0, unit="uA")
        assert _classify_spec_type(p) == "leakage_current"

    def test_on_resistance(self):
        p = _make_param(parameter="On Resistance", typ_val=0.1, unit="Ohm")
        assert _classify_spec_type(p) == "on_resistance"

    def test_on_resistance_rds(self):
        p = _make_param(symbol="RDS", typ_val=0.1)
        assert _classify_spec_type(p) == "on_resistance"

    def test_propagation_delay(self):
        p = _make_param(parameter="Propagation Delay", typ_val=5.0, unit="ns")
        assert _classify_spec_type(p) == "propagation_delay"

    def test_propagation_delay_tpd(self):
        p = _make_param(symbol="tPD", typ_val=5.0)
        assert _classify_spec_type(p) == "propagation_delay"

    def test_power_dissipation(self):
        p = _make_param(parameter="Power Dissipation", max_val=1.0, unit="W")
        assert _classify_spec_type(p) == "power_dissipation"

    def test_power_dissipation_pd(self):
        p = _make_param(symbol="PD", max_val=1.0)
        assert _classify_spec_type(p) == "power_dissipation"

    def test_other_unrecognized(self):
        p = _make_param(parameter="Something Unusual", typ_val=42.0)
        assert _classify_spec_type(p) == "other"


# ======================================================================
# Operating conditions extraction
# ======================================================================

class TestOperatingConditions:
    """Test vin/vout/iout/temp range extraction."""

    def test_vin_range(self):
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                _make_param(parameter="Input Voltage Range", symbol="VIN", min_val=3.0, max_val=36.0, unit="V"),
            ],
        }
        result = ext.extract(source)
        oc = result["operating_conditions"]
        assert oc["vin_min"] == 3.0
        assert oc["vin_max"] == 36.0

    def test_vout_range(self):
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                _make_param(parameter="Output Voltage", symbol="VOUT", min_val=0.8, max_val=5.0, unit="V"),
            ],
        }
        result = ext.extract(source)
        oc = result["operating_conditions"]
        assert oc["vout_min"] == 0.8
        assert oc["vout_max"] == 5.0

    def test_iout_max(self):
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                _make_param(parameter="Output Current", symbol="IOUT", max_val=3.0, unit="A"),
            ],
        }
        result = ext.extract(source)
        oc = result["operating_conditions"]
        assert oc["iout_max"] == 3.0

    def test_temp_range(self):
        ext = _make_extractor()
        source = {
            "absolute_maximum_ratings": [
                _make_param(parameter="Operating Temperature", min_val=-40.0, max_val=125.0, unit="C"),
            ],
        }
        result = ext.extract(source)
        oc = result["operating_conditions"]
        assert oc["temp_min"] == -40.0
        assert oc["temp_max"] == 125.0

    def test_temp_unit_defaults_to_c(self):
        ext = _make_extractor()
        source = {"electrical_characteristics": []}
        result = ext.extract(source)
        assert result["operating_conditions"]["temp_unit"] == "C"

    def test_multiple_vin_sources_picks_extremes(self):
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                _make_param(parameter="Input Voltage", symbol="VIN", min_val=5.0, max_val=20.0),
            ],
            "absolute_maximum_ratings": [
                _make_param(parameter="Supply Voltage", symbol="VIN", min_val=3.0, max_val=40.0),
            ],
        }
        result = ext.extract(source)
        oc = result["operating_conditions"]
        assert oc["vin_min"] == 3.0
        assert oc["vin_max"] == 40.0


# ======================================================================
# Validation tests
# ======================================================================

class TestValidation:
    """Test validation: spec_type enum, vin/temp warnings, etc."""

    def test_valid_spec_types_pass(self):
        ext = _make_extractor()
        result = {
            "key_specs": [
                {"name": "VIN", "spec_type": "input_voltage"},
                {"name": "VOUT", "spec_type": "output_voltage"},
            ],
            "operating_conditions": {},
            "parametric_summary": {"category": "LDO"},
        }
        report = ext.validate(result)
        errors = [i for i in report["parametric_validation"] if i["level"] == "error"]
        assert len(errors) == 0

    def test_invalid_spec_type_raises_error(self):
        ext = _make_extractor()
        result = {
            "key_specs": [
                {"name": "FOO", "spec_type": "nonexistent_type"},
            ],
            "operating_conditions": {},
            "parametric_summary": {"category": "LDO"},
        }
        report = ext.validate(result)
        errors = [i for i in report["parametric_validation"] if i["level"] == "error"]
        assert len(errors) == 1
        assert "nonexistent_type" in errors[0]["message"]

    def test_vin_min_gt_max_warning(self):
        ext = _make_extractor()
        result = {
            "key_specs": [{"name": "VIN", "spec_type": "input_voltage"}],
            "operating_conditions": {"vin_min": 10.0, "vin_max": 5.0},
            "parametric_summary": {},
        }
        report = ext.validate(result)
        warnings = [i for i in report["parametric_validation"] if i["level"] == "warning"]
        vin_warnings = [w for w in warnings if "vin_min" in w["message"]]
        assert len(vin_warnings) == 1

    def test_vout_min_gt_max_warning(self):
        ext = _make_extractor()
        result = {
            "key_specs": [{"name": "VOUT", "spec_type": "output_voltage"}],
            "operating_conditions": {"vout_min": 5.0, "vout_max": 2.0},
            "parametric_summary": {},
        }
        report = ext.validate(result)
        warnings = [i for i in report["parametric_validation"] if i["level"] == "warning"]
        vout_warnings = [w for w in warnings if "vout_min" in w["message"]]
        assert len(vout_warnings) == 1

    def test_temp_range_warning(self):
        ext = _make_extractor()
        result = {
            "key_specs": [{"name": "T", "spec_type": "other"}],
            "operating_conditions": {"temp_min": -200.0, "temp_max": 500.0},
            "parametric_summary": {},
        }
        report = ext.validate(result)
        warnings = [i for i in report["parametric_validation"] if i["level"] == "warning"]
        temp_warnings = [w for w in warnings if "500 degrees" in w["message"]]
        assert len(temp_warnings) == 1

    def test_temp_min_gt_max_warning(self):
        ext = _make_extractor()
        result = {
            "key_specs": [{"name": "T", "spec_type": "other"}],
            "operating_conditions": {"temp_min": 125.0, "temp_max": -40.0},
            "parametric_summary": {},
        }
        report = ext.validate(result)
        warnings = [i for i in report["parametric_validation"] if i["level"] == "warning"]
        temp_warnings = [w for w in warnings if "temp_min" in w["message"]]
        assert len(temp_warnings) >= 1

    def test_no_key_specs_warning(self):
        ext = _make_extractor()
        result = {
            "key_specs": [],
            "operating_conditions": {},
            "parametric_summary": {"category": "Unknown"},
        }
        report = ext.validate(result)
        warnings = [i for i in report["parametric_validation"] if i["level"] == "warning"]
        no_specs_warn = [w for w in warnings if "No key specs" in w["message"]]
        assert len(no_specs_warn) == 1


# ======================================================================
# Edge cases
# ======================================================================

class TestEdgeCases:
    """Test empty input, no numeric values, missing fields."""

    def test_empty_input(self):
        ext = _make_extractor()
        result = ext.extract({})
        assert result["key_specs"] == []
        assert result["parametric_summary"]["total_key_specs"] == 0

    def test_none_input(self):
        ext = _make_extractor()
        result = ext.extract(None)
        assert result["key_specs"] == []

    def test_string_input(self):
        ext = _make_extractor()
        result = ext.extract("not a dict")
        assert result["key_specs"] == []

    def test_no_numeric_values_skipped(self):
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                {"parameter": "Input Voltage", "symbol": "VIN", "unit": "V"},
            ],
        }
        result = ext.extract(source)
        assert result["key_specs"] == []

    def test_missing_parameter_name_skipped(self):
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                {"symbol": "VIN", "min": 3.0, "max": 36.0},
            ],
        }
        result = ext.extract(source)
        # parameter name is empty string (missing), so entry should be skipped
        assert len(result["key_specs"]) == 0

    def test_only_typ_value_included(self):
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                _make_param(parameter="Quiescent Current", symbol="IQ", typ_val=0.5, unit="uA"),
            ],
        }
        result = ext.extract(source)
        assert len(result["key_specs"]) == 1
        assert result["key_specs"][0]["typ"] == 0.5

    def test_empty_arrays(self):
        ext = _make_extractor()
        source = {
            "absolute_maximum_ratings": [],
            "electrical_characteristics": [],
        }
        result = ext.extract(source)
        assert result["key_specs"] == []
        assert result["parametric_summary"]["total_key_specs"] == 0


# ======================================================================
# Schema compliance
# ======================================================================

class TestSchemaCompliance:
    """Validate sample output against parametric.schema.json."""

    @pytest.fixture
    def schema(self):
        schema_path = Path(__file__).parent / "schemas" / "domains" / "parametric.schema.json"
        return json.loads(schema_path.read_text())

    def test_sample_output_structure(self, schema):
        """Verify that extractor output matches schema top-level structure."""
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                _make_param(parameter="Input Voltage Range", symbol="VIN", min_val=3.0, max_val=36.0, unit="V"),
                _make_param(parameter="Output Current", symbol="IOUT", max_val=3.0, unit="A"),
            ],
            "absolute_maximum_ratings": [
                _make_param(parameter="Operating Temperature", min_val=-40.0, max_val=125.0, unit="C"),
            ],
        }
        result = ext.extract(source)

        # top-level keys
        assert "key_specs" in result
        assert "operating_conditions" in result
        assert "parametric_summary" in result

        # key_specs is array of objects
        assert isinstance(result["key_specs"], list)
        for ks in result["key_specs"]:
            assert "name" in ks
            assert "spec_type" in ks
            assert ks["spec_type"] in VALID_SPEC_TYPES

        # operating_conditions has expected keys
        oc = result["operating_conditions"]
        for key in ("vin_min", "vin_max", "vout_min", "vout_max", "iout_max", "temp_min", "temp_max", "temp_unit"):
            assert key in oc

        # parametric_summary has expected keys
        ps = result["parametric_summary"]
        for key in ("category", "total_key_specs", "has_voltage_specs", "has_current_specs", "has_frequency_specs", "packages_available"):
            assert key in ps

    def test_key_spec_fields_match_schema(self, schema):
        """Key spec entries should have fields matching the schema definition."""
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                _make_param(
                    parameter="Output Current",
                    symbol="IOUT",
                    max_val=3.0,
                    unit="A",
                    conditions="VIN = 12V",
                ),
            ],
        }
        result = ext.extract(source)
        ks = result["key_specs"][0]

        # Required fields from schema
        assert "name" in ks
        assert "spec_type" in ks

        # Enum check
        allowed = schema["$defs"]["key_spec"]["properties"]["spec_type"]["enum"]
        assert ks["spec_type"] in allowed

    def test_additionalProperties_false_top_level(self, schema):
        """Schema sets additionalProperties: false at top level."""
        ext = _make_extractor()
        source = {"electrical_characteristics": []}
        result = ext.extract(source)

        # Only allowed top-level properties per schema
        allowed_keys = set(schema.get("properties", {}).keys())
        for key in result:
            assert key in allowed_keys, f"Unexpected key '{key}' in output"


# ======================================================================
# Framework integration tests
# ======================================================================

class TestFrameworkIntegration:
    """ParametricExtractor inherits BaseExtractor, DOMAIN_NAME, select_pages."""

    def test_inherits_base_extractor(self):
        assert issubclass(ParametricExtractor, BaseExtractor)

    def test_domain_name(self):
        assert ParametricExtractor.DOMAIN_NAME == "parametric"

    def test_select_pages_returns_empty(self):
        ext = _make_extractor()
        assert ext.select_pages() == []

    def test_constructor_stores_params(self):
        ext = ParametricExtractor(
            client="c",
            model="m",
            pdf_path="/p",
            page_classification=[1, 2],
            is_fpga=True,
        )
        assert ext.client == "c"
        assert ext.model == "m"
        assert ext.pdf_path == "/p"
        assert ext.page_classification == [1, 2]
        assert ext.is_fpga is True

    def test_has_required_methods(self):
        for method in ("select_pages", "extract", "validate"):
            assert hasattr(ParametricExtractor, method)

    def test_registered_in_registry(self):
        from extractors import EXTRACTOR_REGISTRY
        assert ParametricExtractor in EXTRACTOR_REGISTRY

    def test_registry_position(self):
        from extractors import EXTRACTOR_REGISTRY
        # ParametricExtractor should be 8th (index 7)
        assert EXTRACTOR_REGISTRY[7] is ParametricExtractor


# ======================================================================
# Deduplication tests
# ======================================================================

class TestDeduplication:
    """Verify duplicate parameters are removed."""

    def test_exact_duplicates_removed(self):
        ext = _make_extractor()
        param = _make_param(parameter="Input Voltage", symbol="VIN", min_val=3.0, max_val=36.0, unit="V")
        source = {
            "electrical_characteristics": [param, param.copy()],
        }
        result = ext.extract(source)
        vin_specs = [ks for ks in result["key_specs"] if ks["name"] == "Input Voltage"]
        assert len(vin_specs) == 1

    def test_different_values_not_deduped(self):
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                _make_param(parameter="Input Voltage", symbol="VIN", min_val=3.0, max_val=20.0),
                _make_param(parameter="Input Voltage", symbol="VIN", min_val=3.0, max_val=36.0),
            ],
        }
        result = ext.extract(source)
        vin_specs = [ks for ks in result["key_specs"] if ks["name"] == "Input Voltage"]
        assert len(vin_specs) == 2

    def test_cross_section_dedup(self):
        """Same parameter in both AMR and EC should be deduped."""
        ext = _make_extractor()
        param = _make_param(parameter="Input Voltage", symbol="VIN", min_val=3.0, max_val=36.0)
        source = {
            "absolute_maximum_ratings": [param],
            "electrical_characteristics": [param.copy()],
        }
        result = ext.extract(source)
        vin_specs = [ks for ks in result["key_specs"] if ks["name"] == "Input Voltage"]
        assert len(vin_specs) == 1


# ======================================================================
# Summary tests
# ======================================================================

class TestSummary:
    """Test parametric_summary field generation."""

    def test_has_voltage_specs_true(self):
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                _make_param(parameter="Input Voltage", symbol="VIN", min_val=3.0, max_val=36.0),
            ],
        }
        result = ext.extract(source)
        assert result["parametric_summary"]["has_voltage_specs"] is True

    def test_has_current_specs_true(self):
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                _make_param(parameter="Output Current", symbol="IOUT", max_val=3.0),
            ],
        }
        result = ext.extract(source)
        assert result["parametric_summary"]["has_current_specs"] is True

    def test_has_frequency_specs_true(self):
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                _make_param(parameter="Switching Frequency", symbol="fSW", typ_val=500.0),
            ],
        }
        result = ext.extract(source)
        assert result["parametric_summary"]["has_frequency_specs"] is True

    def test_total_key_specs_count(self):
        ext = _make_extractor()
        source = {
            "electrical_characteristics": [
                _make_param(parameter="Input Voltage", symbol="VIN", min_val=3.0, max_val=36.0),
                _make_param(parameter="Output Current", symbol="IOUT", max_val=3.0),
                _make_param(parameter="Quiescent Current", symbol="IQ", typ_val=0.5),
            ],
        }
        result = ext.extract(source)
        assert result["parametric_summary"]["total_key_specs"] == 3

    def test_packages_available_empty_by_default(self):
        ext = _make_extractor()
        source = {"electrical_characteristics": []}
        result = ext.extract(source)
        assert result["parametric_summary"]["packages_available"] == []


# ======================================================================
# Helper function tests
# ======================================================================

class TestHelpers:
    """Test module-level helper functions."""

    def test_has_numeric_value_with_min(self):
        assert _has_numeric_value({"min": 3.0}) is True

    def test_has_numeric_value_with_typ(self):
        assert _has_numeric_value({"typ": 1.5}) is True

    def test_has_numeric_value_with_max(self):
        assert _has_numeric_value({"max": 36.0}) is True

    def test_has_numeric_value_none(self):
        assert _has_numeric_value({}) is False

    def test_has_numeric_value_string(self):
        assert _has_numeric_value({"min": "3.0"}) is False

    def test_safe_num_int(self):
        assert _safe_num(42) == 42.0

    def test_safe_num_float(self):
        assert _safe_num(3.14) == 3.14

    def test_safe_num_none(self):
        assert _safe_num(None) is None

    def test_safe_num_string(self):
        assert _safe_num("abc") is None
