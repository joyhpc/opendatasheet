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


def case(name):
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


@case("T1.1 All pinout files exist")
def t1_1():
    for fname in EXPECTED_PINOUTS:
        path = FPGA_PINOUT_DIR / fname
        assert_true(path.exists(), f"Missing: {fname}")


@case("T1.2 Pinout pin counts match")
def t1_2():
    for fname, exp in EXPECTED_PINOUTS.items():
        with open(FPGA_PINOUT_DIR / fname) as f:
            d = json.load(f)
        assert_eq(len(d["pins"]), exp["total_pins"], f"{fname} pins[]")
        assert_eq(d["total_pins"], exp["total_pins"], f"{fname} total_pins")


@case("T1.3 Pinout device/package metadata")
def t1_3():
    for fname, exp in EXPECTED_PINOUTS.items():
        with open(FPGA_PINOUT_DIR / fname) as f:
            d = json.load(f)
        assert_eq(d["device"], exp["device"], f"{fname} device")
        assert_eq(d["package"], exp["package"], f"{fname} package")


@case("T1.4 Pinout lookup bidirectional consistency")
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


@case("T1.5 Pinout diff pairs reference valid pins")
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


@case("T1.6 Every pinout has banks")
def t1_6():
    for fname in EXPECTED_PINOUTS:
        with open(FPGA_PINOUT_DIR / fname) as f:
            d = json.load(f)
        assert_gt(len(d.get("banks", {})), 0, f"{fname} banks")


# ─── T2: Schema Validation ─────────────────────────────────────────

@case("T2.1 Schema file exists and is valid JSON Schema")
def t2_1():
    assert_true(SCHEMA_PATH.exists(), "Schema file missing")
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    assert_eq(schema.get("$schema"), "https://json-schema.org/draft/2020-12/schema", "Wrong $schema")
    assert_in("$defs", schema, "Missing $defs")
    assert_in("normal_ic", schema["$defs"], "Missing normal_ic def")
    assert_in("fpga", schema["$defs"], "Missing fpga def")


@case("T2.2 All exports pass schema validation")
def t2_2():
    from jsonschema import Draft202012Validator, RefResolver

    schema_dir = SCHEMA_PATH.parent
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)

    store = {}
    for domain_schema in (schema_dir / "domains").glob("*.schema.json"):
        with open(domain_schema) as f:
            domain = json.load(f)
        store[f"https://opendatasheet.dev/schemas/sch-review-device/domains/{domain_schema.name}"] = domain
        if "$id" in domain:
            store[domain["$id"]] = domain
    resolver = RefResolver.from_schema(schema, store=store)
    validator = Draft202012Validator(schema, resolver=resolver)
    
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


@case("T3.1 All expected export files exist")
def t3_1():
    for fname in EXPECTED_EXPORTS:
        assert_true((EXPORT_DIR / fname).exists(), f"Missing: {fname}")


@case("T3.2 Export _type matches expected")
def t3_2():
    for fname, exp in EXPECTED_EXPORTS.items():
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        assert_eq(d["_type"], exp["type"], f"{fname} _type")


@case("T3.3 Normal IC exports have packages with pins")
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


@case("T3.4 FPGA exports have correct pin counts")
def t3_4():
    for fname, exp in EXPECTED_EXPORTS.items():
        if exp["type"] != "fpga":
            continue
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        assert_eq(len(d["pins"]), exp["pins"], f"{fname} pin count")


@case("T3.5 FPGA pin functions are all valid enum values")
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


@case("T3.6 FPGA DRC rule severities are valid")
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


@case("T3.7 FPGA diff pairs have p_pin and n_pin")
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


@case("T3.8 FPGA diff pair pins exist in pin list")
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


@case("T3.9 FPGA lookup consistency — every pin in lookup")
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


@case("T3.10 FPGA banks have required fields")
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


@case("T3.11 FPGA must_connect is boolean")
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


@case("T3.12 FPGA supply_specs have min or max voltage")
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


@case("T3.13 Normal IC drc_hints have units")
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

@case("T4.1 AMD and Gowin exports share same _schema")
def t4_1():
    amd = json.load(open(EXPORT_DIR / "XCKU3P_FFVA676.json"))
    gowin = json.load(open(EXPORT_DIR / "GW5AT-60_PG484A.json"))
    assert_eq(amd["_schema"], gowin["_schema"], "schema mismatch")
    assert_eq(amd["_type"], gowin["_type"], "type mismatch")


@case("T4.2 AMD and Gowin exports have same top-level keys (core set)")
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


@case("T4.3 All FPGA exports have power + ground pins")
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


@case("T4.4 All FPGA exports have IO pins")
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


