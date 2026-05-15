import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "fpga" / "pinout"
PINOUT_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "pinout"
EXPORT_DIR = REPO_ROOT / "data" / "sch_review_export"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from export_for_sch_review import export_fpga
from parse_fpga_pinout import parse_pinout_file


def _load_pinout(name: str) -> dict:
    return json.loads((PINOUT_DIR / name).read_text(encoding="utf-8"))


def test_parse_artix_ultrascale_plus_pinout_normalizes_identity():
    parsed = parse_pinout_file(RAW_DIR / "xcau10pffvb676pkg.txt")

    assert parsed["_vendor"] == "AMD"
    assert parsed["_family"] == "Artix UltraScale+"
    assert parsed["_series"] == "Artix UltraScale+"
    assert parsed["_base_device"] == "XCAU10P"
    assert parsed["source_traceability"]["package_pinout"]["source_file"] == "xcau10pffvb676pkg.txt"
    assert parsed["lookup"]["pin_to_name"]["AB6"] == "MGTREFCLK0N_224"
    assert "attrs" in parsed["pins"][0]
    assert "attrs" in parsed["diff_pairs"][0]


def test_export_artix_ultrascale_plus_ffvb676_has_expected_identity():
    pinout = _load_pinout("xcau10pffvb676pkg.json")
    dc = json.loads((REPO_ROOT / "data" / "extracted_v2" / "fpga" / "ds931-artix-ultrascale-plus.json").read_text(encoding="utf-8"))

    exported = export_fpga(dc, pinout)

    assert exported["manufacturer"] == "AMD"
    assert exported["device_identity"] == {
        "vendor": "AMD",
        "family": "Artix UltraScale+",
        "series": "Artix UltraScale+",
        "base_device": "XCAU10P",
        "device": "XCAU10P",
        "package": "FFVB676",
    }
    assert exported["source_traceability"]["package_pinout"]["source_file"] == "xcau10pffvb676pkg.txt"
    assert exported["supply_specs"]["VCCINT_Standard_operation"]["typ"] == 0.85
    assert exported["capability_blocks"]["high_speed_serial"]["rx_lane_pairs"] == 12
    assert exported["lookup"]["by_pin"]["AB6"] == "MGTREFCLK0N_224"


def test_catalog_lists_artix_ultrascale_plus_packages():
    catalog = json.loads((EXPORT_DIR / "_fpga_catalog.json").read_text(encoding="utf-8"))
    artix = catalog["tree"]["AMD"]["families"]["Artix UltraScale+"]["series"]["Artix UltraScale+"]["base_devices"]

    assert sorted(artix) == ["XCAU10P", "XCAU15P", "XCAU20P", "XCAU25P", "XCAU7P"]
    assert artix["XCAU10P"]["devices"]["XCAU10P"]["packages"]["FFVB676"]["file"] == "XCAU10P_FFVB676.json"
    assert artix["XCAU25P"]["devices"]["XCAU25P"]["packages"]["SFVB784"]["has_serdes"] is True
