"""Tests for the package/mechanical extraction module.

Tests the PackageExtractor's validation logic, schema compliance, and
framework integration. Does NOT require Gemini API access -- tests use
synthetic data that mimics API output.
"""
import json
import pytest
from pathlib import Path
from extractors.package import (
    PackageExtractor,
    _check_dimension_minmax,
    _validate_pitch,
    _validate_reflow_temp,
    _validate_thermal_properties,
    _validate_moisture_sensitivity,
    _build_package_summary,
    VALID_PACKAGE_TYPES,
    _DIM_MIN_VALUE,
    _DIM_MAX_REASONABLE,
    _PITCH_MIN,
    _PITCH_MAX,
    _REFLOW_TEMP_MIN,
    _REFLOW_TEMP_MAX,
    _THETA_JA_MIN,
    _THETA_JA_MAX,
)
from extractors.base import BaseExtractor


# ─── Sample Data Builders ─────────────────────────────────────────────


def _make_package(**overrides):
    """Build a minimal valid package entry with optional overrides."""
    pkg = {
        "package_name": "VQFN-48",
        "package_type": "QFN",
        "pin_count": 48,
        "pitch_mm": 0.5,
        "body_length_mm": {"min": 6.9, "nom": 7.0, "max": 7.1},
        "body_width_mm": {"min": 6.9, "nom": 7.0, "max": 7.1},
        "body_height_mm": {"min": 0.8, "nom": 0.85, "max": 0.9},
        "lead_span_mm": None,
        "terminal_width_mm": None,
        "terminal_length_mm": None,
        "exposed_pad": {"present": True, "length_mm": 5.6, "width_mm": 5.6},
        "land_pattern": None,
        "thermal_properties": {"theta_ja_c_per_w": 28.5, "theta_jc_c_per_w": 4.3},
        "moisture_sensitivity": {"msl_level": "MSL 3", "peak_reflow_temp_c": 260},
        "reflow_profile": {"peak_temp_c": 260},
        "weight_mg": 120,
        "marking": None,
        "ordering_info": None,
    }
    pkg.update(overrides)
    return pkg


def _make_extraction(packages=None, summary=None):
    """Build a full extraction result dict."""
    if packages is None:
        packages = [_make_package()]
    result = {"packages": packages}
    if summary is not None:
        result["package_summary"] = summary
    else:
        result["package_summary"] = _build_package_summary(packages)
    return result


def _create_extractor():
    """Create a PackageExtractor instance with dummy args."""
    return PackageExtractor(
        client=None,
        model=None,
        pdf_path="/tmp/test.pdf",
        page_classification=[],
        is_fpga=False,
    )


# ─── Framework Tests ──────────────────────────────────────────────────


class TestPackageExtractorFramework:
    """Tests that PackageExtractor integrates correctly with the framework."""

    def test_inherits_base_extractor(self):
        assert issubclass(PackageExtractor, BaseExtractor)

    def test_domain_name(self):
        assert PackageExtractor.DOMAIN_NAME == "package"

    def test_in_registry(self):
        from extractors import EXTRACTOR_REGISTRY
        classes = [E.__name__ for E in EXTRACTOR_REGISTRY]
        assert "PackageExtractor" in classes

    def test_registry_contains_instance(self):
        from extractors import EXTRACTOR_REGISTRY
        assert PackageExtractor in EXTRACTOR_REGISTRY

    def test_has_required_methods(self):
        for method in ("select_pages", "extract", "validate"):
            assert hasattr(PackageExtractor, method)

    def test_instantiation(self):
        ext = _create_extractor()
        assert ext.client is None
        assert ext.model is None
        assert ext.pdf_path == "/tmp/test.pdf"
        assert ext.page_classification == []
        assert ext.is_fpga is False


# ─── Package Type Enum Tests ─────────────────────────────────────────


