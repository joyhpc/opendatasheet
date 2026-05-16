"""Phase-1 stabilization tests for pipeline_v2 failure isolation (R6).

  - A crash in one extractor must not abort the other domains.
  - A crash on one PDF must not abort the rest of the batch; failures are
    recorded in OUTPUT_DIR/_failures.json.
"""
import io
import json
import shutil
import sys
import tempfile
import time as _real_time
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

import pipeline_v2


class _FakeExtractor:
    """Minimal extractor stub for _extract_one_domain tests."""

    def __init__(self, domain_name, *, crash=False, result=None):
        self.DOMAIN_NAME = domain_name
        self._crash = crash
        self._result = {"ok": True} if result is None else result

    def select_pages(self):
        return []

    def extract(self, _payload):
        if self._crash:
            raise RuntimeError("simulated extractor crash")
        return self._result

    def validate(self, _result):
        return {"validated": True}


class _NoSleepTime:
    """time-module shim that delegates everything but no-ops sleep()."""

    def __getattr__(self, name):
        return getattr(_real_time, name)

    def sleep(self, *_a, **_k):
        return None


# --- extractor-level isolation -------------------------------------------

def test_extract_one_domain_isolates_a_crash():
    crash = _FakeExtractor("design_context", crash=True)
    result, validation, pages = pipeline_v2._extract_one_domain(crash, "x.pdf", {})
    assert "error" in result
    assert result["error_type"] == "ExtractorCrash"
    assert "RuntimeError" in result["error"]
    assert validation == {} and pages == []


def test_extract_one_domain_passes_through_success():
    ok = _FakeExtractor("design_context", result={"design_page_candidates": []})
    result, validation, _pages = pipeline_v2._extract_one_domain(ok, "x.pdf", {})
    assert result == {"design_page_candidates": []}
    assert validation == {"validated": True}


def test_other_domains_continue_after_one_crashes():
    """Mirror the process_single_pdf loop: one crash leaves the rest intact."""
    extractors = [
        _FakeExtractor("design_context", result={"a": 1}),
        _FakeExtractor("design_context", crash=True),
        _FakeExtractor("design_context", result={"b": 2}),
    ]
    domains: dict = {}
    for idx, ex in enumerate(extractors):
        result, _v, _p = pipeline_v2._extract_one_domain(ex, "x.pdf", domains)
        domains[f"d{idx}"] = result
    assert domains["d0"] == {"a": 1}
    assert "error" in domains["d1"]
    assert domains["d2"] == {"b": 2}, "extractor after the crash did not run"


# --- batch-level isolation ----------------------------------------------

def _run_batch_isolation_and_capture():
    """Run the batch-isolation scenario and return (good_exists, failures)."""
    tmp = Path(tempfile.mkdtemp())
    data_dir = tmp / "raw"
    out_dir = tmp / "out"
    data_dir.mkdir()
    out_dir.mkdir()
    (data_dir / "good.pdf").write_bytes(b"%PDF-1.4 fake")
    (data_dir / "bad.pdf").write_bytes(b"%PDF-1.4 fake")

    def fake_process(pdf_path):
        if "bad" in str(pdf_path):
            raise RuntimeError("simulated extraction crash")
        return {"pdf_name": Path(pdf_path).name, "extraction": {},
                "validation": [], "cross_validation": {}}

    saved = {name: getattr(pipeline_v2, name) for name in (
        "DATA_DIR", "OUTPUT_DIR", "process_single_pdf",
        "write_model_audit_sidecar", "write_extraction_ledger_sidecar", "time",
    )}
    try:
        pipeline_v2.DATA_DIR = data_dir
        pipeline_v2.OUTPUT_DIR = out_dir
        pipeline_v2.process_single_pdf = fake_process
        pipeline_v2.write_model_audit_sidecar = lambda *a, **k: None
        pipeline_v2.write_extraction_ledger_sidecar = lambda *a, **k: None
        pipeline_v2.time = _NoSleepTime()
        with redirect_stdout(io.StringIO()):
            pipeline_v2.run_batch(limit=0)
        good_exists = (out_dir / "good.json").exists()
        failures_path = out_dir / "_failures.json"
        failures = (json.loads(failures_path.read_text(encoding="utf-8"))
                    if failures_path.exists() else None)
        return good_exists, failures
    finally:
        for name, value in saved.items():
            setattr(pipeline_v2, name, value)
        shutil.rmtree(tmp, ignore_errors=True)


def test_run_batch_continues_and_records_failures():
    good_exists, failures = _run_batch_isolation_and_capture()
    assert good_exists, "good.pdf output missing — batch did not isolate the failure"
    assert failures is not None, "_failures.json not written"
    assert failures["count"] == 1
    assert failures["failed"][0]["pdf"] == "bad.pdf"
    assert failures["failed"][0]["error_type"] == "RuntimeError"


if __name__ == "__main__":
    failed = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"PASS {_name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {_name}: {exc}")
    print("OK" if not failed else f"{failed} FAILED")
    sys.exit(1 if failed else 0)
