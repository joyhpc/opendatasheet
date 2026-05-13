import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
EXPORT_DIR = REPO_ROOT / "data" / "sch_review_export"
SCHEMA_PATH = REPO_ROOT / "schemas" / "sch-review-device.schema.json"


def test_schema_declares_thermal_section():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    normal_props = schema["$defs"]["normal_ic"]["properties"]
    fpga_props = schema["$defs"]["fpga"]["properties"]

    assert "thermal" in normal_props
    assert "thermal" in fpga_props


def test_checked_in_exports_include_thermal_samples():
    adm7155 = json.loads((EXPORT_DIR / "ADM7155.json").read_text(encoding="utf-8"))
    fst3125 = json.loads((EXPORT_DIR / "FST3125.json").read_text(encoding="utf-8"))
    xc9258 = json.loads((EXPORT_DIR / "XC9257_XC9258_Series.json").read_text(encoding="utf-8"))

    assert adm7155["thermal"]["theta_ja"]["typ"] == 36.7
    assert adm7155["thermal"]["theta_jc"]["typ"] == 23.5
    assert fst3125["thermal"]["theta_ja"]["max"] == 125
    assert any(key.startswith("power_dissipation") for key in xc9258["thermal"])


def test_all_exports_have_thermal_key():
    for path in EXPORT_DIR.glob("*.json"):
        if path.name.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "thermal" in data, path.name
        assert isinstance(data["thermal"], dict), path.name