class TestPackageTypeEnum:
    """Tests for the package_type validation against VALID_PACKAGE_TYPES."""

    def test_valid_package_types_accepted(self):
        for ptype in ["QFN", "BGA", "SOIC", "SOT-23", "LQFP", "TO-220", "DPAK", "WLCSP", "DFN"]:
            ext = _create_extractor()
            result = ext.validate(_make_extraction([_make_package(package_type=ptype)]))
            type_warnings = [
                i for i in result["package_validation"]
                if "package_type" in i["message"] and "not in" in i["message"]
            ]
            assert len(type_warnings) == 0, f"{ptype} should be valid"

    def test_invalid_package_type_warned(self):
        ext = _create_extractor()
        result = ext.validate(_make_extraction([_make_package(package_type="ZXYZ-INVALID")]))
        type_warnings = [
            i for i in result["package_validation"]
            if "package_type" in i["message"] and "not in" in i["message"]
        ]
        assert len(type_warnings) == 1

    def test_missing_package_type_warned(self):
        ext = _create_extractor()
        result = ext.validate(_make_extraction([_make_package(package_type=None)]))
        type_warnings = [
            i for i in result["package_validation"]
            if "missing package_type" in i["message"]
        ]
        assert len(type_warnings) == 1

    def test_valid_package_types_set_has_entries(self):
        assert len(VALID_PACKAGE_TYPES) >= 35


# ─── Dimension Validation Tests ──────────────────────────────────────


class TestDimensionValidation:
    """Tests for min/nom/max dimension checking."""

    def test_valid_dimensions_no_issues(self):
        issues = _check_dimension_minmax(
            {"min": 6.9, "nom": 7.0, "max": 7.1}, "body_length_mm", "pkg"
        )
        assert len(issues) == 0

    def test_negative_dimension_error(self):
        issues = _check_dimension_minmax(
            {"min": -1.0, "nom": 7.0, "max": 7.1}, "body_length_mm", "pkg"
        )
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 1
        assert "negative" in errors[0]["message"]

    def test_min_greater_than_max_error(self):
        issues = _check_dimension_minmax(
            {"min": 8.0, "nom": 7.0, "max": 7.1}, "body_length_mm", "pkg"
        )
        errors = [i for i in issues if i["level"] == "error"]
        assert any("min" in e["message"] and ">" in e["message"] for e in errors)

    def test_min_greater_than_nom_error(self):
        issues = _check_dimension_minmax(
            {"min": 7.5, "nom": 7.0, "max": 7.6}, "body_length_mm", "pkg"
        )
        errors = [i for i in issues if i["level"] == "error"]
        assert any("min" in e["message"] and "nom" in e["message"] for e in errors)

    def test_nom_greater_than_max_error(self):
        issues = _check_dimension_minmax(
            {"min": 6.9, "nom": 7.5, "max": 7.1}, "body_length_mm", "pkg"
        )
        errors = [i for i in issues if i["level"] == "error"]
        assert any("nom" in e["message"] and "max" in e["message"] for e in errors)

    def test_unusually_large_dimension_warning(self):
        issues = _check_dimension_minmax(
            {"min": None, "nom": 250.0, "max": None}, "body_length_mm", "pkg"
        )
        warnings = [i for i in issues if i["level"] == "warning"]
        assert len(warnings) == 1
        assert "unusually large" in warnings[0]["message"]

    def test_null_dimension_no_issues(self):
        issues = _check_dimension_minmax(None, "body_length_mm", "pkg")
        assert len(issues) == 0

    def test_non_numeric_dimension_error(self):
        issues = _check_dimension_minmax(
            {"min": "abc", "nom": 7.0, "max": 7.1}, "body_length_mm", "pkg"
        )
        errors = [i for i in issues if i["level"] == "error"]
        assert any("not numeric" in e["message"] for e in errors)

    def test_all_null_values_no_issues(self):
        issues = _check_dimension_minmax(
            {"min": None, "nom": None, "max": None}, "body_length_mm", "pkg"
        )
        assert len(issues) == 0


# ─── Pin Pitch Validation Tests ──────────────────────────────────────


class TestPitchValidation:
    """Tests for pin pitch range checking."""

    def test_valid_pitch_no_issues(self):
        issues = _validate_pitch(0.5, "pkg")
        assert len(issues) == 0

    def test_null_pitch_no_issues(self):
        issues = _validate_pitch(None, "pkg")
        assert len(issues) == 0

    def test_below_minimum_pitch_warning(self):
        issues = _validate_pitch(0.1, "pkg")
        warnings = [i for i in issues if i["level"] == "warning"]
        assert len(warnings) == 1
        assert "below" in warnings[0]["message"]

    def test_above_maximum_pitch_warning(self):
        issues = _validate_pitch(6.0, "pkg")
        warnings = [i for i in issues if i["level"] == "warning"]
        assert len(warnings) == 1
        assert "exceeds" in warnings[0]["message"]

    def test_zero_pitch_error(self):
        issues = _validate_pitch(0, "pkg")
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 1
        assert "non-positive" in errors[0]["message"]

    def test_negative_pitch_error(self):
        issues = _validate_pitch(-0.5, "pkg")
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 1
        assert "non-positive" in errors[0]["message"]

    def test_non_numeric_pitch_error(self):
        issues = _validate_pitch("wide", "pkg")
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 1
        assert "not numeric" in errors[0]["message"]

    def test_boundary_min_pitch_no_warning(self):
        issues = _validate_pitch(_PITCH_MIN, "pkg")
        assert len(issues) == 0

    def test_boundary_max_pitch_no_warning(self):
        issues = _validate_pitch(_PITCH_MAX, "pkg")
        assert len(issues) == 0


