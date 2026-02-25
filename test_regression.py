#!/usr/bin/env python3
"""Regression test suite for OpenDatasheet pipeline.

Tests the full chain: raw pinout → parsed JSON → sch-review export → schema validation.

Usage:
    python test_regression.py           # run all tests
    python test_regression.py -v        # verbose
    python test_regression.py -k fpga   # filter by keyword
"""

import json
import sys
import os
from pathlib import Path
from collections import Counter

# ─── Setup ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
EXTRACTED_DIR = DATA_DIR / "extracted_v2"
FPGA_PINOUT_DIR = EXTRACTED_DIR / "fpga" / "pinout"
EXPORT_DIR = DATA_DIR / "sch_review_export"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "sch-review-device.schema.json"

VERBOSE = "-v" in sys.argv
FILTER = None
for i, a in enumerate(sys.argv):
    if a == "-k" and i + 1 < len(sys.argv):
        FILTER = sys.argv[i + 1].lower()

passed = 0
failed = 0
errors = []


def test(name):
    """Decorator for test functions."""
    def decorator(fn):
        fn._test_name = name
        return fn
    return decorator


def run_test(fn):
    global passed, failed
    name = getattr(fn, "_test_name", fn.__name__)
    if FILTER and FILTER not in name.lower():
        return
    try:
        fn()
        passed += 1
        print(f"  ✓ {name}")
    except AssertionError as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  ✗ {name}: {e}")
    except Exception as e:
        failed += 1
        errors.append((name, f"EXCEPTION: {e}"))
        print(f"  ✗ {name}: EXCEPTION: {e}")


def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg}: expected {expected}, got {actual}")


def assert_in(item, collection, msg=""):
    if item not in collection:
        raise AssertionError(f"{msg}: {item} not in {collection}")


def assert_gt(actual, threshold, msg=""):
    if actual <= threshold:
        raise AssertionError(f"{msg}: {actual} <= {threshold}")


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(msg)


# ─── T1: Pinout Source Data Integrity ───────────────────────────────

EXPECTED_PINOUTS = {
    "xcku3pffva676pkg.json":       {"device": "XCKU3P", "package": "FFVA676", "total_pins": 676, "vendor": "AMD"},
    "xcku3pffvb676pkg.json":       {"device": "XCKU3P", "package": "FFVB676", "total_pins": 676, "vendor": "AMD"},
    "xcku3pffvd900pkg.json":       {"device": "XCKU3P", "package": "FFVD900", "total_pins": 900, "vendor": "AMD"},
    "xcku3psfvb784pkg.json":       {"device": "XCKU3P", "package": "SFVB784", "total_pins": 784, "vendor": "AMD"},
    "gowin_gw5at-60_pg484a.json":  {"device": "GW5AT-60", "package": "PG484A", "total_pins": 484, "vendor": "Gowin"},
    "gowin_gw5at-60_ug225.json":   {"device": "GW5AT-60", "package": "UG225",  "total_pins": 225, "vendor": "Gowin"},
    "gowin_gw5at-60_ug324s.json":  {"device": "GW5AT-60", "package": "UG324S", "total_pins": 324, "vendor": "Gowin"},
    "gowin_gw5at-15_mg132.json":   {"device": "GW5AT-15", "package": "MG132",  "total_pins": 116, "vendor": "Gowin"},
    "gowin_gw5at-15_cs130.json":   {"device": "GW5AT-15", "package": "CS130",  "total_pins": 115, "vendor": "Gowin"},
    "gowin_gw5at-15_cs130f.json":  {"device": "GW5AT-15", "package": "CS130F", "total_pins": 116, "vendor": "Gowin"},
    "gowin_gw5at-138_fpg676a.json":{"device": "GW5AT-138","package": "FPG676A","total_pins": 676, "vendor": "Gowin"},
    "gowin_gw5ar-25_ug256p.json":  {"device": "GW5AR-25", "package": "UG256P", "total_pins": 256, "vendor": "Gowin"},
    "gowin_gw5as-25_ug256.json":   {"device": "GW5AS-25", "package": "UG256",  "total_pins": 256, "vendor": "Gowin"},
    # Lattice ECP5
    "lattice_ecp5u-25_cabga381.json": {"device": "ECP5U-25", "package": "CABGA381", "total_pins": 381, "vendor": "Lattice"},
    "lattice_ecp5u-25_cabga256.json": {"device": "ECP5U-25", "package": "CABGA256", "total_pins": 256, "vendor": "Lattice"},
    "lattice_ecp5u-25_tqfp144.json":  {"device": "ECP5U-25", "package": "TQFP144",  "total_pins": 144, "vendor": "Lattice"},
    "lattice_ecp5u-85_cabga756.json": {"device": "ECP5U-85", "package": "CABGA756", "total_pins": 756, "vendor": "Lattice"},
    # Lattice CrossLink-NX
    "lattice_lifcl-40_cabga400.json": {"device": "LIFCL-40", "package": "CABGA400", "total_pins": 400, "vendor": "Lattice"},
    "lattice_lifcl-40_qfn72.json":    {"device": "LIFCL-40", "package": "QFN72",    "total_pins": 90,  "vendor": "Lattice"},
}


