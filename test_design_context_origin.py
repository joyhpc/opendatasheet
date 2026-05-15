from design_info_utils import extract_design_context
from scripts.normal_ic_contract import _normalize_design_context_domain
from scripts.validate_exports import load_schema, validate_data


def test_design_context_emits_origin_boundaries():
    context = extract_design_context(
        [
            {
                "page_num": 4,
                "kind": "application",
                "text": "\n".join(
                    [
                        "Typical Application",
                        "Use an input capacitor CIN of 10 uF close to the device.",
                        "VOUT = 0.8 V to 12 V",
                        "R1 = R2 * (VOUT / VFB - 1)",
                        "PCB layout guidelines: place the input capacitor as close as possible and minimize the loop area.",
                    ]
                ),
            }
        ]
    )

    assert context["design_page_candidates"][0]["origin"]["kind"] == "source_fact"
    assert context["recommended_external_components"][0]["origin"]["kind"] == "deterministic_inference"
    assert context["component_value_hints"][0]["origin"]["kind"] == "source_fact"
    assert context["design_range_hints"][0]["origin"]["kind"] == "source_fact"
    assert context["design_equation_hints"][0]["origin"]["kind"] == "source_fact"
    assert context["layout_hints"][0]["origin"]["kind"] == "source_recommendation"


def test_design_context_origin_metadata_is_schema_compatible():
    context = extract_design_context(
        [
            {
                "page_num": 4,
                "kind": "application",
                "text": "\n".join(
                    [
                        "Typical Application",
                        "Use an input capacitor CIN of 10 uF close to the device.",
                        "PCB layout guidelines: place the input capacitor as close as possible.",
                    ]
                ),
            }
        ]
    )
    domain, _ = _normalize_design_context_domain(context, {})

    payload = {
        "_schema": "device-knowledge/2.0",
        "mpn": "TEST-PART",
        "domains": {
            "design_context": domain,
        },
    }

    assert domain["design_pages"]["pages"][0]["origin"]["kind"] == "source_fact"
    assert validate_data(load_schema(), payload) == []
