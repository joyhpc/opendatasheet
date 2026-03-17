import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
PINOUT_DIR = REPO_ROOT / "data" / "extracted_v2" / "fpga" / "pinout"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build_fpga_catalog import build_catalog
from export_for_sch_review import export_fpga


def _load_pinout(name: str) -> dict:
    return json.loads((PINOUT_DIR / name).read_text())


def test_export_fpga_infers_device_identity_across_vendors():
    amd = export_fpga({"extraction": {"component": {}}}, _load_pinout("xcku3pffva676pkg.json"))
    gowin = export_fpga({"extraction": {"component": {}}}, _load_pinout("gowin_gw5a-25_lq100.json"))
    lattice = export_fpga({"extraction": {"component": {}}}, _load_pinout("lattice_ecp5u-25_cabga256.json"))

    assert amd["device_identity"] == {
        "vendor": "AMD",
        "family": "Kintex UltraScale+",
        "series": "Kintex UltraScale+",
        "base_device": "XCKU3P",
        "device": "XCKU3P",
        "package": "FFVA676",
    }
    assert gowin["device_identity"] == {
        "vendor": "Gowin",
        "family": "Arora V",
        "series": "Arora V",
        "base_device": "GW5A-25",
        "device": "GW5A-25",
        "package": "LQ100",
    }
    assert lattice["device_identity"] == {
        "vendor": "Lattice",
        "family": "ECP5",
        "series": "ECP5",
        "base_device": "ECP5U-25",
        "device": "ECP5U-25",
        "package": "CABGA256",
    }


def test_build_fpga_catalog_groups_by_family_series_and_base_device(tmp_path):
    exports = [
        export_fpga({"extraction": {"component": {}}}, _load_pinout("xcku3pffva676pkg.json")),
        export_fpga({"extraction": {"component": {}}}, _load_pinout("gowin_gw5a-25_lq100.json")),
        export_fpga({"extraction": {"component": {}}}, _load_pinout("intel_agilex5_a5ec013b_b23a.json")),
        export_fpga({"extraction": {"component": {}}}, _load_pinout("intel_agilex5_a5ed013b_b23a.json")),
    ]

    for export in exports:
        path = tmp_path / f"{export['mpn']}_{export['package']}.json"
        path.write_text(json.dumps(export, indent=2) + "\n", encoding="utf-8")

    catalog = build_catalog(tmp_path)

    assert catalog["summary"] == {
        "vendor_count": 3,
        "family_count": 3,
        "series_count": 3,
        "base_device_count": 3,
        "device_count": 4,
        "package_count": 4,
    }

    agilex5 = catalog["tree"]["Intel/Altera"]["families"]["Agilex 5"]["series"]["E-Series"]["base_devices"]["A5E013B"]["devices"]
    assert sorted(agilex5) == ["A5EC013B", "A5ED013B"]
    assert agilex5["A5EC013B"]["packages"]["B23A"]["has_serdes"] is True
    assert agilex5["A5ED013B"]["packages"]["B23A"]["has_hps"] is True
    assert catalog["tree"]["AMD"]["families"]["Kintex UltraScale+"]["series"]["Kintex UltraScale+"]["base_devices"]["XCKU3P"]["devices"]["XCKU3P"]["packages"]["FFVA676"]["file"] == "XCKU3P_FFVA676.json"