# ─── Reflow Temperature Validation Tests ─────────────────────────────


class TestReflowTempValidation:
    """Tests for reflow profile peak temperature checking."""

    def test_valid_reflow_temp_no_issues(self):
        issues = _validate_reflow_temp({"peak_temp_c": 260}, "pkg")
        assert len(issues) == 0

    def test_null_reflow_no_issues(self):
        issues = _validate_reflow_temp(None, "pkg")
        assert len(issues) == 0

    def test_below_minimum_reflow_temp_warning(self):
        issues = _validate_reflow_temp({"peak_temp_c": 200}, "pkg")
        warnings = [i for i in issues if i["level"] == "warning"]
        assert len(warnings) == 1
        assert "below" in warnings[0]["message"]

    def test_above_maximum_reflow_temp_warning(self):
        issues = _validate_reflow_temp({"peak_temp_c": 300}, "pkg")
        warnings = [i for i in issues if i["level"] == "warning"]
        assert len(warnings) == 1
        assert "exceeds" in warnings[0]["message"]

    def test_non_numeric_reflow_temp_error(self):
        issues = _validate_reflow_temp({"peak_temp_c": "hot"}, "pkg")
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 1
        assert "not numeric" in errors[0]["message"]

    def test_missing_peak_temp_no_issues(self):
        issues = _validate_reflow_temp({"other_field": 123}, "pkg")
        assert len(issues) == 0

    def test_boundary_min_reflow_temp(self):
        issues = _validate_reflow_temp({"peak_temp_c": _REFLOW_TEMP_MIN}, "pkg")
        assert len(issues) == 0

    def test_boundary_max_reflow_temp(self):
        issues = _validate_reflow_temp({"peak_temp_c": _REFLOW_TEMP_MAX}, "pkg")
        assert len(issues) == 0


# ─── Thermal Properties Validation Tests ─────────────────────────────


class TestThermalPropertiesValidation:
    """Tests for thermal resistance value checking."""

    def test_valid_theta_ja_no_issues(self):
        issues = _validate_thermal_properties({"theta_ja_c_per_w": 28.5}, "pkg")
        assert len(issues) == 0

    def test_null_thermal_no_issues(self):
        issues = _validate_thermal_properties(None, "pkg")
        assert len(issues) == 0

    def test_theta_ja_below_minimum_warning(self):
        issues = _validate_thermal_properties({"theta_ja_c_per_w": 0.5}, "pkg")
        warnings = [i for i in issues if i["level"] == "warning"]
        assert len(warnings) == 1
        assert "below" in warnings[0]["message"]

    def test_theta_ja_above_maximum_warning(self):
        issues = _validate_thermal_properties({"theta_ja_c_per_w": 600}, "pkg")
        warnings = [i for i in issues if i["level"] == "warning"]
        assert len(warnings) == 1
        assert "exceeds" in warnings[0]["message"]

    def test_non_numeric_theta_ja_error(self):
        issues = _validate_thermal_properties({"theta_ja_c_per_w": "high"}, "pkg")
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 1
        assert "not numeric" in errors[0]["message"]

    def test_negative_theta_jc_error(self):
        issues = _validate_thermal_properties({"theta_jc_c_per_w": -1.0}, "pkg")
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 1
        assert "negative" in errors[0]["message"]

    def test_negative_power_dissipation_warning(self):
        issues = _validate_thermal_properties({"power_dissipation_w": -0.5}, "pkg")
        warnings = [i for i in issues if i["level"] == "warning"]
        assert len(warnings) == 1
        assert "non-positive" in warnings[0]["message"]


# ─── Moisture Sensitivity Validation Tests ───────────────────────────


