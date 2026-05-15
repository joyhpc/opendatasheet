"""Tests for DesignGuideExtractor.

Validates text-based extraction logic using synthetic design guide text
that mirrors real UG984 (Gowin GW5AT) content. Does NOT require Gemini API.
"""
import pytest
import json
import os
from pathlib import Path

from extractors.design_guide import (
    DesignGuideExtractor,
    _extract_text_rules,
    _classify_design_guide_pages,
    _merge_text_and_vision,
    _validate_severity,
    _check_contradictory_sequencing,
    _check_ramp_rate_sanity,
    VALID_SEVERITIES,
    VALID_CONNECTION_TYPES,
)
from scripts.design_guide_domain import resolve_gowin_design_guide_source_path, load_gowin_design_guide_bundle


# ============================================
# Synthetic UG984-like text for testing
# ============================================

SAMPLE_POWER_TEXT = """
## 电源设计

### 上电顺序与斜率
- **推荐 VCCX 在 VCC 之前上电**
- VCC 上升斜率: 0.1 ~ 15 mV/us
- VCCLDO 上升斜率: 0.09 ~ 15 mV/us
- VCCX 上升斜率: 0.005 ~ 15 mV/us
- VCCIO 上升斜率: 0.06 ~ 15 mV/us

### 纹波要求
- VCC: ≤ 3%
- VCCIO: ≤ 5%
- VCCX: ≤ 5%
"""

SAMPLE_PIN_TEXT = """
## 关键配置管脚

### READY
- 高电平有效，READY 拉高时才能配置
- 开漏输出，需要外部 4.7K 上拉到 3.3V

### DONE
- 配置成功标志
- 开漏输出，需要外部 4.7K 上拉到 3.3V

### CFGBVS
- 必须设置，不能悬空
- 配置 IO 所在 Bank 的 VCCIO ≥ 2.5V → CFGBVS 接高
- 配置 IO 所在 Bank 的 VCCIO ≤ 1.8V → CFGBVS 接低

### PUDC_B
- 不允许悬空，通过 1kΩ 电阻接 VCCIO 或 GND
"""


class TestTextRulesExtraction:
    """Test regex-based text extraction without PDF."""

    def test_ramp_rate_extraction(self):
        """Extract slew rate constraints from UG984-style text."""
        # Create a mock fitz doc-like object
        from unittest.mock import MagicMock
        doc = MagicMock()
        doc.__len__ = lambda self: 1
        page = MagicMock()
        page.get_text.return_value = SAMPLE_POWER_TEXT
        doc.__getitem__ = lambda self, i: page

        result = _extract_text_rules(doc)
        ramps = result.get("power_ramp_constraints", [])

        # Should find VCC, VCCLDO, VCCX, VCCIO ramp constraints
        assert len(ramps) >= 2, f"Expected >=2 ramp constraints, got {len(ramps)}"

        rail_names = [r["rail"] for r in ramps]
        assert any("VCC" in r for r in rail_names), f"VCC not found in {rail_names}"

    def test_ripple_extraction(self):
        """Extract ripple requirements from UG984-style text."""
        from unittest.mock import MagicMock
        doc = MagicMock()
        doc.__len__ = lambda self: 1
        page = MagicMock()
        page.get_text.return_value = SAMPLE_POWER_TEXT
        doc.__getitem__ = lambda self, i: page

        result = _extract_text_rules(doc)
        decoupling = result.get("decoupling_requirements", [])

        assert len(decoupling) >= 2, f"Expected >=2 ripple requirements, got {len(decoupling)}"

        vcc_ripple = [d for d in decoupling if d["rail"] == "VCC"]
        assert len(vcc_ripple) >= 1, "VCC ripple requirement not found"
        assert vcc_ripple[0]["ripple_max_pct"] == 3.0

    def test_pull_up_extraction(self):
        """Extract pull-up requirements from pin description text."""
        from unittest.mock import MagicMock
        doc = MagicMock()
        doc.__len__ = lambda self: 1
        page = MagicMock()
        page.get_text.return_value = SAMPLE_PIN_TEXT
        doc.__getitem__ = lambda self, i: page

        result = _extract_text_rules(doc)
        pin_rules = result.get("pin_connection_rules", [])

        # Should find pull-up rules for READY, DONE and must-not-float for CFGBVS, PUDC_B
        assert len(pin_rules) >= 1, f"Expected >=1 pin rules, got {len(pin_rules)}"

    def test_not_float_extraction(self):
        """Extract must-not-float pin rules."""
        from unittest.mock import MagicMock
        doc = MagicMock()
        doc.__len__ = lambda self: 1
        page = MagicMock()
        page.get_text.return_value = SAMPLE_PIN_TEXT
        doc.__getitem__ = lambda self, i: page

        result = _extract_text_rules(doc)
        pin_rules = result.get("pin_connection_rules", [])

        not_float = [r for r in pin_rules if r.get("connection_type") == "must_not_float"]
        assert len(not_float) >= 1, f"Expected >=1 must-not-float rules, got {len(not_float)}"


