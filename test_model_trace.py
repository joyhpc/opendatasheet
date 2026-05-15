"""Tests for model-call trace metadata.

These tests do not require network access. They use a fake Gemini client and
verify the audit metadata that travels beside model outputs.
"""

import hashlib
import json

from extractors.gemini_json import ModelCallPolicy, TraceableDict, call_gemini_json_response
from extractors.pin import (
    FPGA_PIN_PROMPT_ID,
    FPGA_PIN_PROMPT_VERSION,
    PIN_PROMPT_ID,
    PIN_PROMPT_VERSION,
    PinExtractor,
)
from pipeline_v2 import (
    MODEL_AUDIT_SCHEMA,
    _build_domain_trace_record,
    build_model_audit_record,
    model_audit_sidecar_path,
    write_model_audit_sidecar,
)


class FakeUsage:
    prompt_token_count = 11
    candidates_token_count = 7
    total_token_count = 18


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.usage_metadata = FakeUsage()


class FakeModels:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({
            "model": model,
            "contents": contents,
            "config": config,
        })
        return FakeResponse(self.text)


class FakeClient:
    def __init__(self, text):
        self.models = FakeModels(text)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_call_gemini_json_response_attaches_success_trace():
    prompt = "Return JSON only."
    image = b"fake-png"
    client = FakeClient('{"logical_pins": []}')

    result = call_gemini_json_response(
        client,
        "gemini-test",
        [image],
        prompt,
        prompt_id="opendatasheet.test.pin",
        prompt_version="1.2.3",
        required_keys=("logical_pins",),
    )

    assert result == {"logical_pins": []}
    assert isinstance(result, TraceableDict)
    assert client.models.calls[0]["config"] == {"temperature": 0.1}

    trace = result.model_trace
    assert trace["_schema"] == "model-call-trace/1.0"
    assert trace["status"] == "ok"
    assert trace["attempts"] == 1
    assert trace["policy"] == {
        "max_retries": 2,
        "temperature": 0.1,
        "failure_mode": "error",
    }
    assert trace["prompt_id"] == "opendatasheet.test.pin"
    assert trace["prompt_version"] == "1.2.3"
    assert trace["prompt_sha256"] == _sha256_text(prompt)
    assert trace["model"] == "gemini-test"
    assert trace["input_images"] == [{
        "index": 0,
        "mime_type": "image/png",
        "byte_length": len(image),
        "sha256": hashlib.sha256(image).hexdigest(),
    }]
    assert trace["response_text_sha256"] == _sha256_text('{"logical_pins": []}')
    assert len(trace["response_json_sha256"]) == 64
    assert trace["usage"] == {
        "prompt_token_count": 11,
        "candidates_token_count": 7,
        "total_token_count": 18,
    }


def test_call_gemini_json_response_attaches_error_trace_for_missing_keys():
    client = FakeClient('{"pins": []}')

    result = call_gemini_json_response(
        client,
        "gemini-test",
        [],
        "Return JSON only.",
        prompt_id="opendatasheet.test.pin",
        prompt_version="1.2.3",
        required_keys=("logical_pins",),
    )

    assert result["error"] == "Missing required keys: logical_pins"
    trace = result.model_trace
    assert trace["status"] == "error"
    assert trace["error_type"] == "MissingRequiredKeys"
    assert trace["prompt_id"] == "opendatasheet.test.pin"
    assert trace["response_text_sha256"] == _sha256_text('{"pins": []}')
    assert len(trace["response_json_sha256"]) == 64


def test_call_gemini_json_response_enforces_image_budget():
    client = FakeClient('{"logical_pins": []}')

    result = call_gemini_json_response(
        client,
        "gemini-test",
        [b"image-1", b"image-2"],
        "Return JSON only.",
        prompt_id="opendatasheet.test.pin",
        prompt_version="1.2.3",
        policy=ModelCallPolicy(max_images=1),
    )

    assert result["error_type"] == "ModelBudgetExceeded"
    assert "2 > 1" in result["error"]
    assert client.models.calls == []
    trace = result.model_trace
    assert trace["status"] == "error"
    assert trace["attempts"] == 0
    assert trace["error_type"] == "ModelBudgetExceeded"
    assert trace["policy"]["max_images"] == 1