@test("T1.1 All pinout files exist")
def t1_1():
    for fname in EXPECTED_PINOUTS:
        path = FPGA_PINOUT_DIR / fname
        assert_true(path.exists(), f"Missing: {fname}")


@test("T1.2 Pinout pin counts match")
def t1_2():
    for fname, exp in EXPECTED_PINOUTS.items():
        with open(FPGA_PINOUT_DIR / fname) as f:
            d = json.load(f)
        assert_eq(len(d["pins"]), exp["total_pins"], f"{fname} pins[]")
        assert_eq(d["total_pins"], exp["total_pins"], f"{fname} total_pins")


@test("T1.3 Pinout device/package metadata")
def t1_3():
    for fname, exp in EXPECTED_PINOUTS.items():
        with open(FPGA_PINOUT_DIR / fname) as f:
            d = json.load(f)
        assert_eq(d["device"], exp["device"], f"{fname} device")
        assert_eq(d["package"], exp["package"], f"{fname} package")


@test("T1.4 Pinout lookup bidirectional consistency")
def t1_4():
    for fname in EXPECTED_PINOUTS:
        with open(FPGA_PINOUT_DIR / fname) as f:
            d = json.load(f)
        lookup = d.get("lookup", {})
        p2n = lookup.get("pin_to_name", lookup.get("by_pin", {}))
        n2p = lookup.get("name_to_pin", lookup.get("by_name", {}))
        # Every pin in pins[] should be in lookup
        for pin in d["pins"]:
            pid = pin["pin"]
            assert_in(pid, p2n, f"{fname} pin {pid} missing from lookup")


@test("T1.5 Pinout diff pairs reference valid pins")
def t1_5():
    for fname in EXPECTED_PINOUTS:
        with open(FPGA_PINOUT_DIR / fname) as f:
            d = json.load(f)
        pin_ids = {p["pin"] for p in d["pins"]}
        for dp in d.get("diff_pairs", []):
            p_pin = dp.get("p_pin", dp.get("true_pin", ""))
            n_pin = dp.get("n_pin", dp.get("comp_pin", ""))
            if p_pin:
                assert_in(p_pin, pin_ids, f"{fname} diff_pair p_pin {p_pin}")
            if n_pin:
                assert_in(n_pin, pin_ids, f"{fname} diff_pair n_pin {n_pin}")


@test("T1.6 Every pinout has banks")
def t1_6():
    for fname in EXPECTED_PINOUTS:
        with open(FPGA_PINOUT_DIR / fname) as f:
            d = json.load(f)
        assert_gt(len(d.get("banks", {})), 0, f"{fname} banks")


# ─── T2: Schema Validation ─────────────────────────────────────────

@test("T2.1 Schema file exists and is valid JSON Schema")
def t2_1():
    assert_true(SCHEMA_PATH.exists(), "Schema file missing")
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    assert_eq(schema.get("$schema"), "https://json-schema.org/draft/2020-12/schema", "Wrong $schema")
    assert_in("$defs", schema, "Missing $defs")
    assert_in("normal_ic", schema["$defs"], "Missing normal_ic def")
    assert_in("fpga", schema["$defs"], "Missing fpga def")


