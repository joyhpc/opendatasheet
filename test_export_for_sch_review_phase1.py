"""Phase-1 stabilization regression tests for export_for_sch_review.py.

Covers:
  R1 - drc_hints: vin_operating must not capture a dropout-voltage row.
  R2 - parameter keys: symbol-less / duplicate-symbol rows must not be lost.
  freshness - the compare() helper of scripts/check_exports_fresh.py.
"""
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from export_for_sch_review import (
    _extract_drc_hints,
    _is_expression_symbol,
    _unique_param_key,
    export_normal_ic,
)
from check_exports_fresh import compare


# --- R1: vin_operating vs dropout voltage --------------------------------

# AMS1117-style electrical rows: the dropout row carries symbol "VIN - VOUT".
AMS1117_ELEC = [
    {"parameter": "Reference Voltage", "symbol": "VREF",
     "min": 1.232, "typ": 1.25, "max": 1.268, "unit": "V"},
    {"parameter": "Output Voltage", "symbol": "VOUT",
     "min": 1.478, "typ": 1.5, "max": 1.522, "unit": "V"},
    {"parameter": "Dropout Voltage", "symbol": "VIN - VOUT",
     "min": None, "typ": 1.1, "max": 1.3, "unit": "V"},
]
AMS1117_ABS = [
    {"parameter": "Input Voltage", "symbol": "VIN", "min": None, "max": 15, "unit": "V"},
]


def test_is_expression_symbol():
    assert _is_expression_symbol("VIN - VOUT")
    assert _is_expression_symbol("VOUT - VIN")
    assert _is_expression_symbol("VIN-VOUT")
    assert not _is_expression_symbol("VIN")
    assert not _is_expression_symbol("VREF")
    assert not _is_expression_symbol("V(IN)")
    assert not _is_expression_symbol("")


def test_vin_operating_does_not_capture_dropout_voltage():
    """R1: the AMS1117 dropout row must not become vin_operating."""
    hints = _extract_drc_hints("LDO", {}, {}, raw_elec=AMS1117_ELEC, raw_abs=AMS1117_ABS)
    vin_op = hints.get("vin_operating")
    if vin_op is not None:
        assert not (vin_op.get("typ") == 1.1 and vin_op.get("max") == 1.3), \
            f"vin_operating still captured the dropout voltage: {vin_op}"
    # AMS1117 has no genuine input-voltage-range row -> vin_operating absent.
    assert vin_op is None, f"expected no vin_operating for AMS1117, got {vin_op}"


def test_vin_abs_max_still_extracted():
    """The fix must not break the legitimate plain-symbol VIN match."""
    hints = _extract_drc_hints("LDO", {}, {}, raw_elec=AMS1117_ELEC, raw_abs=AMS1117_ABS)
    assert hints.get("vin_abs_max") == {"value": 15, "unit": "V"}


def test_vin_operating_extracted_for_real_input_range():
    """A genuine input-voltage-range row must still produce vin_operating."""
    elec = [
        {"parameter": "Input Voltage Range", "symbol": "VIN",
         "min": 2.7, "max": 5.5, "unit": "V"},
        {"parameter": "Dropout Voltage", "symbol": "VIN - VOUT",
         "typ": 0.3, "max": 0.5, "unit": "V"},
    ]
    hints = _extract_drc_hints("LDO", {}, {}, raw_elec=elec, raw_abs=[])
    assert hints.get("vin_operating") == {"min": 2.7, "max": 5.5, "unit": "V"}


# --- R2: parameter keys --------------------------------------------------

def test_unique_param_key_falls_back_and_never_overwrites():
    existing: dict = {}
    k1 = _unique_param_key({"symbol": "VIN"}, existing)
    existing[k1] = 1
    k2 = _unique_param_key({"symbol": "", "parameter": "Power Dissipation"}, existing)
    existing[k2] = 1
    k3 = _unique_param_key({"parameter": "ESD HBM"}, existing)
    existing[k3] = 1
    # symbol-less rows still produce a key
    assert k1 == "VIN" and k2 and k3
    # duplicate symbol + same/no condition does not collide
    k4 = _unique_param_key({"symbol": "VIN"}, existing)
    assert k4 != k1 and k4 not in existing


def test_symbolless_and_duplicate_params_are_preserved():
    """R2: every extracted row survives into the export, none dropped/overwritten."""
    data = {
        "extraction": {
            "component": {"mpn": "TESTKEY1", "manufacturer": "T",
                          "category": "Buck", "description": "test device"},
            "absolute_maximum_ratings": [
                {"parameter": "Input Voltage", "symbol": "VIN", "max": 15, "unit": "V"},
                {"parameter": "Power Dissipation", "symbol": "", "max": 1.5, "unit": "W"},
                {"parameter": "ESD HBM", "max": 2000, "unit": "V"},
            ],
            "electrical_characteristics": [
                {"parameter": "Output Voltage", "symbol": "VOUT", "typ": 3.3,
                 "unit": "V", "conditions": "VIN=5V"},
                {"parameter": "Output Voltage", "symbol": "VOUT", "typ": 1.8,
                 "unit": "V", "conditions": "VIN=5V"},
                {"parameter": "Output Voltage", "symbol": "VOUT", "typ": 5.0,
                 "unit": "V", "conditions": "VIN=12V"},
            ],
        },
        "pin_index": {"packages": {}},
        "design_extraction": {"design_page_candidates": []},
    }
    exported = export_normal_ic(data)
    abs_max = exported["absolute_maximum_ratings"]
    elec = exported["electrical_parameters"]

    assert len(abs_max) == 3, f"abs_max lost rows: {sorted(abs_max)}"
    assert sorted(v["parameter"] for v in abs_max.values()) == \
        ["ESD HBM", "Input Voltage", "Power Dissipation"]

    assert len(elec) == 3, f"elec lost rows: {sorted(elec)}"
    assert sorted(v["typ"] for v in elec.values()) == [1.8, 3.3, 5.0]


# --- freshness compare() helper -----------------------------------------

def test_compare_detects_changed_missing_removed():
    with tempfile.TemporaryDirectory() as live, tempfile.TemporaryDirectory() as fresh:
        live_dir, fresh_dir = Path(live), Path(fresh)
        (live_dir / "same.json").write_text('{"a":1}', encoding="utf-8")
        (fresh_dir / "same.json").write_text('{"a":1}', encoding="utf-8")
        (live_dir / "changed.json").write_text('{"a":1}', encoding="utf-8")
        (fresh_dir / "changed.json").write_text('{"a":2}', encoding="utf-8")
        (live_dir / "removed.json").write_text('{}', encoding="utf-8")
        (fresh_dir / "added.json").write_text('{}', encoding="utf-8")
        (live_dir / "_manifest.json").write_text('{}', encoding="utf-8")  # ignored

        diff = compare(live_dir, fresh_dir)
        assert diff["changed"] == ["changed.json"]
        assert diff["removed"] == ["removed.json"]
        assert diff["missing"] == ["added.json"]
        assert diff["total_live"] == 3  # same, changed, removed (_manifest ignored)


if __name__ == "__main__":
    failed = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"PASS {_name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {_name}: {exc}")
    print("OK" if not failed else f"{failed} FAILED")
    sys.exit(1 if failed else 0)