def test_traceable_dict_metadata_is_not_serialized_into_domain_payload():
    result = TraceableDict({"logical_pins": []}, model_trace={"prompt_id": "x"})

    assert json.loads(json.dumps(result)) == {"logical_pins": []}
    assert result.model_trace == {"prompt_id": "x"}


def test_build_domain_trace_record_adds_pipeline_context():
    class FakeExtractor:
        EXTRACTOR_VERSION = "2.0.0"

    record = _build_domain_trace_record(
        {"prompt_id": "opendatasheet.test"},
        domain_name="pin",
        extractor=FakeExtractor(),
        selected_pages=[0, 2],
        pdf_name="part.pdf",
        is_fpga=True,
    )

    assert record == {
        "prompt_id": "opendatasheet.test",
        "domain": "pin",
        "extractor": "FakeExtractor",
        "extractor_version": "2.0.0",
        "selected_pages": [0, 2],
        "pdf_name": "part.pdf",
        "is_fpga": True,
    }


def test_build_model_audit_record_uses_sidecar_shape():
    result = {
        "pdf_name": "part.pdf",
        "model": "gemini-test",
        "mode": "vision",
        "is_fpga": False,
        "checksum": "abc123",
        "total_pages": 3,
        "vision_pages": [0, 2],
        "domain_timings": {"pin": 0.25},
        "validation": [{"passed": False}],
        "physics_validation": [{"passed": True}],
        "pin_validation": [{"level": "warning"}],
        "cross_validation": {"value_coverage_pct": 100.0},
        "domain_traces": {
            "pin": {
                "_schema": "model-call-trace/1.0",
                "prompt_id": "opendatasheet.pin.standard",
            }
        },
        "domains": {"pin": {"logical_pins": []}},
    }

    audit = build_model_audit_record(result)

    assert audit["_schema"] == MODEL_AUDIT_SCHEMA
    assert audit["pdf_name"] == "part.pdf"
    assert audit["checksum"] == "abc123"
    assert audit["validation_summary"] == {
        "l2_failures": 1,
        "l5_failures": 0,
        "pin_issues": 1,
        "cross_validation": {"value_coverage_pct": 100.0},
    }
    assert audit["domain_traces"]["pin"]["prompt_id"] == "opendatasheet.pin.standard"
    assert "domains" not in audit


def test_write_model_audit_sidecar_creates_managed_file(tmp_path):
    result = {
        "pdf_name": "part.pdf",
        "domain_traces": {"electrical": {"prompt_id": "opendatasheet.electrical.vision"}},
    }
    output_path = tmp_path / "part.json"

    sidecar = write_model_audit_sidecar(result, output_path)

    assert sidecar == tmp_path / "_audit" / "part.model_trace.json"
    assert sidecar == model_audit_sidecar_path(output_path)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["_schema"] == MODEL_AUDIT_SCHEMA
    assert payload["domain_traces"]["electrical"]["prompt_id"] == "opendatasheet.electrical.vision"


def test_write_model_audit_sidecar_skips_without_traces(tmp_path):
    sidecar = write_model_audit_sidecar({"pdf_name": "part.pdf"}, tmp_path / "part.json")

    assert sidecar is None
    assert not (tmp_path / "_audit").exists()


def test_pin_extractor_uses_standard_prompt_identity():
    extractor = PinExtractor(
        client=FakeClient('{"logical_pins": []}'),
        model="gemini-test",
        pdf_path="part.pdf",
        page_classification=[],
        is_fpga=False,
    )

    result = extractor.extract([b"fake-png"])

    assert result.model_trace["prompt_id"] == PIN_PROMPT_ID
    assert result.model_trace["prompt_version"] == PIN_PROMPT_VERSION


def test_pin_extractor_uses_fpga_prompt_identity():
    extractor = PinExtractor(
        client=FakeClient('{"logical_pins": []}'),
        model="gemini-test",
        pdf_path="part.pdf",
        page_classification=[],
        is_fpga=True,
    )

    result = extractor.extract([b"fake-png"])

    assert result.model_trace["prompt_id"] == FPGA_PIN_PROMPT_ID
    assert result.model_trace["prompt_version"] == FPGA_PIN_PROMPT_VERSION
