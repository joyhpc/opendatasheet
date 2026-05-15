"""Sidecar ledger helpers for extraction domain progress."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


LEDGER_SCHEMA = "opendatasheet-extraction-ledger/1.0"


def _canonical_sha256(payload: Any) -> str:
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _domain_status(payload: Any) -> str:
    if isinstance(payload, dict) and payload.get("error"):
        return "error"
    if payload in ({}, [], None):
        return "skipped"
    return "ok"


def _domain_error(payload: Any) -> dict | None:
    if not isinstance(payload, dict) or not payload.get("error"):
        return None
    return {
        "type": payload.get("error_type") or "ExtractionError",
        "message": str(payload.get("error")),
    }


def build_extraction_ledger(result: dict) -> dict | None:
    domains = result.get("domains")
    if not isinstance(domains, dict) or not domains:
        return None

    traces = result.get("domain_traces", {})
    timings = result.get("domain_timings", {})
    validations = result.get("domain_validations", {})
    steps = {}

    for domain_name in sorted(domains):
        payload = domains.get(domain_name)
        trace = traces.get(domain_name, {}) if isinstance(traces, dict) else {}
        status = _domain_status(payload)
        step = {
            "status": status,
            "selected_pages": trace.get("selected_pages", []),
            "timing_s": timings.get(domain_name) if isinstance(timings, dict) else None,
        }
        if status == "ok":
            step["output_sha256"] = _canonical_sha256(payload)
        error = _domain_error(payload)
        if error:
            step["error"] = error
        if isinstance(validations, dict) and domain_name in validations:
            step["validation_sha256"] = _canonical_sha256(validations[domain_name])
        steps[domain_name] = {key: value for key, value in step.items() if value is not None}

    return {
        "_schema": LEDGER_SCHEMA,
        "pdf_name": result.get("pdf_name"),
        "checksum": result.get("checksum"),
        "model": result.get("model"),
        "mode": result.get("mode"),
        "total_pages": result.get("total_pages"),
        "steps": steps,
    }


def completed_domains(ledger: dict) -> list[str]:
    steps = ledger.get("steps", {}) if isinstance(ledger, dict) else {}
    return sorted(
        domain
        for domain, step in steps.items()
        if isinstance(step, dict) and step.get("status") == "ok"
    )


def should_skip_completed_domain(ledger: dict, domain_name: str) -> bool:
    steps = ledger.get("steps", {}) if isinstance(ledger, dict) else {}
    step = steps.get(domain_name, {}) if isinstance(steps, dict) else {}
    return isinstance(step, dict) and step.get("status") == "ok" and bool(step.get("output_sha256"))


def extraction_ledger_sidecar_path(output_path: str | Path) -> Path:
    output_path = Path(output_path)
    return output_path.parent / "_state" / f"{output_path.stem}.domain_ledger.json"


def write_extraction_ledger_sidecar(result: dict, output_path: str | Path) -> Path | None:
    ledger = build_extraction_ledger(result)
    if ledger is None:
        return None

    sidecar_path = extraction_ledger_sidecar_path(output_path)
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(
        json.dumps(copy.deepcopy(ledger), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return sidecar_path
