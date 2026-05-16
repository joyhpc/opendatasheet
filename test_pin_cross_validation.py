"""Tests for L3 pin mapping cross-validation."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

import pipeline_v2
from pipeline_v2 import PageInfo


class _FakePage:
    def __init__(self, text):
        self._text = text

    def get_text(self):
        return self._text


class _FakeDoc:
    def __init__(self, pages):
        self._pages = [_FakePage(text) for text in pages]
        self.closed = False

    def __getitem__(self, idx):
        return self._pages[idx]

    def close(self):
        self.closed = True


def _with_fake_pdf(monkeypatch, *page_texts):
    fake_doc = _FakeDoc(page_texts)
    monkeypatch.setattr(pipeline_v2.fitz, "open", lambda _path: fake_doc)
    return fake_doc


def _empty_extraction():
    return {
        "electrical_characteristics": [],
        "absolute_maximum_ratings": [],
    }


def test_cross_validate_pins_verifies_name_number_pairs(monkeypatch):
    _with_fake_pdf(
        monkeypatch,
        """
        Pin No.  Name  Description
        1        VIN   Input supply
        2        GND   Ground
        3        EN    Enable input
        """,
    )
    pages = [PageInfo(page_num=0, text_length=100, category="pin")]
    pin_extraction = {
        "logical_pins": [
            {"name": "VIN", "packages": {"SOT-23-3": [1]}},
            {"name": "GND", "packages": {"SOT-23-3": [2]}},
            {"name": "EN", "packages": {"SOT-23-3": [3]}},
        ]
    }

    result = pipeline_v2.cross_validate("fake.pdf", _empty_extraction(), pages, pin_extraction)

    assert result["pin_total_mappings"] == 3
    assert result["pin_mappings_verified"] == 3
    assert result["pin_mappings_suspicious"] == 0
    assert result["pin_mapping_coverage_pct"] == 100.0


def test_cross_validate_pins_marks_wrong_physical_pin_suspicious(monkeypatch):
    _with_fake_pdf(
        monkeypatch,
        """
        Pin No.  Name  Description
        1        VIN   Input supply
        2        GND   Ground
        3        EN    Enable input
        """,
    )
    pages = [PageInfo(page_num=0, text_length=100, category="pin")]
    pin_extraction = {
        "logical_pins": [
            {"name": "VIN", "packages": {"SOT-23-3": [9]}},
            {"name": "GND", "packages": {"SOT-23-3": [2]}},
        ]
    }

    result = pipeline_v2.cross_validate("fake.pdf", _empty_extraction(), pages, pin_extraction)

    assert result["pin_total_mappings"] == 2
    assert result["pin_mappings_verified"] == 1
    assert result["pin_mappings_suspicious"] == 1
    assert result["suspicious_pins"] == [
        {"name": "VIN", "package": "SOT-23-3", "pin_number": 9}
    ]


def test_cross_validate_pins_skips_fpga_package_free_extraction(monkeypatch):
    _with_fake_pdf(monkeypatch, "VCCINT VCCAUX configuration pins")
    pages = [PageInfo(page_num=0, text_length=100, category="pin")]
    pin_extraction = {
        "logical_pins": [
            {"name": "VCCINT", "pin_group": "POWER_SUPPLY", "packages": {}},
        ]
    }

    result = pipeline_v2.cross_validate(
        "fake.pdf",
        _empty_extraction(),
        pages,
        pin_extraction,
        is_fpga=True,
    )

    assert result["pin_total_mappings"] == 0
    assert result["pin_validation_skipped"] == "fpga_pin_numbers_live_in_separate_pinout_sources"


def test_pin_matching_handles_compact_pin_diagram_text():
    pin_lines = ["1", "VIN", "Input supply", "2", "GND"]

    assert pipeline_v2._pin_mapping_found_in_lines(pin_lines, "VIN", 1)
    assert not pipeline_v2._pin_mapping_found_in_lines(pin_lines, "VIN", 9)