class TestMergeLogic:
    """Test merging of text-based and vision-based results."""

    def test_vision_takes_priority(self):
        text_result = {
            "pin_connection_rules": [
                {"pin": "READY", "rule": "pull-up text", "connection_type": "pull_up", "severity": "ERROR"}
            ]
        }
        vision_result = {
            "pin_connection_rules": [
                {"pin": "READY", "rule": "pull-up vision (better)", "connection_type": "pull_up", "severity": "ERROR"}
            ],
            "power_domain_map": [{"group": "FPGA", "rail_name": "VCC"}],
        }
        merged = _merge_text_and_vision(text_result, vision_result)

        # READY appears in both — should keep vision version, not duplicate
        ready_rules = [r for r in merged["pin_connection_rules"] if r["pin"] == "READY"]
        assert len(ready_rules) == 1, f"Expected 1 READY rule (vision), got {len(ready_rules)}"
        assert "vision" in ready_rules[0]["rule"]

    def test_text_fills_gaps(self):
        text_result = {
            "power_ramp_constraints": [
                {"rail": "VCC", "slew_rate_min": 0.1, "slew_rate_max": 15.0, "unit": "mV/us"}
            ]
        }
        vision_result = {
            "power_ramp_constraints": [],
            "pin_connection_rules": [{"pin": "DONE", "rule": "pull-up", "severity": "ERROR"}],
        }
        merged = _merge_text_and_vision(text_result, vision_result)

        # Vision had empty ramp constraints — text should fill in
        assert len(merged["power_ramp_constraints"]) == 1
        assert merged["power_ramp_constraints"][0]["rail"] == "VCC"

    def test_text_adds_missing_items(self):
        text_result = {
            "pin_connection_rules": [
                {"pin": "CFGBVS", "rule": "must not float", "connection_type": "must_not_float", "severity": "ERROR"},
                {"pin": "READY", "rule": "pull-up", "connection_type": "pull_up", "severity": "ERROR"},
            ]
        }
        vision_result = {
            "pin_connection_rules": [
                {"pin": "READY", "rule": "pull-up from vision", "connection_type": "pull_up", "severity": "ERROR"},
            ]
        }
        merged = _merge_text_and_vision(text_result, vision_result)

        pins = [r["pin"] for r in merged["pin_connection_rules"]]
        assert "CFGBVS" in pins, "Text-only pin CFGBVS should be merged in"
        assert "READY" in pins, "Vision pin READY should be present"


class TestValidation:
    """Test validation logic."""

    def test_valid_severities(self):
        items = [{"severity": "ERROR"}, {"severity": "WARNING"}, {"severity": "INFO"}]
        issues = _validate_severity(items, "test")
        assert len(issues) == 0

    def test_invalid_severity(self):
        items = [{"severity": "CRITICAL"}, {"severity": "ERROR"}]
        issues = _validate_severity(items, "test")
        assert len(issues) == 1
        assert "CRITICAL" in issues[0]["message"]

    def test_contradictory_sequencing(self):
        rules = [
            {"rail_before": "VCC", "rail_after": "VCCIO"},
            {"rail_before": "VCCIO", "rail_after": "VCC"},
        ]
        issues = _check_contradictory_sequencing(rules)
        assert len(issues) == 1
        assert "Contradictory" in issues[0]["message"]

    def test_no_contradictory_sequencing(self):
        rules = [
            {"rail_before": "VCCX", "rail_after": "VCC"},
            {"rail_before": "VCC", "rail_after": "VCCIO"},
        ]
        issues = _check_contradictory_sequencing(rules)
        assert len(issues) == 0

    def test_ramp_rate_min_gt_max(self):
        constraints = [{"rail": "VCC", "slew_rate_min": 20, "slew_rate_max": 15}]
        issues = _check_ramp_rate_sanity(constraints)
        assert len(issues) == 1
        assert "slew_rate_min" in issues[0]["message"]

    def test_ramp_rate_negative(self):
        constraints = [{"rail": "VCC", "slew_rate_min": -1, "slew_rate_max": 15}]
        issues = _check_ramp_rate_sanity(constraints)
        assert len(issues) >= 1

    def test_valid_ramp_rates(self):
        constraints = [{"rail": "VCC", "slew_rate_min": 0.1, "slew_rate_max": 15}]
        issues = _check_ramp_rate_sanity(constraints)
        assert len(issues) == 0