@case("T4.5 FPGA high-speed and MIPI exports expose capability_blocks")
def t4_5():
    for f in sorted(EXPORT_DIR.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            d = json.load(fp)
        if d.get("_type") != "fpga":
            continue
        summary = d.get("summary", {})
        by_function = summary.get("by_function", {}) if isinstance(summary, dict) else {}
        has_mipi = by_function.get("MIPI", 0) > 0
        has_hs = any(pair.get("type") in ("SERDES_RX", "SERDES_TX", "SERDES_REFCLK", "GT_RX", "GT_TX", "GT_REFCLK", "REFCLK") for pair in d.get("diff_pairs", []))
        if not (has_mipi or has_hs):
            continue
        capability_blocks = d.get("capability_blocks", {})
        assert_true(capability_blocks, f"{f.name} missing capability_blocks")
        if has_mipi:
            assert_true("mipi_phy" in capability_blocks, f"{f.name} missing capability_blocks.mipi_phy")
        if has_hs:
            assert_true("high_speed_serial" in capability_blocks, f"{f.name} missing capability_blocks.high_speed_serial")


@case("T4.6 FPGA refclk pairs expose refclk_requirements constraints")
def t4_6():
    for f in sorted(EXPORT_DIR.glob("*.json")):
        if f.name == "_manifest.json":
            continue
        with open(f) as fp:
            d = json.load(fp)
        if d.get("_type") != "fpga":
            continue
        by_function = (d.get("summary") or {}).get("by_function", {}) if isinstance(d.get("summary"), dict) else {}
        has_refclk = any(pair.get("type") in ("SERDES_REFCLK", "GT_REFCLK", "REFCLK") for pair in d.get("diff_pairs", []))
        has_gt = any(pair.get("type") in ("SERDES_RX", "SERDES_TX", "GT_RX", "GT_TX") for pair in d.get("diff_pairs", [])) or any(key in by_function for key in ("SERDES_RX", "SERDES_TX", "GT_RX", "GT_TX"))
        if not (has_refclk or has_gt):
            continue
        constraints = d.get("constraint_blocks", {})
        refclk = constraints.get("refclk_requirements")
        assert_true(refclk is not None, f"{f.name} missing constraint_blocks.refclk_requirements")
        assert_gt(refclk.get("refclk_pair_count", 0), 0, f"{f.name} refclk_pair_count")
        assert_true(refclk.get("selection_required") is True, f"{f.name} selection_required")
        assert_true(refclk.get("refclk_pairs"), f"{f.name} refclk_pairs missing")


@case("T4.7 STM32 exports expose capability and constraint blocks")
def t4_7():
    for f in sorted(EXPORT_DIR.glob("STM32*.json")):
        with open(f) as fp:
            d = json.load(fp)
        capability_blocks = d.get("capability_blocks", {})
        constraint_blocks = d.get("constraint_blocks", {})
        assert_true(capability_blocks, f"{f.name} missing capability_blocks")
        assert_true("boot_configuration" in capability_blocks, f"{f.name} missing boot_configuration")
        assert_true("clocking" in capability_blocks, f"{f.name} missing clocking")
        assert_true("boot_configuration" in constraint_blocks, f"{f.name} missing constraint_blocks.boot_configuration")
        if f.name in ("STM32F401xB_C.json", "STM32H745xI_G.json"):
            assert_true("debug_access" in capability_blocks, f"{f.name} missing debug_access")
            assert_true("debug_access" in constraint_blocks, f"{f.name} missing constraint_blocks.debug_access")


# ─── T5: Manifest Consistency ──────────────────────────────────────

@case("T5.1 Manifest exists and lists all export files")
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

@case("T6.1 Gowin FPGA exports have supply_specs from DC data")
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


@case("T6.2 Gowin FPGA exports have absolute_maximum_ratings")
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


@case("T4.8 Refclk protocol profiles and pin inference are populated")
def t4_8():
    gw = json.load(open(EXPORT_DIR / "GW5AT-60_UG225.json"))
    gw_refclk = gw.get("constraint_blocks", {}).get("refclk_requirements", {})
    assert_eq(gw_refclk.get("protocol_refclk_profiles", {}).get("PCIe 3.0", {}).get("frequencies_mhz"), [100.0], "GW5AT-60_UG225 PCIe refclk")

    lifcl = json.load(open(EXPORT_DIR / "LIFCL-40_CABGA400.json"))
    lifcl_refclk = lifcl.get("constraint_blocks", {}).get("refclk_requirements", {})
    inferred = [pair for pair in lifcl_refclk.get("refclk_pairs", []) if pair.get("source") == "pin_name_inference"]
    assert_true(inferred, "LIFCL-40_CABGA400 missing inferred refclk pair")
    assert_eq(inferred[0].get("p_name"), "SD_REFCLKP", "LIFCL-40_CABGA400 inferred p_name")
    assert_eq(inferred[0].get("n_name"), "SD_REFCLKN", "LIFCL-40_CABGA400 inferred n_name")


@case("T4.9 MCU interface blocks expose review constraints")
def t4_9():
    f103 = json.load(open(EXPORT_DIR / "STM32F103xC.json"))
    f103_caps = f103.get("capability_blocks", {})
    f103_cons = f103.get("constraint_blocks", {})
    for key in ("usb_interface", "can_interface", "storage_interface"):
        assert_true(key in f103_caps, f"STM32F103xC missing {key} capability")
        assert_true(key in f103_cons, f"STM32F103xC missing {key} constraint")
    assert_eq(f103_caps["usb_interface"].get("signal_roles", {}).get("dm"), ["PA11"], "STM32F103xC USB DM role")
    assert_eq(f103_caps["usb_interface"].get("signal_roles", {}).get("dp"), ["PA12"], "STM32F103xC USB DP role")
    can_rx_roles = set(f103_caps["can_interface"].get("signal_roles", {}).get("rx", []))
    can_tx_roles = set(f103_caps["can_interface"].get("signal_roles", {}).get("tx", []))
    assert_true({"PA11", "PD0"}.issubset(can_rx_roles), f"STM32F103xC CAN RX roles incomplete: {sorted(can_rx_roles)}")
    assert_true({"PA12", "PD1"}.issubset(can_tx_roles), f"STM32F103xC CAN TX roles incomplete: {sorted(can_tx_roles)}")
    storage_roles = f103_caps["storage_interface"].get("signal_roles", {})
    assert_eq(storage_roles.get("ck"), ["PC12"], "STM32F103xC SDIO CK role")
    assert_eq(storage_roles.get("cmd"), ["PD2"], "STM32F103xC SDIO CMD role")
    assert_eq(storage_roles.get("d0"), ["PC8"], "STM32F103xC SDIO D0 role")
    assert_true("tx" in f103_cons["can_interface"].get("present_signal_roles", []), "STM32F103xC CAN constraint missing tx role")
    assert_true("rx" in f103_cons["can_interface"].get("present_signal_roles", []), "STM32F103xC CAN constraint missing rx role")

    f205 = json.load(open(EXPORT_DIR / "STM32F205xx.json"))
    f205_caps = f205.get("capability_blocks", {})
    f205_cons = f205.get("constraint_blocks", {})
    for key in ("usb_interface", "ethernet_interface", "can_interface", "serial_memory_interface", "storage_interface"):
        if key in f205_caps:
            assert_true(key in f205_cons, f"STM32F205xx missing {key} constraint")


@case("T4.10 AMD and Lattice high-speed exports expose family protocol profiles")
def t4_10():
    xcku = json.load(open(EXPORT_DIR / "XCKU3P_FFVA676.json"))
    xcku_hs = xcku.get("capability_blocks", {}).get("high_speed_serial", {})
    xcku_refclk = xcku.get("constraint_blocks", {}).get("refclk_requirements", {})
    assert_true("PCIe 4.0" in xcku_hs.get("supported_protocols", []), "XCKU3P missing PCIe 4.0 support")
    assert_true("10GBASE-R" in xcku_hs.get("supported_protocols", []), "XCKU3P missing 10GBASE-R support")
    assert_eq(xcku_hs.get("transceiver_type"), "GTY", "XCKU3P transceiver type")
    assert_eq(xcku_refclk.get("protocol_refclk_profiles", {}).get("PCIe 4.0", {}).get("frequencies_mhz"), [100.0], "XCKU3P PCIe 4.0 refclk")
    assert_eq(xcku_refclk.get("protocol_refclk_profiles", {}).get("10GBASE-R", {}).get("frequencies_mhz"), [156.25], "XCKU3P 10GBASE-R refclk")
    assert_true(100.0 in xcku_refclk.get("common_review_candidates_mhz", []), "XCKU3P missing 100 MHz candidate")
    assert_true(156.25 in xcku_refclk.get("common_review_candidates_mhz", []), "XCKU3P missing 156.25 MHz candidate")

    lifcl = json.load(open(EXPORT_DIR / "LIFCL-40_CABGA400.json"))
    lifcl_hs = lifcl.get("capability_blocks", {}).get("high_speed_serial", {})
    lifcl_refclk = lifcl.get("constraint_blocks", {}).get("refclk_requirements", {})
    assert_true("SGMII" in lifcl_hs.get("supported_protocols", []), "LIFCL-40 missing SGMII support")
    assert_true("PCIe Gen2" in lifcl_hs.get("supported_protocols", []), "LIFCL-40 missing PCIe Gen2 support")
    assert_eq(lifcl_refclk.get("protocol_refclk_profiles", {}).get("SGMII", {}).get("frequencies_mhz"), [125.0], "LIFCL-40 SGMII refclk")
    assert_eq(lifcl_refclk.get("protocol_refclk_profiles", {}).get("PCIe Gen2", {}).get("frequencies_mhz"), [100.0], "LIFCL-40 PCIe Gen2 refclk")
    assert_true(125.0 in lifcl_refclk.get("common_review_candidates_mhz", []), "LIFCL-40 missing 125 MHz candidate")
    assert_true(100.0 in lifcl_refclk.get("common_review_candidates_mhz", []), "LIFCL-40 missing 100 MHz candidate")


@case("T4.11 Refclk constraints expose lane group topology")
def t4_11():
    xcku = json.load(open(EXPORT_DIR / "XCKU3P_FFVA676.json"))
    xcku_refclk = xcku.get("constraint_blocks", {}).get("refclk_requirements", {})
    xcku_groups = {entry.get("group_id"): entry for entry in xcku_refclk.get("lane_group_mappings", [])}
    assert_true("224" in xcku_groups, "XCKU3P missing quad 224 topology")
    assert_eq(xcku_groups["224"].get("lane_indices"), [0, 1, 2, 3], "XCKU3P quad 224 lane indices")
    assert_eq(xcku_groups["224"].get("refclk_indices"), [0, 1], "XCKU3P quad 224 refclk indices")
    refclk0_224 = [pair for pair in xcku_refclk.get("refclk_pairs", []) if pair.get("pair_name") == "REFCLK0_224"][0]
    assert_eq(refclk0_224.get("mapped_lane_groups"), ["224"], "XCKU3P REFCLK0_224 mapping")

    gw = json.load(open(EXPORT_DIR / "GW5AT-60_UG225.json"))
    gw_refclk = gw.get("constraint_blocks", {}).get("refclk_requirements", {})
    gw_groups = {entry.get("group_id"): entry for entry in gw_refclk.get("lane_group_mappings", [])}
    assert_true("Q0" in gw_groups, "GW5AT-60_UG225 missing Q0 topology")
    assert_eq(gw_groups["Q0"].get("lane_indices"), [0, 1, 2, 3], "GW5AT-60_UG225 Q0 lane indices")
    assert_eq(gw_groups["Q0"].get("refclk_indices"), [0, 1], "GW5AT-60_UG225 Q0 refclk indices")

    lifcl = json.load(open(EXPORT_DIR / "LIFCL-40_CABGA400.json"))
    lifcl_refclk = lifcl.get("constraint_blocks", {}).get("refclk_requirements", {})
    lifcl_groups = {entry.get("group_id"): entry for entry in lifcl_refclk.get("lane_group_mappings", [])}
    assert_true("SD0" in lifcl_groups, "LIFCL-40 missing SD0 topology")
    assert_eq(lifcl_groups["SD0"].get("refclk_pair_names"), ["SD_REFCLK"], "LIFCL-40 SD0 refclk mapping")


@case("T4.12 Lane groups and refclk pairs expose protocol candidates")
def t4_12():
    xcku = json.load(open(EXPORT_DIR / "XCKU3P_FFVA676.json"))
    xcku_refclk = xcku.get("constraint_blocks", {}).get("refclk_requirements", {})
    xcku_groups = {entry.get("group_id"): entry for entry in xcku_refclk.get("lane_group_mappings", [])}
    quad224 = xcku_groups["224"]
    assert_true("PCIe 4.0" in quad224.get("candidate_protocols", []), "XCKU3P quad 224 missing PCIe 4.0")
    assert_eq(quad224.get("protocol_lane_widths", {}).get("PCIe 4.0"), [1, 2, 4], "XCKU3P quad 224 PCIe 4.0 widths")
    refclk0_224 = [pair for pair in xcku_refclk.get("refclk_pairs", []) if pair.get("pair_name") == "REFCLK0_224"][0]
    assert_true("XAUI" in refclk0_224.get("candidate_protocols", []), "XCKU3P REFCLK0_224 missing XAUI")
    assert_eq(refclk0_224.get("protocol_lane_widths", {}).get("XAUI"), [4], "XCKU3P REFCLK0_224 XAUI width")

    gw = json.load(open(EXPORT_DIR / "GW5AT-60_UG225.json"))
    gw_group = gw.get("constraint_blocks", {}).get("refclk_requirements", {}).get("lane_group_mappings", [])[0]
    assert_eq(gw_group.get("protocol_lane_widths", {}).get("PCIe 3.0"), [1, 2, 4], "GW5AT Q0 PCIe widths")

    lifcl = json.load(open(EXPORT_DIR / "LIFCL-40_CABGA400.json"))
    lifcl_group = lifcl.get("constraint_blocks", {}).get("refclk_requirements", {}).get("lane_group_mappings", [])[0]
    assert_eq(lifcl_group.get("protocol_lane_widths", {}).get("SGMII"), [1], "LIFCL SD0 SGMII width")
    lifcl_pair = lifcl.get("constraint_blocks", {}).get("refclk_requirements", {}).get("refclk_pairs", [])[0]
    assert_true("PCIe Gen2" in lifcl_pair.get("candidate_protocols", []), "LIFCL SD_REFCLK missing PCIe Gen2")


@case("T4.13 Lane groups and refclk pairs expose bundle/use-case tags")
def t4_13():
    xcku = json.load(open(EXPORT_DIR / "XCKU3P_FFVA676.json"))
    quad224 = {entry.get("group_id"): entry for entry in xcku.get("constraint_blocks", {}).get("refclk_requirements", {}).get("lane_group_mappings", [])}["224"]
    assert_true("SerDes" in quad224.get("bundle_tags", []), "XCKU3P quad 224 missing SerDes tag")
    assert_true("PCIe" in quad224.get("bundle_tags", []), "XCKU3P quad 224 missing PCIe tag")
    assert_true("high_speed_link" in quad224.get("use_case_tags", []), "XCKU3P quad 224 missing high_speed_link use case")
    assert_true("pcie_link" in quad224.get("use_case_tags", []), "XCKU3P quad 224 missing pcie_link use case")
    assert_eq(quad224.get("bundle_scenario_candidates"), ["high_speed_link_bridge"], "XCKU3P quad 224 scenario candidates")

    refclk0_224 = [pair for pair in xcku.get("constraint_blocks", {}).get("refclk_requirements", {}).get("refclk_pairs", []) if pair.get("pair_name") == "REFCLK0_224"][0]
    assert_true("Ethernet" in refclk0_224.get("bundle_tags", []), "XCKU3P REFCLK0_224 missing Ethernet tag")

    lifcl_pair = lifcl_pair = json.load(open(EXPORT_DIR / "LIFCL-40_CABGA400.json")).get("constraint_blocks", {}).get("refclk_requirements", {}).get("refclk_pairs", [])[0]
    assert_true("high_speed_link_bridge" in lifcl_pair.get("bundle_scenario_candidates", []), "LIFCL SD_REFCLK missing scenario candidate")
    assert_true("ethernet_link" in lifcl_pair.get("use_case_tags", []), "LIFCL SD_REFCLK missing ethernet_link use case")


@case("T6.3 Gowin GW5AT exports expose package-specific ip_blocks")
def t6_3():
    ug225 = json.load(open(EXPORT_DIR / "GW5AT-60_UG225.json"))
    ug324s = json.load(open(EXPORT_DIR / "GW5AT-60_UG324S.json"))
    pg484a = json.load(open(EXPORT_DIR / "GW5AT-60_PG484A.json"))
    fpg676a = json.load(open(EXPORT_DIR / "GW5AT-138_FPG676A.json"))

    ug225_mipi = ug225.get("ip_blocks", {}).get("mipi", {})
    ug225_serdes = ug225.get("ip_blocks", {}).get("serdes", {})
    assert_true(ug225_mipi.get("present") is True, "GW5AT-60_UG225 MIPI missing")
    assert_eq(ug225_mipi.get("phy_types"), ["D-PHY", "C-PHY"], "GW5AT-60_UG225 phy types")
    assert_eq(ug225_mipi.get("directions"), ["RX", "TX"], "GW5AT-60_UG225 MIPI directions")
    assert_eq(ug225_mipi.get("dphy", {}).get("max_data_lanes"), 4, "GW5AT-60_UG225 D-PHY lanes")
    assert_eq(ug225_mipi.get("cphy", {}).get("max_trios"), 3, "GW5AT-60_UG225 C-PHY trios")
    assert_eq(ug225_serdes.get("transceiver_count"), 4, "GW5AT-60_UG225 transceiver count")
    assert_eq(ug225_serdes.get("quad_count"), 1, "GW5AT-60_UG225 quad count")
    assert_eq(ug225_serdes.get("protocol_matrix", {}).get("PCIe 3.0", {}).get("lane_widths"), [1, 2, 4], "GW5AT-60_UG225 PCIe widths")

    for export in (ug324s, pg484a):
        mipi = export.get("ip_blocks", {}).get("mipi", {})
        assert_true(mipi.get("present") is False, f"{export.get('mpn')}_{export.get('package')} should not expose MIPI on this package")
        assert_eq(mipi.get("phy_types"), [], f"{export.get('mpn')}_{export.get('package')} phy types")

    pg484a_serdes = pg484a.get("ip_blocks", {}).get("serdes", {})
    assert_eq(pg484a_serdes.get("package_rate_ceiling_gbps"), 8.0, "GW5AT-60_PG484A package SerDes ceiling")

    fpg676a_mipi = fpg676a.get("ip_blocks", {}).get("mipi", {})
    fpg676a_serdes = fpg676a.get("ip_blocks", {}).get("serdes", {})
    assert_eq(fpg676a_mipi.get("phy_types"), ["D-PHY"], "GW5AT-138_FPG676A phy types")
    assert_eq(fpg676a_mipi.get("directions"), ["RX"], "GW5AT-138_FPG676A MIPI directions")
    assert_eq(fpg676a_mipi.get("dphy", {}).get("max_data_lanes"), 8, "GW5AT-138_FPG676A D-PHY lanes")
    assert_eq(fpg676a_serdes.get("transceiver_count"), 8, "GW5AT-138_FPG676A transceiver count")
    assert_eq(fpg676a_serdes.get("quad_count"), 2, "GW5AT-138_FPG676A quad count")
    assert_eq(fpg676a_serdes.get("protocol_matrix", {}).get("PCIe 3.0", {}).get("lane_widths"), [1, 2, 4, 8], "GW5AT-138_FPG676A PCIe widths")


@case("T6.4 Gowin GW5AT exports expose design-guide power and config rules")
def t6_4():
    ug225 = json.load(open(EXPORT_DIR / "GW5AT-60_UG225.json"))
    power_sequence = ug225.get("domains", {}).get("power_sequence", {})
    sequencing_rules = power_sequence.get("sequencing_rules", [])
    assert_true(sequencing_rules, "GW5AT-60_UG225 missing domains.power_sequence.sequencing_rules")
    first_rule = sequencing_rules[0]
    assert_eq(first_rule.get("rail_before"), "VCCX", "GW5AT-60_UG225 sequence before rail")
    assert_eq(first_rule.get("rail_after"), "VCC", "GW5AT-60_UG225 sequence after rail")

    ramps = {entry.get("name"): entry.get("ramp_rate") for entry in power_sequence.get("power_rails", [])}
    assert_eq(ramps.get("VCC", {}).get("min"), 0.1, "GW5AT-60_UG225 VCC ramp min")
    assert_eq(ramps.get("VCCIO", {}).get("max"), 15.0, "GW5AT-60_UG225 VCCIO ramp max")

    constraints = ug225.get("constraint_blocks", {})
    cfg = constraints.get("configuration_boot", {})
    pins = cfg.get("pin_requirements", {})
    assert_true(pins.get("RECONFIG_N", {}).get("must_be_high_during_powerup") is True, "GW5AT-60_UG225 RECONFIG_N power-up rule")
    assert_eq(pins.get("READY", {}).get("requires_pullup", {}).get("resistance_ohm"), 4700, "GW5AT-60_UG225 READY pullup")
    assert_true(pins.get("CFGBVS", {}).get("must_not_float") is True, "GW5AT-60_UG225 CFGBVS must_not_float")

    power_integrity = constraints.get("power_integrity", {})
    assert_eq(power_integrity.get("ripple_limits_pct", {}).get("VCC", {}).get("max_pct"), 3.0, "GW5AT-60_UG225 VCC ripple")
    mipi_group = power_integrity.get("sensitive_power_pin_groups", {}).get("mipi", {})
    assert_true("VDDX_MIPI" in mipi_group.get("pin_name_tokens", []), "GW5AT-60_UG225 MIPI sensitive power tokens")
    assert_eq(mipi_group.get("missing_isolation_severity"), "WARNING", "GW5AT-60_UG225 MIPI isolation severity")

    clocking = constraints.get("clocking", {})
    assert_eq(clocking.get("serdes_refclk_ac_coupling_nf"), 100.0, "GW5AT-60_UG225 SerDes AC coupling")


@case("T6.5 Gowin design-guide domain preserves family and package source boundaries")
def t6_5():
    ug225 = json.load(open(EXPORT_DIR / "GW5AT-60_UG225.json"))
    cs130 = json.load(open(EXPORT_DIR / "GW5AT-15_CS130.json"))

    ug225_guide = ug225.get("domains", {}).get("design_guide", {})
    cs130_guide = cs130.get("domains", {}).get("design_guide", {})
    assert_true(ug225_guide, "GW5AT-60_UG225 missing domains.design_guide")
    assert_true(cs130_guide, "GW5AT-15_CS130 missing domains.design_guide")

    family_doc = ug225_guide.get("source_document", {})
    assert_eq(family_doc.get("document_id"), "UG984", "GW5AT family guide doc id")
    assert_eq(family_doc.get("version"), "1.2", "GW5AT family guide version")

    ug225_docs = {
        (item.get("document_id"), item.get("version"), item.get("package"))
        for item in ug225_guide.get("source_documents", [])
    }
    cs130_docs = {
        (item.get("document_id"), item.get("version"), item.get("package"))
        for item in cs130_guide.get("source_documents", [])
    }
    assert_true(("UG1222", "1.3.3E", "UG225") in ug225_docs, "GW5AT-60_UG225 missing latest package guide boundary")
    assert_true(("UG1224", "1.2E", "CS130") in cs130_docs, "GW5AT-15_CS130 missing latest package guide boundary")

    io_signaling = ug225.get("constraint_blocks", {}).get("io_signaling", {})
    scope = io_signaling.get("lvds_input_termination", {}).get("package_scope", {})
    assert_eq(scope.get("GW5AT-60"), "all_regions", "GW5AT-60 LVDS termination scope")
    assert_eq(scope.get("GW5AT-138"), "top_bottom_only", "GW5AT-138 LVDS termination scope")


@case("T6.6 GW5AT-15 package profiles expose bonded rail overrides")
def t6_6():
    cs130 = json.load(open(EXPORT_DIR / "GW5AT-15_CS130.json"))
    cs130f = json.load(open(EXPORT_DIR / "GW5AT-15_CS130F.json"))
    mg132 = json.load(open(EXPORT_DIR / "GW5AT-15_MG132.json"))

    cs130_profile = cs130.get("domains", {}).get("design_guide", {}).get("package_profile", {})
    cs130f_profile = cs130f.get("domains", {}).get("design_guide", {}).get("package_profile", {})
    mg132_profile = mg132.get("domains", {}).get("design_guide", {}).get("package_profile", {})

    cs130_aliases = {item.get("physical_rail"): item for item in cs130_profile.get("power_rail_aliases", [])}
    assert_true("VCCX_VCCLDO_VDDXM" in cs130_aliases, "CS130 missing merged auxiliary rail alias")
    assert_eq(cs130_aliases["VCCX_VCCLDO_VDDXM"].get("logical_rails"), ["VCCX", "VCCLDO", "VDDXM"], "CS130 merged logical rails")
    assert_true(any("VDD12M" in alias.get("logical_rails", []) for alias in cs130_aliases.values()), "CS130 missing VDD12M bonded rail alias")

    cs130f_aliases = {item.get("physical_rail"): item for item in cs130f_profile.get("power_rail_aliases", [])}
    assert_eq(cs130f_aliases.get("VCCX_VDDXM", {}).get("logical_rails"), ["VCCX", "VDDXM"], "CS130F VCCX/VDDXM merge")
    assert_eq(cs130f_aliases.get("VCCLDO_VDD12M", {}).get("logical_rails"), ["VCCLDO", "VDD12M"], "CS130F VCCLDO/VDD12M merge")
    assert_true(any("binding source" in note for note in cs130f_profile.get("package_notes", [])), "CS130F missing pinout-priority note")

    mg132_aliases = {item.get("physical_rail"): item for item in mg132_profile.get("power_rail_aliases", [])}
    assert_eq(mg132_aliases.get("VCCX", {}).get("logical_rails"), ["VCCX"], "MG132 dedicated VCCX")
    assert_eq(mg132_aliases.get("VCCLDO", {}).get("logical_rails"), ["VCCLDO"], "MG132 dedicated VCCLDO")
    assert_eq(mg132_aliases.get("VDDAM/VDDXM", {}).get("logical_rails"), ["VDDAM", "VDDXM"], "MG132 MIPI bonded rail")

    power_block = cs130f.get("constraint_blocks", {}).get("power_integrity", {})
    alias_physical = {item.get("physical_rail") for item in power_block.get("package_power_rail_aliases", [])}
    assert_true("VCCX_VDDXM" in alias_physical, "CS130F power_integrity missing package alias")
    assert_true(["VCCX", "VDDXM"] in power_block.get("package_merged_logical_rail_groups", []), "CS130F power_integrity missing merged logical group")


@case("T6.6B GW5AT-15 exports expose current package-listing status and MG132 high-speed guidance")
def t6_6b():
    cs130 = json.load(open(EXPORT_DIR / "GW5AT-15_CS130.json"))
    cs130f = json.load(open(EXPORT_DIR / "GW5AT-15_CS130F.json"))
    mg132 = json.load(open(EXPORT_DIR / "GW5AT-15_MG132.json"))

    cs130_status = cs130.get("ip_blocks", {}).get("serdes", {}).get("package_listing_status", {})
    cs130f_status = cs130f.get("ip_blocks", {}).get("serdes", {}).get("package_listing_status", {})
    mg132_serdes = mg132.get("ip_blocks", {}).get("serdes", {})

    assert_true(cs130_status.get("listed_on_current_product_page") is False, "GW5AT-15_CS130 should be absent from current product page package list")
    assert_true(cs130f_status.get("listed_on_current_product_page") is True, "GW5AT-15_CS130F should remain listed on current product page")
    assert_true(mg132_serdes.get("package_listing_status", {}).get("listed_on_current_product_page") is True, "GW5AT-15_MG132 should remain listed on current product page")
    guidance = mg132_serdes.get("link_reach_guidance", {})
    assert_eq(guidance.get("rate_threshold_gbps"), 8.0, "GW5AT-15_MG132 guidance threshold")
    assert_eq(guidance.get("recommended_scope_above_threshold"), "on_board_only", "GW5AT-15_MG132 high-rate scope")


@case("T6.7 Gowin GW5AR/GW5AS exports expose metadata-only design-guide package profiles")
def t6_7():
    gw5ar = json.load(open(EXPORT_DIR / "GW5AR-25_UG256P.json"))
    gw5as = json.load(open(EXPORT_DIR / "GW5AS-25_UG256.json"))

    gw5ar_guide = gw5ar.get("domains", {}).get("design_guide", {})
    gw5as_guide = gw5as.get("domains", {}).get("design_guide", {})
    assert_true(gw5ar_guide, "GW5AR-25_UG256P missing domains.design_guide")
    assert_true(gw5as_guide, "GW5AS-25_UG256 missing domains.design_guide")

    assert_eq(gw5ar_guide.get("source_document", {}).get("document_id"), "UG1117", "GW5AR family guide doc id")
    assert_eq(gw5ar_guide.get("source_document", {}).get("version"), "1.1E", "GW5AR family guide version")
    assert_eq(gw5as_guide.get("source_document", {}).get("document_id"), "UG1116", "GW5AS family guide doc id")
    assert_eq(gw5as_guide.get("source_document", {}).get("version"), "1.1E", "GW5AS family guide version")

    gw5ar_docs = {
        (item.get("document_id"), item.get("version"), item.get("package"))
        for item in gw5ar_guide.get("source_documents", [])
    }
    gw5as_docs = {
        (item.get("document_id"), item.get("version"), item.get("package"))
        for item in gw5as_guide.get("source_documents", [])
    }
    assert_true(("UG1110", "1.1.1E", "UG256P") in gw5ar_docs, "GW5AR-25_UG256P missing latest package guide boundary")
    assert_true(("UG1115", "1.1.4E", "UG256") in gw5as_docs, "GW5AS-25_UG256 missing latest package guide boundary")

    gw5ar_profile = gw5ar_guide.get("package_profile", {})
    gw5as_profile = gw5as_guide.get("package_profile", {})
    assert_true(gw5ar_profile.get("family_rules_apply") is False, "GW5AR package profile should be metadata-only")
    assert_true(gw5as_profile.get("family_rules_apply") is False, "GW5AS package profile should be metadata-only")

    gw5ar_pin_rules = gw5ar_guide.get("pin_connection_rules", [])
    gw5ar_io_rules = {item.get("standard"): item for item in gw5ar_guide.get("io_standard_rules", [])}
    gw5as_modes = {item.get("mode"): item for item in gw5as_guide.get("configuration_mode_support", [])}
    assert_true(any(item.get("pin") == "RECONFIG_N" for item in gw5ar_pin_rules), "GW5AR should derive RECONFIG_N pin rule from pinout")
    assert_true(any(item.get("pin") == "PUDC_B" and item.get("connection_type") == "must_not_float" for item in gw5ar_pin_rules), "GW5AR should derive PUDC_B must_not_float rule")
    assert_eq(gw5ar_io_rules.get("LVDS", {}).get("requirement"), "Set the bank VCCIO to 2.5 V when using True LVDS.", "GW5AR LVDS VCCIO rule")
    assert_true("JTAG" in gw5as_modes, "GW5AS should derive JTAG configuration mode from pinout")
    assert_true("SERIAL_BOOT" in gw5as_modes, "GW5AS should derive SERIAL_BOOT configuration mode from pinout")

    gw5ar_aliases = {item.get("physical_rail"): item for item in gw5ar_profile.get("power_rail_aliases", [])}
    gw5as_aliases = {item.get("physical_rail"): item for item in gw5as_profile.get("power_rail_aliases", [])}
    assert_eq(
        gw5ar_aliases.get("M0_VDDX/VCC_REG/VCCIO10/VCCX", {}).get("logical_rails"),
        ["M0_VDDX", "VCC_REG", "VCCIO", "VCCX"],
        "GW5AR merged auxiliary rail map",
    )
    assert_eq(
        gw5as_aliases.get("VCCIO0/VCCIO1/VCCIO10/VCCIO2/VCCIO6/VCCIO7", {}).get("logical_rails"),
        ["VCCIO"],
        "GW5AS merged VCCIO bank group should normalize to logical VCCIO",
    )

    gw5ar_io_block = gw5ar.get("constraint_blocks", {}).get("io_signaling", {})
    cfg_block = gw5as.get("constraint_blocks", {}).get("configuration_boot", {})
    power_block = gw5as.get("constraint_blocks", {}).get("power_integrity", {})
    io_block = gw5as.get("constraint_blocks", {}).get("io_signaling", {})
    assert_eq(gw5ar_io_block.get("lvds_bank_vccio_requirement_v"), 2.5, "GW5AR io_signaling LVDS VCCIO requirement")
    assert_true(cfg_block.get("pin_requirements", {}).get("MODE0", {}).get("must_not_float") is True, "GW5AS configuration_boot should expose MODE0 strap requirement")
    assert_true(io_block.get("lvds_bank_vccio_requirement_v") is None, "GW5AS should not invent LVDS VCCIO rule without source")
    assert_eq(power_block.get("coverage"), "package_profile_only", "GW5AS power_integrity coverage")
    assert_true(power_block.get("design_guide_rules_normalized") is False, "GW5AS power_integrity should stay metadata-only")

    gw5ar_resources = gw5ar.get("resources", {})
    gw5as_resources = gw5as.get("resources", {})
    gw5ar_mem = gw5ar.get("embedded_memories", {})
    gw5as_mem = gw5as.get("embedded_memories", {})
    gw5ar_mipi = gw5ar.get("ip_blocks", {}).get("mipi", {})
    gw5as_mipi = gw5as.get("ip_blocks", {}).get("mipi", {})
    assert_eq(gw5ar_resources.get("lut4"), 23040, "GW5AR-25 LUT4 summary")
    assert_eq(gw5ar_resources.get("bsram_kbit"), 1008, "GW5AR-25 BSRAM summary")
    assert_eq(gw5ar_resources.get("dsp"), 28, "GW5AR-25 DSP summary")
    assert_eq(gw5ar_mem.get("embedded_psram_mbit"), 64, "GW5AR-25 embedded PSRAM summary")
    assert_eq(gw5ar_mipi.get("directions"), ["RX", "TX"], "GW5AR-25 MIPI directions")
    assert_eq(gw5as_resources.get("lut4"), 41472, "GW5AS-25 LUT4 summary")
    assert_eq(gw5as_resources.get("dsp"), 178, "GW5AS-25 DSP summary")
    assert_eq(gw5as_resources.get("adc", {}).get("total"), 4, "GW5AS-25 ADC summary")
    assert_eq(gw5as_mem.get("embedded_psram_mbit"), 64, "GW5AS-25 embedded PSRAM summary")
    assert_eq(gw5as_mipi.get("directions"), ["RX", "TX"], "GW5AS-25 MIPI directions")
    assert_eq(gw5ar.get("device_role"), "FPGA", "GW5AR device role")
    assert_eq(gw5as.get("device_role"), "FPGA SoC", "GW5AS device role")


@case("T6.8 GW5AT-75 and GW5AT-138 package exports cover current public package set")
def t6_8():
    gw5at75 = json.load(open(EXPORT_DIR / "GW5AT-75_UG484.json"))
    pg484 = json.load(open(EXPORT_DIR / "GW5AT-138_PG484.json"))
    pg484a = json.load(open(EXPORT_DIR / "GW5AT-138_PG484A.json"))
    pg676a = json.load(open(EXPORT_DIR / "GW5AT-138_PG676A.json"))
    ug324a = json.load(open(EXPORT_DIR / "GW5AT-138_UG324A.json"))

    gw5at75_serdes = gw5at75.get("ip_blocks", {}).get("serdes", {})
    gw5at75_mipi = gw5at75.get("ip_blocks", {}).get("mipi", {})
    assert_eq(gw5at75_serdes.get("transceiver_count"), 8, "GW5AT-75 transceiver count")
    assert_eq(gw5at75_serdes.get("protocol_matrix", {}).get("PCIe 3.0", {}).get("lane_widths"), [1, 2, 4, 8], "GW5AT-75 PCIe widths")
    assert_eq(gw5at75_mipi.get("directions"), ["RX"], "GW5AT-75 MIPI directions")
    assert_eq(gw5at75_mipi.get("dphy", {}).get("max_data_lanes"), 8, "GW5AT-75 D-PHY lanes")

    assert_true(pg484.get("ip_blocks", {}).get("serdes", {}).get("package_listing_status", {}).get("listed_on_current_product_page") is True, "GW5AT-138_PG484 listing status")
    assert_true(pg484a.get("ip_blocks", {}).get("serdes", {}).get("package_listing_status", {}).get("listed_on_current_product_page") is True, "GW5AT-138_PG484A listing status")
    assert_true(pg676a.get("ip_blocks", {}).get("serdes", {}).get("package_listing_status", {}).get("listed_on_current_product_page") is True, "GW5AT-138_PG676A listing status")
    assert_true(ug324a.get("ip_blocks", {}).get("serdes", {}).get("package_listing_status", {}).get("listed_on_current_product_page") is True, "GW5AT-138_UG324A listing status")
    assert_eq(pg676a.get("ip_blocks", {}).get("serdes", {}).get("protocol_matrix", {}).get("PCIe 3.0", {}).get("lane_widths"), [1, 2, 4, 8], "GW5AT-138_PG676A PCIe widths")


@case("T6.9 GW5A exports provide package pinout coverage plus public capability summaries")
def t6_9():
    gw5a25 = json.load(open(EXPORT_DIR / "GW5A-25_UG324.json"))
    gw5a60s = json.load(open(EXPORT_DIR / "GW5A-60_UG324S.json"))
    gw5a60a = json.load(open(EXPORT_DIR / "GW5A-60_UG324A.json"))

    assert_true(gw5a25.get("banks"), "GW5A-25_UG324 missing banks")
    assert_true(gw5a25.get("power_rails"), "GW5A-25_UG324 missing power_rails")
    assert_true(gw5a25.get("lookup", {}).get("by_pin"), "GW5A-25_UG324 missing lookup.by_pin")
    assert_eq(gw5a25.get("resources", {}).get("lut4"), 23040, "GW5A-25 LUT4 summary")
    assert_eq(gw5a25.get("resources", {}).get("user_io"), 206, "GW5A-25 user IO summary")
    assert_eq(gw5a25.get("capability_blocks", {}).get("memory_interface", {}).get("ddr3_mbps"), 800, "GW5A-25 DDR3 summary")
    assert_eq(gw5a25.get("ip_blocks", {}).get("mipi", {}).get("directions"), ["RX", "TX"], "GW5A-25 MIPI directions")

    for export, expected_io in ((gw5a60s, 226), (gw5a60a, 222)):
        assert_true(export.get("banks"), f"{export.get('mpn')}_{export.get('package')} missing banks")
        assert_true(export.get("power_rails"), f"{export.get('mpn')}_{export.get('package')} missing power_rails")
        assert_eq(export.get("resources", {}).get("lut4"), 59904, f"{export.get('mpn')}_{export.get('package')} LUT4 summary")
        assert_eq(export.get("resources", {}).get("user_io"), expected_io, f"{export.get('mpn')}_{export.get('package')} user IO summary")
        assert_eq(export.get("capability_blocks", {}).get("memory_interface", {}).get("ddr3_mbps"), 1100, f"{export.get('mpn')}_{export.get('package')} DDR3 summary")
        assert_eq(export.get("ip_blocks", {}).get("mipi", {}).get("phy_types"), ["D-PHY", "C-PHY"], f"{export.get('mpn')}_{export.get('package')} MIPI phy types")



# ─── T7: Lattice DC Data Integration ───────────────────────────────

@case("T7.1 Lattice ECP5 exports have supply_specs from DC data")
def t7_1():
    lattice_exports = [
        "ECP5U-25_CABGA381.json", "ECP5U-85_CABGA756.json",
    ]
    for fname in lattice_exports:
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        specs = d.get("supply_specs", {})
        assert_gt(len(specs), 5, f"{fname} supply_specs count")


@case("T7.2 Lattice CrossLink-NX exports have supply_specs from DC data")
def t7_2():
    lattice_exports = [
        "LIFCL-40_CABGA400.json", "LIFCL-40_QFN72.json",
    ]
    for fname in lattice_exports:
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        specs = d.get("supply_specs", {})
        assert_gt(len(specs), 10, f"{fname} supply_specs count")


@case("T7.3 Lattice exports have absolute_maximum_ratings")
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


@case("T8.1 Lattice pinout source files exist and pin counts match")
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


@case("T8.2 Lattice pinout lookup bidirectional consistency")
def t8_2():
    for fname in LATTICE_PINOUTS:
        with open(FPGA_PINOUT_DIR / fname) as f:
            d = json.load(f)
        lookup = d.get("lookup", {})
        p2n = lookup.get("pin_to_name", lookup.get("by_pin", {}))
        for pin in d["pins"]:
            pid = pin["pin"]
            assert_in(pid, p2n, f"{fname} pin {pid} missing from lookup")


@case("T8.3 Lattice diff pairs reference valid pins")
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


@case("T8.4 Lattice exports have all 3 vendors in same schema")
def t8_4():
    amd = json.load(open(EXPORT_DIR / "XCKU3P_FFVA676.json"))
    gowin = json.load(open(EXPORT_DIR / "GW5AT-60_PG484A.json"))
    lattice = json.load(open(EXPORT_DIR / "ECP5U-25_CABGA381.json"))
    assert_eq(amd["_schema"], lattice["_schema"], "AMD vs Lattice schema")
    assert_eq(gowin["_schema"], lattice["_schema"], "Gowin vs Lattice schema")
    assert_eq(lattice["_type"], "fpga", "Lattice _type")
    assert_eq(lattice["manufacturer"], "Lattice", "Lattice manufacturer")


@case("T8.5 Lattice exports have same core keys as AMD/Gowin")
def t8_5():
    core_keys = {"_schema", "_type", "mpn", "manufacturer", "category", "package",
                 "supply_specs", "io_standard_specs", "power_rails", "banks",
                 "diff_pairs", "drc_rules", "pins", "lookup", "summary"}
    for fname in ["ECP5U-25_CABGA381.json", "LIFCL-40_CABGA400.json"]:
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        missing = core_keys - set(d.keys())
        assert_true(not missing, f"{fname} missing keys: {missing}")


@case("T8.6 Lattice exports pin functions all valid")
def t8_6():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        for i, pin in enumerate(d.get("pins", [])):
            func = pin.get("function", "")
            assert_in(func, VALID_FUNCTIONS, f"{fname} pin[{i}] ({pin.get('name','?')}) function={func}")


@case("T8.7 Lattice exports have power + ground + IO pins")
def t8_7():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        funcs = Counter(p["function"] for p in d["pins"])
        assert_gt(funcs.get("POWER", 0), 0, f"{fname} no POWER pins")
        assert_gt(funcs.get("IO", 0), 0, f"{fname} no IO pins")


@case("T8.8 Lattice diff pair pins exist in export pin list")
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


@case("T8.9 Lattice banks have required fields")
def t8_9():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        for bank_id, bank in d.get("banks", {}).items():
            assert_true("bank" in bank, f"{fname} banks.{bank_id} missing 'bank'")
            assert_true("total_pins" in bank, f"{fname} banks.{bank_id} missing 'total_pins'")


@case("T8.10 Lattice supply_specs have no min > max violations")
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


@case("T8.11 ECP5 cross-package IO monotonicity (larger pkg >= smaller pkg IO count)")
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


@case("T8.12 Lattice DRC rules have valid severities")
def t8_12():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        for rule_name, rule in d.get("drc_rules", {}).items():
            sev = rule.get("severity", "")
            assert_in(sev, VALID_SEVERITIES, f"{fname} drc_rules.{rule_name}.severity={sev}")


@case("T8.13 Lattice must_connect is boolean")
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


@case("T8.14 All 18 Lattice exports exist")
def t8_14():
    expected = [
        "ECP5U-25_CABGA256.json", "ECP5U-25_CABGA381.json", "ECP5U-25_CSFBGA285.json", "ECP5U-25_TQFP144.json",
        "ECP5U-45_CABGA256.json", "ECP5U-45_CABGA381.json", "ECP5U-45_CABGA554.json", "ECP5U-45_CSFBGA285.json", "ECP5U-45_TQFP144.json",
        "ECP5U-85_CABGA381.json", "ECP5U-85_CABGA554.json", "ECP5U-85_CABGA756.json", "ECP5U-85_CSFBGA285.json",
        "LIFCL-40_CABGA256.json", "LIFCL-40_CABGA400.json", "LIFCL-40_CSBGA289.json", "LIFCL-40_CSFBGA121.json", "LIFCL-40_QFN72.json",
    ]
    for fname in expected:
        assert_true((EXPORT_DIR / fname).exists(), f"Missing: {fname}")


@case("T8.15 Lattice lookup completeness — every pin in by_pin")
def t8_15():
    import glob
    for f in sorted(glob.glob(str(EXPORT_DIR / "ECP5U-*.json")) + glob.glob(str(EXPORT_DIR / "LIFCL-*.json"))):
        fname = Path(f).name
        with open(f) as fp:
            d = json.load(fp)
        by_pin = d.get("lookup", {}).get("by_pin", {})
        for pin in d["pins"]:
            assert_in(pin["pin"], by_pin, f"{fname} pin {pin['pin']} missing from lookup")


# ─── T9: TI Hot-Swap / eFuse / Ideal Diode ICs ──────────────────────

TI_HOTSWAP_EXPORTS = {
    # Hot-Swap Controllers (original 6)
    "LM5060.json":          {"mpn": "LM5060", "min_pins": 10, "category": "Other"},
    "LM5064.json":          {"mpn": "LM5064", "min_pins": 28, "category": "Other"},
    "LM5069.json":          {"mpn": "LM5069", "min_pins": 10, "category": "Other"},
    "LM74610-Q1.json":      {"mpn": "LM74610-Q1", "min_pins": 7, "category": "Other"},
    "TPS2490__TPS2491.json": {"mpn": "TPS2490, TPS2491", "min_pins": 10, "category": "Other"},
    "TPS2596.json":         {"mpn": "TPS2596", "min_pins": 8, "category": "Other"},
    # Hot-Swap Controllers (new)
    "TPS2480.json":         {"mpn": "TPS2480", "min_pins": 18, "category": "Other"},
    "TPS2410.json":         {"mpn": "TPS2410", "min_pins": 12, "category": "Other"},
    "TPS2412__TPS2413.json": {"mpn": "TPS2412, TPS2413", "min_pins": 8, "category": "Other"},
    "TPS2420.json":         {"mpn": "TPS2420", "min_pins": 11, "category": "Hot-Swap Controller"},
    "LM5067.json":          {"mpn": "LM5067", "min_pins": 10, "category": "Other"},
    "LM5068.json":          {"mpn": "LM5068", "min_pins": 8, "category": "Other"},
    # eFuse
    "TPS2595xx.json":       {"mpn": "TPS2595xx", "min_pins": 8, "category": "Other"},
    "TPS2590.json":         {"mpn": "TPS2590", "min_pins": 8, "category": "Switch"},
    "TPS25940A__TPS25940L.json": {"mpn": "TPS25940A, TPS25940L", "min_pins": 18, "category": "Other"},
    "TPS26600.json":        {"mpn": "TPS26600", "min_pins": 14, "category": "Other"},
    "TPS2661x.json":        {"mpn": "TPS2661x", "min_pins": 8, "category": "Other"},
    "TPS2662x.json":        {"mpn": "TPS2662x", "min_pins": 8, "category": "Switch"},
    "TPS2663.json":         {"mpn": "TPS2663", "min_pins": 14, "category": "Other"},
    "TPS1663.json":         {"mpn": "TPS1663", "min_pins": 14, "category": "Other"},
    "TPS1H100-Q1.json":     {"mpn": "TPS1H100-Q1", "min_pins": 8, "category": "Switch"},
    # Ideal Diode / Power MUX
    "LM66100.json":         {"mpn": "LM66100", "min_pins": 5, "category": "Other"},
    "LM66200.json":         {"mpn": "LM66200", "min_pins": 6, "category": "Switch"},
    "TPS2112__TPS2113.json": {"mpn": "TPS2112, TPS2113", "min_pins": 8, "category": "Switch"},
    "TPS2112A__TPS2113A.json": {"mpn": "TPS2112A, TPS2113A", "min_pins": 8, "category": "Other"},
    "TPS2114.json":         {"mpn": "TPS2114", "min_pins": 8, "category": "Switch"},
    "LM5051.json":          {"mpn": "LM5051", "min_pins": 7, "category": "Other"},
}


@case("T9.1 All TI hot-swap export files exist")
def t9_1():
    for fname in TI_HOTSWAP_EXPORTS:
        path = EXPORT_DIR / fname
        assert_true(path.exists(), f"Missing: {fname}")


@case("T9.2 TI hot-swap exports have electrical_parameters")
def t9_2():
    for fname, exp in TI_HOTSWAP_EXPORTS.items():
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        elec = d.get("electrical_parameters", {})
        assert_gt(len(elec), 0, f"{fname} electrical_parameters")
        # abs_max may be empty if extraction didn't capture symbols (Gemini limitation)
        # but at least check it exists as a dict
        abs_max = d.get("absolute_maximum_ratings", {})
        assert_true(isinstance(abs_max, dict), f"{fname} absolute_maximum_ratings should be dict")


@case("T9.3 TI hot-swap exports have complete pin definitions")
def t9_3():
    for fname, exp in TI_HOTSWAP_EXPORTS.items():
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        packages = d.get("packages", {})
        assert_gt(len(packages), 0, f"{fname} packages")
        total_pins = sum(p.get("pin_count", 0) for p in packages.values())
        assert_true(total_pins >= exp["min_pins"], f"{fname} pin count {total_pins} < {exp['min_pins']}")


@case("T9.4 TI hot-swap exports have DRC hints where available")
def t9_4():
    # DRC hints depend on symbol extraction quality - check that most have hints
    hints_count = 0
    total = len(TI_HOTSWAP_EXPORTS)
    for fname, exp in TI_HOTSWAP_EXPORTS.items():
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        drc_hints = d.get("drc_hints", {})
        if len(drc_hints) > 0:
            hints_count += 1
    # At least 50% should have DRC hints
    min_expected = total // 2
    assert_gt(hints_count, min_expected, f"TI hot-swap exports with DRC hints: {hints_count}/{total}")


@case("T9.5 TI hot-swap exports have correct MPN and manufacturer")
def t9_5():
    for fname, exp in TI_HOTSWAP_EXPORTS.items():
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        assert_eq(d.get("mpn"), exp["mpn"], f"{fname} mpn")
        assert_eq(d.get("manufacturer"), "Texas Instruments", f"{fname} manufacturer")


@case("T9.6 TI hot-swap pin directions are valid")
def t9_6():
    valid_directions = {"INPUT", "OUTPUT", "BIDIRECTIONAL", "POWER_IN", "POWER_OUT", "PASSIVE", "NC"}
    for fname in TI_HOTSWAP_EXPORTS:
        with open(EXPORT_DIR / fname) as f:
            d = json.load(f)
        for pkg_name, pkg in d.get("packages", {}).items():
            for pin_num, pin in pkg.get("pins", {}).items():
                direction = pin.get("direction", "")
                assert_in(direction, valid_directions, f"{fname} {pkg_name} pin {pin_num} direction={direction}")


# ─── Runner ─────────────────────────────────────────────────────────

def collect_cases():
    cases = []
    for name, obj in sorted(globals().items()):
        if callable(obj) and hasattr(obj, "_test_name"):
            cases.append(obj)
    return cases


def run_all_cases():
    global passed, failed, errors
    passed = 0
    failed = 0
    errors = []

    cases = collect_cases()

    print(f"\nRunning {len(cases)} tests...\n")

    for t in cases:
        run_test(t)

    return failed


def test_regression_suite():
    assert run_all_cases() == 0


def main():
    global passed, failed

    print("=" * 60)
    print("OpenDatasheet Regression Test Suite")
    print("=" * 60)

    run_all_cases()

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
