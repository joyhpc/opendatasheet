import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
PINOUT_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "pinout"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from normalize_fpga_parse import normalize_fpga_parse_result


def test_normalize_fpga_parse_result_converges_gowin_pdf_like_shape():
    data = {
        "_schema_version": "2.0",
        "_purpose": "FPGA pin definition for LLM-driven schematic DRC",
        "device": "GW5AT-15",
        "package": "CS130",
        "source_file": "UG1224-1.2_GW5AT-15器件Pinout手册.pdf",
        "pins": [
            {"pin": "A1", "name": "IOB1A", "function": "IO", "bank": "1"},
            {"pin": "A2", "name": "IOB1B", "function": "IO", "bank": "1"},
        ],
        "banks": {"1": {"pins": ["A1", "A2"], "io_count": 2}},
        "diff_pairs": [{"type": "IO", "true_name": "IOB1A", "comp_name": "IOB1B", "true_pin": "A1", "comp_pin": "A2"}],
        "lookup": {"by_pin": {"A1": "IOB1A"}, "by_name": {"IOB1A": "A1"}},
    }

    normalized = normalize_fpga_parse_result(data)

    assert normalized["_vendor"] == "Gowin"
    assert normalized["_family"] == "Arora V"
    assert normalized["_series"] == "Arora VT"
    assert normalized["_base_device"] == "GW5AT-15"
    assert normalized["lookup"]["pin_to_name"]["A1"] == "IOB1A"
    assert normalized["lookup"]["name_to_pin"]["IOB1A"] == "A1"
    assert normalized["banks"]["1"]["bank"] == "1"
    assert normalized["banks"]["1"]["total_pins"] == 2
    assert normalized["banks"]["1"]["io_pins"] == 2
    assert normalized["banks"]["1"]["attrs"]["pins"] == ["A1", "A2"]
    assert normalized["diff_pairs"][0]["p_pin"] == "A1"
    assert normalized["diff_pairs"][0]["n_pin"] == "A2"
    assert normalized["diff_pairs"][0]["p_name"] == "IOB1A"
    assert normalized["diff_pairs"][0]["n_name"] == "IOB1B"
    assert normalized["diff_pairs"][0]["pair_name"] == "IOB1A"
    assert normalized["vendor_extensions"] == {}


def test_normalized_parse_outputs_have_stable_identity_and_attrs():
    amd = json.loads((PINOUT_DIR / "xcku3pffva676pkg.json").read_text())
    gowin = json.loads((PINOUT_DIR / "gowin_gw5a-25_lq100.json").read_text())
    lattice = json.loads((PINOUT_DIR / "lattice_ecp5u-25_cabga256.json").read_text())
    intel = json.loads((PINOUT_DIR / "intel_agilex5_a5ec013b_b23a.json").read_text())

    assert amd["_vendor"] == "AMD"
    assert amd["_family"] == "Kintex UltraScale+"
    assert amd["_series"] == "Kintex UltraScale+"
    assert amd["_base_device"] == "XCKU3P"
    assert "attrs" in amd["pins"][0]
    assert "source_traceability" in amd
    assert amd["vendor_extensions"] == {}

    assert gowin["_vendor"] == "Gowin"
    assert gowin["_family"] == "Arora V"
    assert gowin["_series"] == "Arora V"
    assert "attrs" in gowin["pins"][0]
    assert "attrs" in next(iter(gowin["banks"].values()))
    assert gowin["vendor_extensions"] == {}

    assert lattice["_vendor"] == "Lattice"
    assert lattice["_family"] == "ECP5"
    assert lattice["_series"] == "ECP5"
    assert lattice["diff_pairs"][0]["p_pin"]
    assert "attrs" in lattice["diff_pairs"][0]
    assert lattice["vendor_extensions"] == {}

    assert intel["_vendor"] == "Intel/Altera"
    assert intel["_family"] == "Agilex 5"
    assert intel["_series"] == "E-Series"
    assert intel["_base_device"] == "A5E013B"
    assert intel["source_traceability"]["package_pinout"]["source_document_id"] == "819287"
    assert intel["vendor_extensions"]["ordering_variant"]["variant_code"] == "C"
