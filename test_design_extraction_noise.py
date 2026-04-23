import json
from pathlib import Path

from scripts.export_design_bundle import _index_extracted_records, _load_datasheet_design_context

REPO_ROOT = Path(__file__).resolve().parent
EXPORT_DIR = REPO_ROOT / "data/sch_review_export"
EXTRACTED_DIR = REPO_ROOT / "data/extracted_v2"
PDF_DIR = REPO_ROOT / "data/raw/datasheet_PDF"


def _load_devices():
    devices = {}
    for path in EXPORT_DIR.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("mpn"):
            devices[payload["mpn"]] = payload
    return devices


def test_switch_noise_is_constrained():
    devices = _load_devices()
    index = _index_extracted_records(EXTRACTED_DIR)

    tps2552 = _load_datasheet_design_context(devices["TPS2552"], index, PDF_DIR)
    eqs = [item["equation"].lower() for item in tps2552.get("design_equation_hints", [])]
    assert all("fully enhanced" not in eq for eq in eqs)
    assert all("total power dissipation" not in eq for eq in eqs)
    assert len(tps2552.get("design_equation_hints", [])) <= 3

    st890 = _load_datasheet_design_context(devices["ST890"], index, PDF_DIR)
    previews = [item["preview"].lower() for item in st890.get("design_page_candidates", [])]
    assert all("contents st890" not in preview for preview in previews)
    assert all("revision history" not in preview for preview in previews)
    assert len(st890.get("layout_hints", [])) == 0


def test_interface_internal_component_noise_is_filtered():
    devices = _load_devices()
    index = _index_extracted_records(EXTRACTED_DIR)
    ctx = _load_datasheet_design_context(devices["Si3402-B"], index, PDF_DIR)
    snippets = [item["snippet"].lower() for item in ctx.get("recommended_external_components", [])]
    equations = [item["equation"].lower() for item in ctx.get("design_equation_hints", [])]
    assert all("not internally connected" not in snippet for snippet in snippets)
    assert all("is internal" not in snippet for snippet in snippets)
    assert all("internal soft-start" not in snippet for snippet in snippets)
    assert all("w/ diode" not in equation for equation in equations)


def test_range_hints_are_not_reported_as_equations():
    devices = _load_devices()
    index = _index_extracted_records(EXTRACTED_DIR)
    ctx = _load_datasheet_design_context(devices["TPS62147"], index, PDF_DIR)

    equations = [item["equation"] for item in ctx.get("design_equation_hints", [])]
    ranges = {(item["name"], item["min"], item["max"], item["unit"]) for item in ctx.get("design_range_hints", [])}

    assert all("VOUT = 0.8V to 12V" not in equation for equation in equations)
    assert ("VOUT", 0.8, 12.0, "V") in ranges


def test_switch_schematic_examples_replace_cover_page_noise():
    devices = _load_devices()
    index = _index_extracted_records(EXTRACTED_DIR)

    adg706 = _load_datasheet_design_context(devices["ADG706/ADG707"], index, PDF_DIR)
    pages = [item["page_num"] for item in adg706.get("design_page_candidates", [])]

    assert 0 not in pages
    assert any(page >= 8 for page in pages)


def test_switch_devices_extract_schematic_support_components():
    devices = _load_devices()
    index = _index_extracted_records(EXTRACTED_DIR)

    tps2114 = _load_datasheet_design_context(devices["TPS2114"], index, PDF_DIR)
    tps2114_roles = {item["role"] for item in tps2114.get("recommended_external_components", [])}
    tps2114_values = [item["values"] for item in tps2114.get("component_value_hints", [])]

    assert "current_limit_resistor" in tps2114_roles
    assert any("0.1 µF" in values for values in tps2114_values)

    tps2662x = _load_datasheet_design_context(devices["TPS2662x"], index, PDF_DIR)
    tps2662x_roles = {item["role"] for item in tps2662x.get("recommended_external_components", [])}

    assert {"current_limit_resistor", "dvdt_capacitor", "uvlo_divider", "ovp_divider"}.issubset(tps2662x_roles)


