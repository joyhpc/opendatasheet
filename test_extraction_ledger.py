import json

from runtime.extraction_ledger import (
    LEDGER_SCHEMA,
    build_extraction_ledger,
    completed_domains,
    extraction_ledger_sidecar_path,
    should_skip_completed_domain,
    write_extraction_ledger_sidecar,
)


def _fake_result():
    return {
        "pdf_name": "part.pdf",
        "checksum": "abc123",
        "model": "gemini-test",
        "mode": "vision",
        "total_pages": 5,
        "domains": {
            "electrical": {"component": {"mpn": "PART"}, "electrical_characteristics": []},
            "package": {"error": "Gemini timeout", "error_type": "GeminiTimeout"},
            "thermal": {},
        },
        "domain_traces": {
            "electrical": {"selected_pages": [0, 2]},
            "package": {"selected_pages": [4]},
        },
        "domain_timings": {
            "electrical": 1.25,
            "package": 180.0,
            "thermal": 0.01,
        },
        "domain_validations": {
            "electrical": {"l2_validation": []},
            "package": {},
        },
    }


def test_build_extraction_ledger_records_domain_states():
    ledger = build_extraction_ledger(_fake_result())

    assert ledger["_schema"] == LEDGER_SCHEMA
    assert ledger["pdf_name"] == "part.pdf"
    assert ledger["steps"]["electrical"]["status"] == "ok"
    assert ledger["steps"]["electrical"]["selected_pages"] == [0, 2]
    assert len(ledger["steps"]["electrical"]["output_sha256"]) == 64
    assert ledger["steps"]["package"]["status"] == "error"
    assert ledger["steps"]["package"]["error"] == {
        "type": "GeminiTimeout",
        "message": "Gemini timeout",
    }
    assert ledger["steps"]["thermal"]["status"] == "skipped"


def test_ledger_resume_helpers_identify_completed_domains():
    ledger = build_extraction_ledger(_fake_result())

    assert completed_domains(ledger) == ["electrical"]
    assert should_skip_completed_domain(ledger, "electrical") is True
    assert should_skip_completed_domain(ledger, "package") is False
    assert should_skip_completed_domain(ledger, "thermal") is False


def test_write_extraction_ledger_sidecar_creates_state_file(tmp_path):
    output_path = tmp_path / "part.json"

    sidecar = write_extraction_ledger_sidecar(_fake_result(), output_path)

    assert sidecar == tmp_path / "_state" / "part.domain_ledger.json"
    assert sidecar == extraction_ledger_sidecar_path(output_path)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["steps"]["electrical"]["status"] == "ok"


def test_write_extraction_ledger_sidecar_skips_without_domains(tmp_path):
    sidecar = write_extraction_ledger_sidecar({"pdf_name": "part.pdf"}, tmp_path / "part.json")

    assert sidecar is None
    assert not (tmp_path / "_state").exists()