class TestDesignGuideExtractor:
    """Test DesignGuideExtractor class itself."""

    def test_domain_name(self):
        assert DesignGuideExtractor.DOMAIN_NAME == "design_guide"

    def test_validate_empty(self):
        """Validate handles empty results gracefully."""
        ext = DesignGuideExtractor(
            client=None, model=None, pdf_path="",
            page_classification=[], is_fpga=True
        )
        result = ext.validate({})
        assert "design_guide_validation_issues" in result
        assert result["power_domain_count"] == 0

    def test_validate_error_result(self):
        """Validate handles error results gracefully."""
        ext = DesignGuideExtractor(
            client=None, model=None, pdf_path="",
            page_classification=[], is_fpga=True
        )
        result = ext.validate({"error": "test error"})
        assert result["power_domain_count"] == 0

    def test_validate_good_data(self):
        """Validate passes clean data without issues."""
        ext = DesignGuideExtractor(
            client=None, model=None, pdf_path="",
            page_classification=[], is_fpga=True
        )
        good_data = {
            "power_domain_map": [
                {"group": "FPGA", "rail_name": "VCC", "description": "Core voltage"},
                {"group": "FPGA", "rail_name": "VCCIO", "description": "IO voltage"},
            ],
            "power_sequencing_rules": [
                {"rule": "VCCX before VCC", "rail_before": "VCCX", "rail_after": "VCC", "severity": "ERROR"}
            ],
            "power_ramp_constraints": [
                {"rail": "VCC", "slew_rate_min": 0.1, "slew_rate_max": 15, "unit": "mV/us"}
            ],
            "pin_connection_rules": [
                {"pin": "READY", "rule": "4.7K pull-up to 3.3V", "connection_type": "pull_up", "severity": "ERROR"}
            ],
            "decoupling_requirements": [
                {"rail": "VCC", "ripple_max_pct": 3, "severity": "WARNING"}
            ],
            "clock_design_rules": [
                {"signal": "SerDes refclk", "requirement": "AC coupling 0.1uF", "severity": "WARNING"}
            ],
            "configuration_mode_support": [
                {"mode": "JTAG", "supported": True, "max_clock_freq": "100MHz"}
            ],
            "io_standard_rules": [
                {"standard": "LVDS", "requirement": "100Ω differential termination", "severity": "INFO"}
            ],
            "rail_merge_guidelines": [
                {"rails": ["VCC"], "can_merge": False, "severity": "ERROR"}
            ],
            "design_guideline_text": [
                {"category": "power", "guideline": "Use ferrite bead isolation between power domains"}
            ],
        }
        result = ext.validate(good_data)
        errors = [i for i in result["design_guide_validation_issues"] if i["level"] == "error"]
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert result["power_domain_count"] == 2
        assert result["sequencing_rule_count"] == 1
        assert result["pin_rule_count"] == 1


