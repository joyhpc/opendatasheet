import copy
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
PINOUT_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "pinout"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from export_for_sch_review import export_fpga


def _load_pinout(name: str) -> dict:
    return json.loads((PINOUT_DIR / name).read_text())


def test_export_fpga_prefers_normalized_parse_traceability_lookup_and_diff_pairs():
    pinout = copy.deepcopy(_load_pinout("intel_agilex5_a5ec013b_b23a.json"))

    package_traceability = pinout["source_traceability"]["package_pinout"]
    package_traceability["source_file"] = "normalized.xlsx"
    package_traceability["source_document_id"] = "normalized-doc"
    pinout["source_file"] = "legacy.xlsx"
    pinout["source_document_id"] = "legacy-doc"

    sample_pin, sample_name = next(iter(pinout["lookup"]["pin_to_name"].items()))
    pinout["lookup"]["by_pin"] = {sample_pin: "WRONG_NAME"}
    pinout["lookup"]["by_name"] = {"WRONG_NAME": sample_pin}

    first_pair = pinout["diff_pairs"][0]
    first_pair["true_pin"] = "WRONG_P"
    first_pair["comp_pin"] = "WRONG_N"
    first_pair["true_name"] = "WRONG_P_NAME"
    first_pair["comp_name"] = "WRONG_N_NAME"

    exported = export_fpga({"extraction": {"component": {}}}, pinout)

    assert exported["source_traceability"]["package_pinout"]["source_file"] == "normalized.xlsx"
    assert exported["source_traceability"]["package_pinout"]["source_document_id"] == "normalized-doc"
    assert exported["lookup"]["by_pin"][sample_pin] == sample_name
    assert exported["lookup"]["by_name"][sample_name] == sample_pin
    assert exported["diff_pairs"][0]["p_pin"] == first_pair["p_pin"]
    assert exported["diff_pairs"][0]["n_pin"] == first_pair["n_pin"]
    assert exported["diff_pairs"][0]["p_name"] == first_pair["p_name"]
    assert exported["diff_pairs"][0]["n_name"] == first_pair["n_name"]


def test_export_fpga_consumes_unified_parse_fields_across_vendors():
    for name in (
        "xcku3pffva676pkg.json",
        "gowin_gw5a-25_lq100.json",
        "intel_agilex5_a5ec013b_b23a.json",
    ):
        pinout = _load_pinout(name)
        exported = export_fpga({"extraction": {"component": {}}}, pinout)

        sample_pin, sample_name = next(iter(pinout["lookup"]["pin_to_name"].items()))
        assert exported["manufacturer"] == pinout["_vendor"]
        assert exported["device_identity"]["vendor"] == pinout["_vendor"]
        assert exported["device_identity"]["family"] == pinout["_family"]
        assert exported["device_identity"]["series"] == pinout["_series"]
        assert exported["device_identity"]["base_device"] == pinout["_base_device"]
        assert exported["source_traceability"]["package_pinout"]["source_file"] == pinout["source_traceability"]["package_pinout"]["source_file"]
        assert exported["lookup"]["by_pin"][sample_pin] == sample_name
        assert exported["lookup"]["by_name"][sample_name] == sample_pin