class TestMoistureSensitivityValidation:
    """Tests for MSL level and related data."""

    def test_valid_msl_no_issues(self):
        issues = _validate_moisture_sensitivity(
            {"msl_level": "MSL 3", "peak_reflow_temp_c": 260}, "pkg"
        )
        assert len(issues) == 0

    def test_null_msl_no_issues(self):
        issues = _validate_moisture_sensitivity(None, "pkg")
        assert len(issues) == 0

    def test_unrecognized_msl_level_warning(self):
        issues = _validate_moisture_sensitivity({"msl_level": "MSL 99"}, "pkg")
        warnings = [i for i in issues if i["level"] == "warning"]
        assert len(warnings) == 1
        assert "unrecognized" in warnings[0]["message"]

    def test_valid_numeric_msl_levels(self):
        for level in ["1", "2", "2a", "3", "4", "5", "5a", "6"]:
            issues = _validate_moisture_sensitivity({"msl_level": level}, "pkg")
            level_warnings = [
                i for i in issues if "unrecognized" in i["message"]
            ]
            assert len(level_warnings) == 0, f"MSL level '{level}' should be valid"

    def test_msl_reflow_temp_out_of_range_warning(self):
        issues = _validate_moisture_sensitivity(
            {"msl_level": "MSL 3", "peak_reflow_temp_c": 300}, "pkg"
        )
        warnings = [i for i in issues if i["level"] == "warning"]
        assert any("peak_reflow_temp_c" in w["message"] for w in warnings)


# ─── Duplicate Package Name Tests ────────────────────────────────────


class TestDuplicatePackageName:
    """Tests for duplicate package_name detection."""

    def test_no_duplicates_no_issues(self):
        packages = [
            _make_package(package_name="VQFN-48"),
            _make_package(package_name="SOIC-16", package_type="SOIC", pin_count=16),
        ]
        ext = _create_extractor()
        result = ext.validate(_make_extraction(packages))
        dup_warnings = [
            i for i in result["package_validation"]
            if "duplicate package_name" in i["message"]
        ]
        assert len(dup_warnings) == 0

    def test_duplicate_name_warned(self):
        packages = [
            _make_package(package_name="VQFN-48"),
            _make_package(package_name="VQFN-48"),
        ]
        ext = _create_extractor()
        result = ext.validate(_make_extraction(packages))
        dup_warnings = [
            i for i in result["package_validation"]
            if "duplicate package_name" in i["message"]
        ]
        assert len(dup_warnings) == 1

    def test_duplicate_name_case_insensitive(self):
        packages = [
            _make_package(package_name="VQFN-48"),
            _make_package(package_name="vqfn-48"),
        ]
        ext = _create_extractor()
        result = ext.validate(_make_extraction(packages))
        dup_warnings = [
            i for i in result["package_validation"]
            if "duplicate package_name" in i["message"]
        ]
        assert len(dup_warnings) == 1


# ─── Summary Consistency Tests ───────────────────────────────────────


class TestSummaryConsistency:
    """Tests for package_summary consistency checks."""

    def test_consistent_summary_no_issues(self):
        packages = [_make_package()]
        summary = _build_package_summary(packages)
        ext = _create_extractor()
        result = ext.validate(_make_extraction(packages, summary))
        summary_warnings = [
            i for i in result["package_validation"]
            if "package_summary" in i["message"]
        ]
        assert len(summary_warnings) == 0

    def test_mismatched_total_packages_warned(self):
        packages = [_make_package()]
        summary = _build_package_summary(packages)
        summary["total_packages"] = 5  # Wrong count
        ext = _create_extractor()
        result = ext.validate(_make_extraction(packages, summary))
        total_warnings = [
            i for i in result["package_validation"]
            if "total_packages" in i["message"]
        ]
        assert len(total_warnings) == 1

    def test_mismatched_package_types_warned(self):
        packages = [_make_package(package_type="QFN")]
        summary = _build_package_summary(packages)
        summary["package_types"] = ["BGA"]  # Wrong type
        ext = _create_extractor()
        result = ext.validate(_make_extraction(packages, summary))
        type_warnings = [
            i for i in result["package_validation"]
            if "package_types" in i["message"]
        ]
        assert len(type_warnings) == 1

    def test_mismatched_has_exposed_pad_warned(self):
        packages = [_make_package()]
        summary = _build_package_summary(packages)
        summary["has_exposed_pad"] = False  # Wrong flag
        ext = _create_extractor()
        result = ext.validate(_make_extraction(packages, summary))
        ep_warnings = [
            i for i in result["package_validation"]
            if "has_exposed_pad" in i["message"]
        ]
        assert len(ep_warnings) == 1