class TestSchemaValidation:
    """Test that schema file is valid JSON Schema."""

    def test_schema_loads(self):
        schema_path = os.path.join(
            os.path.dirname(__file__),
            "schemas", "domains", "design_guide.schema.json"
        )
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        assert schema["$id"] == "https://opendatasheet.dev/schemas/domains/design_guide/1.0"
        assert "power_domain_map" in schema["properties"]
        assert "pin_connection_rules" in schema["properties"]
        assert "power_sequencing_rules" in schema["properties"]
        assert "clock_design_rules" in schema["properties"]

    def test_schema_validates_sample(self):
        """Validate sample data against the schema."""
        try:
            from jsonschema import validate, ValidationError
        except ImportError:
            pytest.skip("jsonschema not installed")

        schema_path = os.path.join(
            os.path.dirname(__file__),
            "schemas", "domains", "design_guide.schema.json"
        )
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)

        sample = {
            "source_document": {
                "title": "GW5AT Schematic Design Guide",
                "document_id": "UG984",
                "version": "1.2",
                "device_family": "GW5AT"
            },
            "power_domain_map": [
                {"group": "FPGA", "rail_name": "VCC", "description": "Core voltage"}
            ],
            "power_sequencing_rules": [
                {"rule": "VCCX before VCC", "severity": "ERROR"}
            ],
            "power_ramp_constraints": [
                {"rail": "VCC", "slew_rate_min": 0.1, "slew_rate_max": 15, "unit": "mV/us"}
            ],
            "rail_merge_guidelines": [
                {"rails": ["VDDAQ0", "VDDDQ0"], "can_merge": True,
                 "conditions": "Same voltage", "recommendation": "Use LDO", "severity": "WARNING"}
            ],
            "pin_connection_rules": [
                {"pin": "CFGBVS", "rule": "Must not float", "connection_type": "must_not_float", "severity": "ERROR"}
            ],
            "decoupling_requirements": [
                {"rail": "VCC", "ripple_max_pct": 3, "filter_type": "ferrite bead + ceramic cap", "severity": "WARNING"}
            ],
            "clock_design_rules": [
                {"signal": "SerDes refclk", "requirement": "AC coupling 0.1uF near FPGA", "severity": "WARNING"}
            ],
            "configuration_mode_support": [
                {"mode": "JTAG", "supported": True, "max_clock_freq": "100MHz",
                 "signals": ["TCK", "TMS", "TDI", "TDO"]}
            ],
            "io_standard_rules": [
                {"standard": "LVDS", "requirement": "100Ω internal differential termination",
                 "applies_to": "All banks (GW5AT-15/60)", "severity": "INFO"}
            ],
            "design_guideline_text": [
                {"category": "power", "guideline": "Ferrite bead isolation between voltage domains"}
            ]
        }

        # Should not raise
        validate(instance=sample, schema=schema)


class TestExistingGuideDataCoverage:
    """Compare existing gowin_gw5at_schematic_guide.md content with what the extractor should capture."""

    def test_existing_guide_has_expected_sections(self):
        guide_path = os.path.join(
            os.path.dirname(__file__),
            "data", "extracted_v2", "fpga", "gowin_gw5at_schematic_guide.md"
        )
        if not os.path.exists(guide_path):
            pytest.skip("gowin_gw5at_schematic_guide.md not found")

        with open(guide_path, encoding="utf-8") as f:
            content = f.read()

        # Verify key sections exist in the manually-created guide
        assert "电源设计" in content or "Power" in content
        assert "RECONFIG_N" in content
        assert "READY" in content
        assert "CFGBVS" in content
        assert "JTAG" in content
        assert "MSPI" in content or "SSPI" in content
        assert "LVDS" in content
        assert "上电顺序" in content or "power-up" in content.lower()


class TestGuideSourceResolution:
    def test_resolve_gowin_guide_prefers_json_over_markdown(self, tmp_path: Path):
        repo = tmp_path
        target_dir = repo / "data" / "extracted_v2" / "fpga"
        target_dir.mkdir(parents=True)
        md = target_dir / "gowin_gw5ar_schematic_guide.md"
        js = target_dir / "gowin_gw5ar_design_guide.json"
        md.write_text("# placeholder\n", encoding="utf-8")
        js.write_text("{}", encoding="utf-8")

        resolved = resolve_gowin_design_guide_source_path("GW5AR-25", repo_root=repo)
        assert resolved == js

    def test_load_gowin_bundle_accepts_extracted_json(self, tmp_path: Path):
        guide_path = tmp_path / "gowin_gw5as_design_guide.json"
        guide_path.write_text(json.dumps({
            "domains": {
                "design_guide": {
                    "source_document": {
                        "document_id": "UG1116",
                        "version": "1.1E",
                        "device_family": "GW5AS",
                    },
                    "source_documents": [],
                    "power_domain_map": [],
                    "power_sequencing_rules": [],
                    "power_ramp_constraints": [],
                    "rail_merge_guidelines": [],
                    "pin_connection_rules": [
                        {"pin": "MODE0", "rule": "MODE0 strap", "connection_type": "must_not_float", "severity": "ERROR"}
                    ],
                    "decoupling_requirements": [],
                    "clock_design_rules": [],
                    "configuration_mode_support": [],
                    "io_standard_rules": [],
                    "design_guideline_text": [],
                }
            }
        }), encoding="utf-8")

        bundle = load_gowin_design_guide_bundle(
            device="GW5AS-25",
            package="UG256",
            pinout_data={"power_rails": {}, "pins": []},
            guide_path=guide_path,
            gowin_dc=None,
        )

        assert "design_guide" in bundle["domains"]
        assert "power_sequence" in bundle["domains"]
        assert bundle["domains"]["design_guide"]["source_document"]["document_id"] == "UG1116"