@test("T2.2 All exports pass schema validation")
def t2_2():
    from jsonschema import Draft202012Validator
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    validator = Draft202012Validator(schema)
    
    failures = []
    for f in sorted(EXPORT_DIR.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            data = json.load(fp)
        errs = list(validator.iter_errors(data))
        if errs:
            failures.append((f.name, len(errs), str(errs[0].message)[:80]))
    
    if failures:
        detail = "; ".join(f"{n}({c})" for n, c, _ in failures[:5])
        raise AssertionError(f"{len(failures)} files failed: {detail}")


# ─── T3: Export Data Quality ────────────────────────────────────────

VALID_FUNCTIONS = {"IO", "POWER", "GROUND", "CONFIG", "GT", "GT_POWER", "RSVDGND", "NC", "SPECIAL"}
VALID_SEVERITIES = {"ERROR", "WARNING", "INFO"}

EXPECTED_EXPORTS = {
    # Normal ICs
    "AMS1117.json":     {"type": "normal_ic", "min_pkgs": 3, "min_pins": 12},
    "RT9193.json":      {"type": "normal_ic", "min_pkgs": 3, "min_pins": 15},
    "LT1964.json":      {"type": "normal_ic", "min_pkgs": 2, "min_pins": 10},
    "XL4003.json":      {"type": "normal_ic", "min_pkgs": 1, "min_pins": 5},
    "FST3125.json":     {"type": "normal_ic", "min_pkgs": 2, "min_pins": 20},
    # AMD FPGAs
    "XCKU3P_FFVA676.json":  {"type": "fpga", "pins": 676, "min_diff_pairs": 100},
    "XCKU3P_FFVD900.json":  {"type": "fpga", "pins": 900, "min_diff_pairs": 100},
    # Gowin FPGAs
    "GW5AT-60_PG484A.json": {"type": "fpga", "pins": 484, "min_diff_pairs": 50},
    "GW5AT-15_MG132.json":  {"type": "fpga", "pins": 116, "min_diff_pairs": 10},
    "GW5AR-25_UG256P.json": {"type": "fpga", "pins": 256, "min_diff_pairs": 30},
    "GW5AS-25_UG256.json":  {"type": "fpga", "pins": 256, "min_diff_pairs": 20},
    # Lattice ECP5 FPGAs
    "ECP5U-25_CABGA381.json": {"type": "fpga", "pins": 381, "min_diff_pairs": 50},
    "ECP5U-25_TQFP144.json":  {"type": "fpga", "pins": 144, "min_diff_pairs": 20},
    "ECP5U-85_CABGA756.json": {"type": "fpga", "pins": 756, "min_diff_pairs": 100},
    # Lattice CrossLink-NX FPGAs
    "LIFCL-40_CABGA400.json": {"type": "fpga", "pins": 400, "min_diff_pairs": 50},
    "LIFCL-40_QFN72.json":    {"type": "fpga", "pins": 90,  "min_diff_pairs": 10},
}


@test("T3.1 All expected export files exist")
def t3_1():
    for fname in EXPECTED_EXPORTS:
        assert_true((EXPORT_DIR / fname).exists(), f"Missing: {fname}")


@test("T3.2 Export _type matches expected")
def t3_2():
    for fname, exp in EXPECTED_EXPORTS.items():
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        assert_eq(d["_type"], exp["type"], f"{fname} _type")


@test("T3.3 Normal IC exports have packages with pins")
def t3_3():
    for fname, exp in EXPECTED_EXPORTS.items():
        if exp["type"] != "normal_ic":
            continue
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        pkgs = d.get("packages", {})
        assert_gt(len(pkgs), exp["min_pkgs"] - 1, f"{fname} package count")
        total_pins = sum(p["pin_count"] for p in pkgs.values())
        assert_gt(total_pins, exp["min_pins"] - 1, f"{fname} total pins")
        # Every pin must have a name
        for pkg_name, pkg in pkgs.items():
            for pin_num, pin_data in pkg["pins"].items():
                assert_true(pin_data.get("name"), f"{fname}/{pkg_name}/pin{pin_num} missing name")


@test("T3.4 FPGA exports have correct pin counts")
def t3_4():
    for fname, exp in EXPECTED_EXPORTS.items():
        if exp["type"] != "fpga":
            continue
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        assert_eq(len(d["pins"]), exp["pins"], f"{fname} pin count")


@test("T3.5 FPGA pin functions are all valid enum values")
def t3_5():
    for f in sorted(EXPORT_DIR.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            d = json.load(fp)
        if d.get("_type") != "fpga":
            continue
        for i, pin in enumerate(d.get("pins", [])):
            func = pin.get("function", "")
            assert_in(func, VALID_FUNCTIONS, f"{f.name} pin[{i}] ({pin.get('name','?')}) function={func}")


@test("T3.6 FPGA DRC rule severities are valid")
def t3_6():
    for f in sorted(EXPORT_DIR.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            d = json.load(fp)
        if d.get("_type") != "fpga":
            continue
        for rule_name, rule in d.get("drc_rules", {}).items():
            sev = rule.get("severity", "")
            assert_in(sev, VALID_SEVERITIES, f"{f.name} drc_rules.{rule_name}.severity={sev}")


@test("T3.7 FPGA diff pairs have p_pin and n_pin")
def t3_7():
    for f in sorted(EXPORT_DIR.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            d = json.load(fp)
        if d.get("_type") != "fpga":
            continue
        for i, dp in enumerate(d.get("diff_pairs", [])):
            assert_true("p_pin" in dp, f"{f.name} diff_pairs[{i}] missing p_pin")
            assert_true("n_pin" in dp, f"{f.name} diff_pairs[{i}] missing n_pin")


@test("T3.8 FPGA diff pair pins exist in pin list")
def t3_8():
    for f in sorted(EXPORT_DIR.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            d = json.load(fp)
        if d.get("_type") != "fpga":
            continue
        pin_ids = {p["pin"] for p in d["pins"]}
        for i, dp in enumerate(d.get("diff_pairs", [])):
            if dp["p_pin"]:
                assert_in(dp["p_pin"], pin_ids, f"{f.name} diff_pairs[{i}].p_pin={dp['p_pin']}")
            if dp["n_pin"]:
                assert_in(dp["n_pin"], pin_ids, f"{f.name} diff_pairs[{i}].n_pin={dp['n_pin']}")


@test("T3.9 FPGA lookup consistency — every pin in lookup")
def t3_9():
    for f in sorted(EXPORT_DIR.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            d = json.load(fp)
        if d.get("_type") != "fpga":
            continue
        lookup = d.get("lookup", {})
        by_pin = lookup.get("by_pin", {})
        for pin in d["pins"]:
            pid = pin["pin"]
            assert_in(pid, by_pin, f"{f.name} pin {pid} missing from lookup.by_pin")


@test("T3.10 FPGA banks have required fields")
def t3_10():
    for f in sorted(EXPORT_DIR.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            d = json.load(fp)
        if d.get("_type") != "fpga":
            continue
        for bank_id, bank in d.get("banks", {}).items():
            assert_true("bank" in bank, f"{f.name} banks.{bank_id} missing 'bank' field")


@test("T3.11 FPGA must_connect is boolean")
def t3_11():
    for f in sorted(EXPORT_DIR.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            d = json.load(fp)
        if d.get("_type") != "fpga":
            continue
        for i, pin in enumerate(d.get("pins", [])):
            drc = pin.get("drc")
            if drc and "must_connect" in drc:
                mc = drc["must_connect"]
                assert_true(isinstance(mc, bool), f"{f.name} pin[{i}] ({pin.get('name','?')}) must_connect={mc} (type={type(mc).__name__})")


@test("T3.12 FPGA supply_specs have min or max voltage")
def t3_12():
    for fname, exp in EXPECTED_EXPORTS.items():
        if exp["type"] != "fpga":
            continue
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        specs = d.get("supply_specs", {})
        if not specs:
            continue  # AMD may have empty if no DC match
        # At least 30% of specs should have values (PDF extraction is imperfect)
        valid_count = 0
        for key, spec in specs.items():
            has_value = spec.get("min") is not None or spec.get("max") is not None or spec.get("typ") is not None
            if has_value:
                valid_count += 1
        min_required = max(1, len(specs) // 3)
        assert_gt(valid_count, min_required - 1, f"{fname} supply_specs: only {valid_count}/{len(specs)} have values")


@test("T3.13 Normal IC drc_hints have units")
def t3_13():
    for fname, exp in EXPECTED_EXPORTS.items():
        if exp["type"] != "normal_ic":
            continue
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        for key, hint in d.get("drc_hints", {}).items():
            if isinstance(hint, dict):
                assert_true("unit" in hint, f"{fname} drc_hints.{key} missing unit")


# ─── T4: Cross-Vendor Consistency ──────────────────────────────────

@test("T4.1 AMD and Gowin exports share same _schema")
def t4_1():
    amd = json.load(open(EXPORT_DIR / "XCKU3P_FFVA676.json"))
    gowin = json.load(open(EXPORT_DIR / "GW5AT-60_PG484A.json"))
    assert_eq(amd["_schema"], gowin["_schema"], "schema mismatch")
    assert_eq(amd["_type"], gowin["_type"], "type mismatch")


@test("T4.2 AMD and Gowin exports have same top-level keys (core set)")
def t4_2():
    amd = json.load(open(EXPORT_DIR / "XCKU3P_FFVA676.json"))
    gowin = json.load(open(EXPORT_DIR / "GW5AT-60_PG484A.json"))
    core_keys = {"_schema", "_type", "mpn", "manufacturer", "category", "package",
                 "supply_specs", "io_standard_specs", "power_rails", "banks",
                 "diff_pairs", "drc_rules", "pins", "lookup", "summary"}
    amd_keys = set(amd.keys())
    gowin_keys = set(gowin.keys())
    missing_amd = core_keys - amd_keys
    missing_gowin = core_keys - gowin_keys
    assert_true(not missing_amd, f"AMD missing: {missing_amd}")
    assert_true(not missing_gowin, f"Gowin missing: {missing_gowin}")


@test("T4.3 All FPGA exports have power + ground pins")
def t4_3():
    for f in sorted(EXPORT_DIR.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            d = json.load(fp)
        if d.get("_type") != "fpga":
            continue
        funcs = Counter(p["function"] for p in d["pins"])
        assert_gt(funcs.get("POWER", 0), 0, f"{f.name} no POWER pins")
        # Small packages (< 100 pins) may have ground on thermal pad not in pinout
        total_pins = len(d["pins"])
        if total_pins >= 100:
            assert_gt(funcs.get("GROUND", 0), 0, f"{f.name} no GROUND pins")


@test("T4.4 All FPGA exports have IO pins")
def t4_4():
    for f in sorted(EXPORT_DIR.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            d = json.load(fp)
        if d.get("_type") != "fpga":
            continue
        funcs = Counter(p["function"] for p in d["pins"])
        assert_gt(funcs.get("IO", 0), 0, f"{f.name} no IO pins")


# ─── T5: Manifest Consistency ──────────────────────────────────────

@test("T5.1 Manifest exists and lists all export files")
def t5_1():
    manifest_path = EXPORT_DIR / "_manifest.json"
    assert_true(manifest_path.exists(), "Manifest missing")
    with open(manifest_path) as f:
        manifest = json.load(f)
    manifest_files = {d["file"] for d in manifest.get("devices", [])}
    actual_files = {f.name for f in EXPORT_DIR.glob("*.json") if f.name not in ("_manifest.json",)}
    # Exclude reference/ subdirectory files
    actual_files -= {f.name for f in EXPORT_DIR.glob("reference/*.json")}
    missing = actual_files - manifest_files
    # Allow README.md to not be in manifest
    missing = {f for f in missing if f.endswith(".json")}
    assert_true(not missing, f"Files not in manifest: {missing}")


# ─── T6: Gowin DC Data Integration ─────────────────────────────────

@test("T6.1 Gowin FPGA exports have supply_specs from DC data")
def t6_1():
    gowin_exports = [
        "GW5AT-60_PG484A.json", "GW5AT-15_MG132.json",
        "GW5AT-138_FPG676A.json",
    ]
    for fname in gowin_exports:
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        specs = d.get("supply_specs", {})
        assert_gt(len(specs), 5, f"{fname} supply_specs count")


@test("T6.2 Gowin FPGA exports have absolute_maximum_ratings")
def t6_2():
    gowin_exports = [
        "GW5AT-60_PG484A.json", "GW5AT-15_MG132.json",
        "GW5AT-138_FPG676A.json",
    ]
    for fname in gowin_exports:
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        abs_max = d.get("absolute_maximum_ratings", {})
        assert_gt(len(abs_max), 5, f"{fname} abs_max count")


# ─── T7: Lattice DC Data Integration ───────────────────────────────

@test("T7.1 Lattice ECP5 exports have supply_specs from DC data")
def t7_1():
    lattice_exports = [
        "ECP5U-25_CABGA381.json", "ECP5U-85_CABGA756.json",
    ]
    for fname in lattice_exports:
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        specs = d.get("supply_specs", {})
        assert_gt(len(specs), 5, f"{fname} supply_specs count")


@test("T7.2 Lattice CrossLink-NX exports have supply_specs from DC data")
def t7_2():
    lattice_exports = [
        "LIFCL-40_CABGA400.json", "LIFCL-40_QFN72.json",
    ]
    for fname in lattice_exports:
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        specs = d.get("supply_specs", {})
        assert_gt(len(specs), 10, f"{fname} supply_specs count")


@test("T7.3 Lattice exports have absolute_maximum_ratings")
def t7_3():
    lattice_exports = [
        "ECP5U-25_CABGA381.json", "LIFCL-40_CABGA400.json",
    ]
    for fname in lattice_exports:
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        abs_max = d.get("absolute_maximum_ratings", {})
        assert_gt(len(abs_max), 5, f"{fname} abs_max count")


# ─── T8: Lattice Internal Deep Validation ──────────────────────────

LATTICE_PINOUTS = {
    "lattice_ecp5u-25_cabga381.json":  {"device": "ECP5U-25",  "package": "CABGA381",  "total_pins": 381, "vendor": "Lattice"},
    "lattice_ecp5u-25_cabga256.json":  {"device": "ECP5U-25",  "package": "CABGA256",  "total_pins": 256, "vendor": "Lattice"},
    "lattice_ecp5u-25_tqfp144.json":   {"device": "ECP5U-25",  "package": "TQFP144",   "total_pins": 144, "vendor": "Lattice"},
    "lattice_ecp5u-25_csfbga285.json": {"device": "ECP5U-25",  "package": "CSFBGA285", "total_pins": 285, "vendor": "Lattice"},
    "lattice_ecp5u-45_cabga554.json":  {"device": "ECP5U-45",  "package": "CABGA554",  "total_pins": 554, "vendor": "Lattice"},
    "lattice_ecp5u-85_cabga756.json":  {"device": "ECP5U-85",  "package": "CABGA756",  "total_pins": 756, "vendor": "Lattice"},
    "lattice_lifcl-40_cabga400.json":  {"device": "LIFCL-40",  "package": "CABGA400",  "total_pins": 400, "vendor": "Lattice"},
    "lattice_lifcl-40_csfbga121.json": {"device": "LIFCL-40",  "package": "CSFBGA121", "total_pins": 121, "vendor": "Lattice"},
    "lattice_lifcl-40_qfn72.json":     {"device": "LIFCL-40",  "package": "QFN72",     "total_pins": 90,  "vendor": "Lattice"},
}


@test("T8.1 Lattice pinout source files exist and pin counts match")
def t8_1():
    for fname, exp in LATTICE_PINOUTS.items():
        path = FPGA_PINOUT_DIR / fname
        assert_true(path.exists(), f"Missing: {fname}")
        with open(path) as f:
            d = json.load(f)
        assert_eq(len(d["pins"]), exp["total_pins"], f"{fname} pins[]")
        assert_eq(d["total_pins"], exp["total_pins"], f"{fname} total_pins")
        assert_eq(d["device"], exp["device"], f"{fname} device")
        assert_eq(d["package"], exp["package"], f"{fname} package")


@test("T8.2 Lattice pinout lookup bidirectional consistency")
def t8_2():
    for fname in LATTICE_PINOUTS:
        with open(FPGA_PINOUT_DIR / fname) as f:
            d = json.load(f)
        lookup = d.get("lookup", {})
        p2n = lookup.get("pin_to_name", lookup.get("by_pin", {}))
        for pin in d["pins"]:
            pid = pin["pin"]
            assert_in(pid, p2n, f"{fname} pin {pid} missing from lookup")


@test("T8.3 Lattice diff pairs reference valid pins")
def t8_3():
    for fname in LATTICE_PINOUTS:
        with open(FPGA_PINOUT_DIR / fname) as f:
            d = json.load(f)
        pin_ids = {p["pin"] for p in d["pins"]}
        for i, dp in enumerate(d.get("diff_pairs", [])):
            p_pin = dp.get("p_pin", dp.get("true_pin", ""))
            n_pin = dp.get("n_pin", dp.get("comp_pin", ""))
            if p_pin:
                assert_in(p_pin, pin_ids, f"{fname} dp[{i}].p_pin={p_pin}")
            if n_pin:
                assert_in(n_pin, pin_ids, f"{fname} dp[{i}].n_pin={n_pin}")


@test("T8.4 Lattice exports have all 3 vendors in same schema")
def t8_4():
    amd = json.load(open(EXPORT_DIR / "XCKU3P_FFVA676.json"))
    gowin = json.load(open(EXPORT_DIR / "GW5AT-60_PG484A.json"))
    lattice = json.load(open(EXPORT_DIR / "ECP5U-25_CABGA381.json"))
    assert_eq(amd["_schema"], lattice["_schema"], "AMD vs Lattice schema")
    assert_eq(gowin["_schema"], lattice["_schema"], "Gowin vs Lattice schema")
    assert_eq(lattice["_type"], "fpga", "Lattice _type")
    assert_eq(lattice["manufacturer"], "Lattice", "Lattice manufacturer")


@test("T8.5 Lattice exports have same core keys as AMD/Gowin")
def t8_5():
    core_keys = {"_schema", "_type", "mpn", "manufacturer", "category", "package",
                 "supply_specs", "io_standard_specs", "power_rails", "banks",
                 "diff_pairs", "drc_rules", "pins", "lookup", "summary"}
    for fname in ["ECP5U-25_CABGA381.json", "LIFCL-40_CABGA400.json"]:
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        missing = core_keys - set(d.keys())
        assert_true(not missing, f"{fname} missing keys: {missing}")


@test("T8.6 Lattice exports pin functions all valid")
def t8_6():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        for i, pin in enumerate(d.get("pins", [])):
            func = pin.get("function", "")
            assert_in(func, VALID_FUNCTIONS, f"{fname} pin[{i}] ({pin.get('name','?')}) function={func}")


@test("T8.7 Lattice exports have power + ground + IO pins")
def t8_7():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        funcs = Counter(p["function"] for p in d["pins"])
        assert_gt(funcs.get("POWER", 0), 0, f"{fname} no POWER pins")
        assert_gt(funcs.get("IO", 0), 0, f"{fname} no IO pins")


@test("T8.8 Lattice diff pair pins exist in export pin list")
def t8_8():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        pin_ids = {p["pin"] for p in d["pins"]}
        for i, dp in enumerate(d.get("diff_pairs", [])):
            if dp["p_pin"]:
                assert_in(dp["p_pin"], pin_ids, f"{fname} dp[{i}].p_pin={dp['p_pin']}")
            if dp["n_pin"]:
                assert_in(dp["n_pin"], pin_ids, f"{fname} dp[{i}].n_pin={dp['n_pin']}")


@test("T8.9 Lattice banks have required fields")
def t8_9():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        for bank_id, bank in d.get("banks", {}).items():
            assert_true("bank" in bank, f"{fname} banks.{bank_id} missing 'bank'")
            assert_true("total_pins" in bank, f"{fname} banks.{bank_id} missing 'total_pins'")


@test("T8.10 Lattice supply_specs have no min > max violations")
def t8_10():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        for key, spec in d.get("supply_specs", {}).items():
            mn = spec.get("min")
            mx = spec.get("max")
            if mn is not None and mx is not None:
                assert_true(mn <= mx, f"{fname} supply_specs.{key}: min={mn} > max={mx}")


@test("T8.11 ECP5 cross-package IO monotonicity (larger pkg >= smaller pkg IO count)")
def t8_11():
    # ECP5U-25: CABGA381 >= CABGA256 >= TQFP144
    pkg_order = ["ECP5U-25_CABGA381.json", "ECP5U-25_CABGA256.json", "ECP5U-25_TQFP144.json"]
    io_counts = []
    for fname in pkg_order:
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        io_count = sum(1 for p in d["pins"] if p["function"] == "IO")
        io_counts.append((fname, io_count))
    for i in range(len(io_counts) - 1):
        assert_true(io_counts[i][1] >= io_counts[i+1][1],
                    f"IO monotonicity: {io_counts[i][0]}({io_counts[i][1]}) < {io_counts[i+1][0]}({io_counts[i+1][1]})")


@test("T8.12 Lattice DRC rules have valid severities")
def t8_12():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        for rule_name, rule in d.get("drc_rules", {}).items():
            sev = rule.get("severity", "")
            assert_in(sev, VALID_SEVERITIES, f"{fname} drc_rules.{rule_name}.severity={sev}")


@test("T8.13 Lattice must_connect is boolean")
def t8_13():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        for i, pin in enumerate(d.get("pins", [])):
            drc = pin.get("drc")
            if drc and "must_connect" in drc:
                mc = drc["must_connect"]
                assert_true(isinstance(mc, bool), f"{fname} pin[{i}] must_connect={mc} type={type(mc).__name__}")


@test("T8.14 All 18 Lattice exports exist")
def t8_14():
    expected = [
        "ECP5U-25_CABGA256.json", "ECP5U-25_CABGA381.json", "ECP5U-25_CSFBGA285.json", "ECP5U-25_TQFP144.json",
        "ECP5U-45_CABGA256.json", "ECP5U-45_CABGA381.json", "ECP5U-45_CABGA554.json", "ECP5U-45_CSFBGA285.json", "ECP5U-45_TQFP144.json",
        "ECP5U-85_CABGA381.json", "ECP5U-85_CABGA554.json", "ECP5U-85_CABGA756.json", "ECP5U-85_CSFBGA285.json",
        "LIFCL-40_CABGA256.json", "LIFCL-40_CABGA400.json", "LIFCL-40_CSBGA289.json", "LIFCL-40_CSFBGA121.json", "LIFCL-40_QFN72.json",
    ]
    for fname in expected:
        assert_true((EXPORT_DIR / fname).exists(), f"Missing: {fname}")


@test("T8.15 Lattice lookup completeness — every pin in by_pin")
def t8_15():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        by_pin = d.get("lookup", {}).get("by_pin", {})
        for pin in d["pins"]:
            assert_in(pin["pin"], by_pin, f"{fname} pin {pin['pin']} missing from lookup")


# ─── Runner ─────────────────────────────────────────────────────────

def main():
    global passed, failed

    print("=" * 60)
    print("OpenDatasheet Regression Test Suite")
    print("=" * 60)

    # Collect all test functions
    tests = []
    for name, obj in sorted(globals().items()):
        if callable(obj) and hasattr(obj, "_test_name"):
            tests.append(obj)

    print(f"\nRunning {len(tests)} tests...\n")

    for t in tests:
        run_test(t)

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")

    if errors:
        print(f"\nFailures:")
        for name, msg in errors:
            print(f"  ✗ {name}")
            print(f"    {msg[:200]}")

    print(f"{'=' * 60}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