# ─── Edge Cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge conditions and boundary values."""

    def test_empty_packages_list(self):
        ext = _create_extractor()
        result = ext.validate(_make_extraction([]))
        assert result["package_count"] == 0
        warnings = [
            i for i in result["package_validation"]
            if "No packages found" in i["message"]
        ]
        assert len(warnings) == 1

    def test_error_in_extraction_result(self):
        ext = _create_extractor()
        result = ext.validate({"error": "API failed"})
        assert result["package_count"] == 0
        assert len(result["package_validation"]) == 0

    def test_null_dimensions_no_crash(self):
        pkg = _make_package(
            body_length_mm=None,
            body_width_mm=None,
            body_height_mm=None,
            lead_span_mm=None,
            terminal_width_mm=None,
            terminal_length_mm=None,
        )
        ext = _create_extractor()
        result = ext.validate(_make_extraction([pkg]))
        assert result["package_count"] == 1

    def test_missing_optional_fields(self):
        pkg = {
            "package_name": "MINIMAL-8",
            "package_type": "QFN",
            "pin_count": 8,
        }
        ext = _create_extractor()
        result = ext.validate(_make_extraction([pkg]))
        assert result["package_count"] == 1

    def test_pin_count_zero_error(self):
        ext = _create_extractor()
        result = ext.validate(_make_extraction([_make_package(pin_count=0)]))
        errors = [
            i for i in result["package_validation"]
            if "pin_count" in i["message"] and i["level"] == "error"
        ]
        assert len(errors) == 1

    def test_pin_count_negative_error(self):
        ext = _create_extractor()
        result = ext.validate(_make_extraction([_make_package(pin_count=-5)]))
        errors = [
            i for i in result["package_validation"]
            if "pin_count" in i["message"] and i["level"] == "error"
        ]
        assert len(errors) == 1

    def test_pin_count_non_integer_error(self):
        ext = _create_extractor()
        result = ext.validate(_make_extraction([_make_package(pin_count=3.5)]))
        errors = [
            i for i in result["package_validation"]
            if "pin_count" in i["message"] and i["level"] == "error"
        ]
        assert len(errors) == 1

    def test_exposed_pad_non_positive_dimension_error(self):
        pkg = _make_package(
            exposed_pad={"present": True, "length_mm": 0, "width_mm": 5.0}
        )
        ext = _create_extractor()
        result = ext.validate(_make_extraction([pkg]))
        errors = [
            i for i in result["package_validation"]
            if "exposed_pad" in i["message"] and "non-positive" in i["message"]
        ]
        assert len(errors) == 1

    def test_duplicate_ordering_info_part_number(self):
        pkg = _make_package(
            ordering_info=[
                {"part_number": "ABC123", "package_type": "QFN"},
                {"part_number": "ABC123", "package_type": "QFN"},
            ]
        )
        ext = _create_extractor()
        result = ext.validate(_make_extraction([pkg]))
        dup_warnings = [
            i for i in result["package_validation"]
            if "duplicate part_number" in i["message"]
        ]
        assert len(dup_warnings) == 1


# ─── Build Package Summary Tests ─────────────────────────────────────


class TestBuildPackageSummary:
    """Tests for the _build_package_summary helper."""

    def test_empty_packages(self):
        summary = _build_package_summary([])
        assert summary["total_packages"] == 0
        assert summary["package_types"] == []
        assert summary["has_exposed_pad"] is False
        assert summary["has_land_pattern"] is False
        assert summary["has_thermal_data"] is False
        assert summary["has_ordering_info"] is False

    def test_single_package_with_all_features(self):
        pkg = _make_package(
            land_pattern={"pad_length_mm": 0.85, "pad_width_mm": 0.3, "pad_pitch_mm": 0.5},
            ordering_info=[{"part_number": "TEST123"}],
        )
        summary = _build_package_summary([pkg])
        assert summary["total_packages"] == 1
        assert "QFN" in summary["package_types"]
        assert summary["has_exposed_pad"] is True
        assert summary["has_land_pattern"] is True
        assert summary["has_thermal_data"] is True
        assert summary["has_ordering_info"] is True

    def test_multiple_package_types_sorted(self):
        packages = [
            _make_package(package_type="BGA", package_name="BGA-256"),
            _make_package(package_type="QFN", package_name="QFN-48"),
            _make_package(package_type="SOIC", package_name="SOIC-8"),
        ]
        summary = _build_package_summary(packages)
        assert summary["total_packages"] == 3
        assert summary["package_types"] == ["BGA", "QFN", "SOIC"]

    def test_no_exposed_pad(self):
        pkg = _make_package(exposed_pad=None)
        summary = _build_package_summary([pkg])
        assert summary["has_exposed_pad"] is False

    def test_exposed_pad_not_present(self):
        pkg = _make_package(exposed_pad={"present": False})
        summary = _build_package_summary([pkg])
        assert summary["has_exposed_pad"] is False


