"""Tests for model-call trace metadata.

These tests do not require network access. They use a fake Gemini client and
verify the audit metadata that travels beside model outputs.
"""

import hashlib
import json

from extractors.gemini_json import TraceableDict, call_gemini_json_response
from extractors.pin import (
    FPGA_PIN_PROMPT_ID,
    FPGA_PIN_PROMPT_VERSION,
    PIN_PROMPT_ID,
    PIN_PROMPT_VERSION,
    PinExtractor,
)
from pipeline_v2 import _build_domain_trace_record


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