def test_opamp_application_pages_and_snubber_hints():
    devices = _load_devices()
    index = _index_extracted_records(EXTRACTED_DIR)

    ad8571 = _load_datasheet_design_context(devices["AD8571/AD8572/AD8574"], index, PDF_DIR)
    pages = {(item["page_num"], item["kind"]) for item in ad8571.get("design_page_candidates", [])}
    roles = {item["role"] for item in ad8571.get("recommended_external_components", [])}

    assert {(19, "application"), (20, "application"), (21, "application")}.issubset(pages)
    assert {"snubber_capacitor", "snubber_resistor", "output_capacitor"}.issubset(roles)

    lm358 = _load_datasheet_design_context(devices["LM358"], index, PDF_DIR)
    lm358_pages = [item["page_num"] for item in lm358.get("design_page_candidates", [])]

    assert 15 not in lm358_pages
    assert {6, 7, 8}.issubset(set(lm358_pages))


def test_decoder_block_diagram_pages_are_captured_for_design():
    devices = _load_devices()
    index = _index_extracted_records(EXTRACTED_DIR)

    tp2860 = _load_datasheet_design_context(devices["TP2860"], index, PDF_DIR)
    pages = {(item["page_num"], item["kind"]) for item in tp2860.get("design_page_candidates", [])}

    assert any(page >= 8 and kind == "application" for page, kind in pages)


def test_decoder_component_hints_filter_timing_noise_and_keep_link_parts():
    devices = _load_devices()
    index = _index_extracted_records(EXTRACTED_DIR)

    max96718a = _load_datasheet_design_context(devices["MAX96718A"], index, PDF_DIR)
    roles = {item["role"] for item in max96718a.get("recommended_external_components", [])}
    snippets = [item["snippet"].lower() for item in max96718a.get("recommended_external_components", [])]

    assert "feedback_divider" not in roles
    assert "inductor" not in roles
    assert {"line_fault_resistor", "termination_resistor", "link_isolation_capacitor", "poc_inductor"}.issubset(roles)
    assert all("packet spacing" not in snippet for snippet in snippets)
    assert all("cfg0 input resistor divider" not in snippet for snippet in snippets)


def test_decoder_component_values_capture_split_table_entries():
    devices = _load_devices()
    index = _index_extracted_records(EXTRACTED_DIR)

    max96718a = _load_datasheet_design_context(devices["MAX96718A"], index, PDF_DIR)
    hints = max96718a.get("recommended_external_components", [])
    value_snippets = " ".join(
        " ".join(item.get("values", [])) for item in max96718a.get("component_value_hints", [])
    )

    assert any(item["role"] == "link_isolation_capacitor" and item.get("value_hint") == "0.1 μF" for item in hints)
    assert any(item["role"] == "termination_resistor" and item.get("value_hint") == "49.9 Ω" for item in hints)
    assert any(item["role"] == "line_fault_resistor" and item.get("value_hint") in {"42.2kΩ", "48.7kΩ"} for item in hints)
    assert any(token in value_snippets for token in ["0.1 μF", "49.9 Ω", "42.2kΩ", "48.7kΩ"])


def test_current_decoder_design_contexts_capture_design_pages():
    devices = _load_devices()
    index = _index_extracted_records(EXTRACTED_DIR)

    tp2860 = _load_datasheet_design_context(devices["TP2860"], index, PDF_DIR)
    assert tp2860.get("source_mode") == "pdf_text"
    assert tp2860.get("design_page_candidates")

    max96718a = _load_datasheet_design_context(devices["MAX96718A"], index, PDF_DIR)
    assert max96718a.get("source_mode") == "pdf_text"
    assert max96718a.get("design_page_candidates")
    assert max96718a.get("recommended_external_components")


def test_removed_ds90ub_exports_are_absent_from_checked_in_device_index():
    devices = _load_devices()

    for mpn in ("DS90UB934TRGZRQ1", "DS90UB954TRGZRQ1", "DS90UB962WRTDTQ1", "DS90UB960WRTDRQ1", "DS90UB9702-Q1"):
        assert mpn not in devices