# ─── Schema Compliance Tests ─────────────────────────────────────────


class TestSchemaCompliance:
    """Tests that sample output conforms to the package domain schema."""

    @pytest.fixture
    def schema(self):
        schema_path = Path(__file__).parent / "schemas" / "domains" / "package.schema.json"
        with open(schema_path) as f:
            return json.load(f)

    def test_schema_file_exists(self):
        schema_path = Path(__file__).parent / "schemas" / "domains" / "package.schema.json"
        assert schema_path.exists(), f"Schema file not found: {schema_path}"

    def test_schema_has_packages_property(self, schema):
        assert "packages" in schema["properties"]

    def test_schema_has_package_summary_property(self, schema):
        assert "package_summary" in schema["properties"]

    def test_schema_has_package_info_def(self, schema):
        assert "package_info" in schema["$defs"]

    def test_schema_package_type_enum_exists(self, schema):
        pkg_info = schema["$defs"]["package_info"]
        pkg_type = pkg_info["properties"]["package_type"]
        assert "enum" in pkg_type
        assert len(pkg_type["enum"]) > 0

    def test_schema_requires_package_type_and_name(self, schema):
        pkg_info = schema["$defs"]["package_info"]
        assert "package_type" in pkg_info["required"]
        assert "package_name" in pkg_info["required"]

    def test_sample_output_validates_against_schema(self, schema):
        """Validate a well-formed sample output against the schema structure."""
        sample = {
            "packages": [
                {
                    "package_type": "QFN",
                    "package_name": "VQFN-48",
                    "pin_count": 48,
                    "pin_pitch_mm": 0.5,
                    "dimensions": {
                        "body_length_mm": {"min": 6.9, "nom": 7.0, "max": 7.1},
                        "body_width_mm": {"min": 6.9, "nom": 7.0, "max": 7.1},
                        "body_height_mm": {"min": 0.8, "nom": 0.85, "max": 0.9},
                    },
                    "exposed_pad": {
                        "present": True,
                        "length_mm": {"min": None, "nom": 5.6, "max": None},
                        "width_mm": {"min": None, "nom": 5.6, "max": None},
                    },
                    "land_pattern": None,
                    "thermal_properties": {
                        "theta_ja": 28.5,
                        "theta_jc": 4.3,
                    },
                    "moisture_sensitivity_level": "3",
                    "weight_mg": 120,
                    "reflow_profile": None,
                    "marking": None,
                    "ordering_info": [],
                    "notes": None,
                }
            ],
            "package_summary": {
                "total_packages": 1,
                "package_types": ["QFN"],
                "has_exposed_pad": True,
                "has_land_pattern": False,
                "has_reflow_profile": False,
            },
        }
        # Verify structural compliance: top-level keys match schema properties
        for key in sample:
            assert key in schema["properties"], f"Key '{key}' not in schema properties"

        # Verify package item has required fields per schema
        pkg_info_required = schema["$defs"]["package_info"]["required"]
        for pkg in sample["packages"]:
            for req_field in pkg_info_required:
                assert req_field in pkg, f"Required field '{req_field}' missing from package"


# ─── Full Validate Integration Tests ─────────────────────────────────


class TestValidateIntegration:
    """Integration tests for the full validate() method."""

    def test_clean_extraction_no_issues(self):
        ext = _create_extractor()
        result = ext.validate(_make_extraction())
        assert result["package_count"] == 1
        # A clean extraction should only have summary consistency issues at most
        errors = [i for i in result["package_validation"] if i["level"] == "error"]
        assert len(errors) == 0

    def test_multiple_issues_accumulated(self):
        pkg = _make_package(
            package_type="INVALID_TYPE",
            pin_count=-1,
            pitch_mm=-0.5,
            body_length_mm={"min": 10.0, "nom": 5.0, "max": 3.0},
        )
        ext = _create_extractor()
        result = ext.validate(_make_extraction([pkg]))
        assert len(result["package_validation"]) >= 3

    def test_package_count_returned(self):
        packages = [
            _make_package(package_name="PKG-A"),
            _make_package(package_name="PKG-B", package_type="BGA"),
        ]
        ext = _create_extractor()
        result = ext.validate(_make_extraction(packages))
        assert result["package_count"] == 2
