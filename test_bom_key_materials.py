import json

import pytest

from scripts.bom_key_materials import (
    build_lookup_queries,
    classify_key_material,
    extract_key_materials_from_file,
    load_bom,
)


def _write_export(export_dir, mpn="ACT4523"):
    export_dir.mkdir()
    (export_dir / f"{mpn}.json").write_text(
        json.dumps(
            {
                "_schema": "device-knowledge/2.0",
                "_type": "normal_ic",
                "mpn": mpn,
                "manufacturer": "Qorvo",
                "category": "Buck",
                "description": "Wide Input Sensorless CC/CV Step-Down DC/DC Converter",
            }
        ),
        encoding="utf-8",
    )


def test_bom_key_materials_parse_aliases_filter_passives_and_match_local_export(tmp_path):
    bom = tmp_path / "demo_bom.csv"
    bom.write_text(
        "\n".join(
            [
                "位号,数量,物料型号,厂商,描述,封装,规格",
                "U1,1,ACT4523,Qorvo,Wide Input Step-Down DC/DC Converter,SOP-8EP,",
                "R1 R2,2,RC0402FR-0710KL,Yageo,10k resistor,0402,10k",
                "Y1,1,ABM8-24.000MHZ,Abracon,24 MHz crystal,3225,24MHz",
                "J1,1,USB4105-GF-A,GCT,USB-C connector,TYPE-C,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    export_dir = tmp_path / "exports"
    _write_export(export_dir)

    report = extract_key_materials_from_file(bom, export_dir=export_dir)
    by_mpn = {item["mpn"]: item for item in report["key_materials"]}

    assert report["_schema"] == "bom-key-materials/1.0"
    assert report["summary"]["total_rows"] == 4
    assert report["summary"]["key_material_count"] == 3
    assert report["summary"]["skipped_row_count"] == 1
    assert by_mpn["ACT4523"]["evidence_status"] == "local_match"
    assert by_mpn["ACT4523"]["local_match"]["category"] == "Buck"
    assert by_mpn["ABM8-24.000MHZ"]["risk_tags"] == ["clock"]
    assert by_mpn["ABM8-24.000MHZ"]["evidence_status"] == "needs_web_lookup"
    assert "high_speed_interface" in by_mpn["USB4105-GF-A"]["risk_tags"]
    assert "connector" in by_mpn["USB4105-GF-A"]["risk_tags"]
    assert by_mpn["USB4105-GF-A"]["lookup_queries"]


def test_lookup_queries_prefer_known_manufacturer_domain():
    queries = build_lookup_queries(
        {
            "mpn": "TPS62147RGXT",
            "manufacturer": "Texas Instruments",
            "package": "VQFN-11",
            "description": "Step-down converter",
        }
    )

    assert queries[0] == '"TPS62147RGXT" "Texas Instruments" datasheet official'
    assert any(query.startswith("site:ti.com") for query in queries)
    assert any("package pinout" in query for query in queries)


def test_classification_keeps_plain_passives_out():
    is_key, reason, risk_tags, category = classify_key_material(
        {
            "designator": "R12 R13",
            "mpn": "RC0402FR-0710KL",
            "manufacturer": "Yageo",
            "description": "10k resistor",
            "category": "resistor",
            "value": "10k",
            "package": "0402",
        }
    )

    assert is_key is False
    assert "passive" in reason
    assert risk_tags == []
    assert category == "passive"


def test_xlsx_bom_header_can_start_after_preamble(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    bom = tmp_path / "bom.xlsx"
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "BOM"
    worksheet.append(["Project", "Demo board"])
    worksheet.append(["RefDes", "Qty", "Part Number", "Manufacturer", "Description"])
    worksheet.append(["U2", 1, "STM32F407VGT6", "STMicroelectronics", "MCU with Ethernet and USB"])
    workbook.save(bom)

    rows = load_bom(bom, sheet="BOM")

    assert len(rows) == 1
    assert rows[0].fields["mpn"] == "STM32F407VGT6"
    assert rows[0].fields["manufacturer"] == "STMicroelectronics"


def test_allegro_bom_continuation_and_description_identity_are_preserved(tmp_path):
    bom = tmp_path / "demo.BOM"
    bom.write_text(
        "\n".join(
            [
                "Bill Of Materials",
                "",
                "Item\tQuantity\tReference\tValue\tDescription",
                "______________________________________________",
                "1\t3\tU1,U2,\tTPS62147\t电源芯片\\降压转换器\\VQFN\\TPS62147RGXT\\Texas Instruments",
                "\t\tU3",
                "2\t2\tR1,R2\t10K\t贴片电阻\\10K\\0402\\RC0402FR-0710KL\\YAGEO",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = extract_key_materials_from_file(bom, export_dir=tmp_path / "no_exports")
    by_mpn = {item["mpn"]: item for item in report["key_materials"]}

    assert report["summary"]["total_rows"] == 2
    assert by_mpn["TPS62147RGXT"]["manufacturer"] == "Texas Instruments"
    assert by_mpn["TPS62147RGXT"]["package"] == "VQFN"
    assert by_mpn["TPS62147RGXT"]["designators"] == ["U1", "U2", "U3"]
    assert "power" in by_mpn["TPS62147RGXT"]["risk_tags"]
    assert "RC0402FR-0710KL" not in by_mpn


def test_gb18030_encoded_bom_is_supported(tmp_path):
    bom = tmp_path / "cn.BOM"
    bom.write_text(
        "\n".join(
            [
                "Item\tQuantity\tReference\tValue\tDescription",
                "1\t1\tJ1\tQSFP\t金手指插座\\QSFP+插座\\755860010\\MOLEX",
            ]
        )
        + "\n",
        encoding="gb18030",
    )

    report = extract_key_materials_from_file(bom, export_dir=tmp_path / "no_exports")
    item = report["key_materials"][0]

    assert item["mpn"] == "755860010"
    assert item["manufacturer"] == "MOLEX"
    assert "connector" in item["risk_tags"]


def test_description_identity_prefers_full_mpn_over_package_and_avoids_short_keyword_false_hits(tmp_path):
    bom = tmp_path / "ic.BOM"
    bom.write_text(
        "\n".join(
            [
                "Item\tQuantity\tReference\tValue\tDescription",
                "1\t3\tU8,U11,U13\tTPS56C215\tIC\\开关电源\\TPS56C215RNNR\\VQFN-HR-18\\TI",
                "2\t1\tL1\t2.2uH\t电感\\2.2uH\\±20%\\9.1A\\\\6.6*7.0*2.8\\贴片\\\\\\CSAB0730-2R2M\\CODACA",
                "3\t1\tJ4\t1X2P\tWAFER座\\\\PH2A\\2PIN*PH2.0\\\\180度\\直插\\白色",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = extract_key_materials_from_file(bom, export_dir=tmp_path / "no_exports")
    by_line = {item["line_number"]: item for item in report["key_materials"]}

    assert by_line[2]["mpn"] == "TPS56C215RNNR"
    assert by_line[2]["package"] == "VQFN-HR-18"
    assert by_line[3]["mpn"] == "CSAB0730-2R2M"
    assert by_line[3]["category_guess"] == "power"
    assert by_line[4]["category_guess"] == "connector"


def test_switches_are_kept_as_key_materials(tmp_path):
    bom = tmp_path / "switch.BOM"
    bom.write_text(
        "\n".join(
            [
                "Item\tQuantity\tReference\tValue\tDescription",
                "1\t1\tS1\tSW_BM-4BIT\t拨码开关\\PH2.54\\4位\\L11.72*W10.7*H9.5\\\\插件-侧拨",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = extract_key_materials_from_file(bom, export_dir=tmp_path / "no_exports")

    assert report["key_materials"][0]["category_guess"] == "switch_control"
    assert "switch_control" in report["key_materials"][0]["risk_tags"]


def test_description_infers_known_manufacturer_with_digit(tmp_path):
    bom = tmp_path / "secure_element.BOM"
    bom.write_text(
        "\n".join(
            [
                "Item\tQuantity\tReference\tValue\tDescription",
                "1\t1\tU112\tPC800\tIC\\加密\\PC800\\SOT23-6\\DO3THINK",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = extract_key_materials_from_file(bom, export_dir=tmp_path / "no_exports")
    item = report["key_materials"][0]

    assert item["mpn"] == "PC800"
    assert item["manufacturer"] == "DO3THINK"
    assert any(query.startswith('site:do3think.com "PC800"') for query in item["lookup_queries"])
