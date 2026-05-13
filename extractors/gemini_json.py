"""Shared Gemini JSON extraction helpers for extractor modules."""

from __future__ import annotations

import json
import hashlib
import time
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone

from google.genai import types


TRACE_SCHEMA_VERSION = "model-call-trace/1.0"


class TraceableDict(dict):
    """Dictionary result with non-serialized model trace metadata."""

    def __init__(self, *args, model_trace: dict | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_trace = model_trace or {}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_json_sha256(payload: dict) -> str:
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return _sha256_text(rendered)


def _usage_to_dict(usage) -> dict | None:
    if usage is None:
        return None
    keys = (
        "prompt_token_count",
        "candidates_token_count",
        "total_token_count",
        "cached_content_token_count",
    )
    data = {
        key: getattr(usage, key)
        for key in keys
        if getattr(usage, key, None) is not None
    }
    return data or None


def _build_base_trace(
    *,
    model: str,
    images: list[bytes],
    prompt: str,
    prompt_id: str,
    prompt_version: str,
    temperature: float,
    max_retries: int,
) -> dict:
    return {
        "_schema": TRACE_SCHEMA_VERSION,
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "prompt_sha256": _sha256_text(prompt),
        "prompt_length": len(prompt),
        "model": model,
        "temperature": temperature,
        "max_retries": max_retries,
        "input_images": [
            {
                "index": index,
                "mime_type": "image/png",
                "byte_length": len(image),
                "sha256": _sha256_bytes(image),
            }
            for index, image in enumerate(images)
        ],
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def _finish_trace(
    trace: dict,
    *,
    started_at: float,
    attempts: int,
    status: str,
    raw: str = "",
    result: dict | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    usage=None,
) -> dict:
    trace = dict(trace)
    trace.update({
        "status": status,
        "attempts": attempts,
        "latency_ms": round((time.time() - started_at) * 1000, 3),
    })
    if raw:
        trace["response_text_sha256"] = _sha256_text(raw)
        trace["response_text_length"] = len(raw)
    if result is not None:
        trace["response_json_sha256"] = _canonical_json_sha256(result)
    if error_type:
        trace["error_type"] = error_type
    if error_message:
        trace["error_message"] = error_message
    usage_data = _usage_to_dict(usage)
    if usage_data:
        trace["usage"] = usage_data
    return trace


def _strip_json_wrapper(raw: str) -> str:
    """Remove markdown fences and trim to the outermost JSON object."""
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in raw:
        raw = raw.split("```", 1)[1].split("```", 1)[0]

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    return raw


def _normalize_keys(payload: dict, key_aliases: Mapping[str, Iterable[str]] | None) -> dict:
    """Map alternate model output keys onto the canonical schema keys."""
    if not key_aliases:
        return payload

    normalized = dict(payload)
    for canonical_key, aliases in key_aliases.items():
        if canonical_key in normalized:
            continue
        for alias in aliases:
            if alias in normalized:
                normalized[canonical_key] = normalized.pop(alias)
                break
    return normalized


def _is_retryable_error(exc: Exception) -> bool:
    text = str(exc)
    name = type(exc).__name__
    return (
        "503" in text
        or "429" in text
        or "504" in text
        or "timeout" in text.lower()
        or "ReadTimeout" in name
        or "ConnectTimeout" in name
    )


def call_gemini_json_response(
    client,
    model: str,
    images: list[bytes],
    prompt: str,
    *,
    max_retries: int = 2,
    key_aliases: Mapping[str, Iterable[str]] | None = None,
    required_keys: Iterable[str] | None = None,
    temperature: float = 0.1,
    prompt_id: str = "inline",
    prompt_version: str = "unversioned",
) -> dict:
    """Call Gemini Vision and normalize the response into a JSON object."""
    contents = [prompt]
    for image in images:
        contents.append(types.Part.from_bytes(data=image, mime_type="image/png"))

    trace = _build_base_trace(
        model=model,
        images=images,
        prompt=prompt,
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        temperature=temperature,
        max_retries=max_retries,
    )
    started_at = time.time()
    raw = ""
    for attempt in range(max_retries + 1):
        attempts = attempt + 1
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config={"temperature": temperature},
            )
            raw = _strip_json_wrapper(response.text)
            result = json.loads(raw.strip())
            if isinstance(result, list):
                result = result[0] if result else {"error": "Empty list"}
            if not isinstance(result, dict):
                error = {"error": f"Unexpected type: {type(result).__name__}"}
                return TraceableDict(
                    error,
                    model_trace=_finish_trace(
                        trace,
                        started_at=started_at,
                        attempts=attempts,
                        status="error",
                        raw=raw,
                        result=error,
                        error_type="UnexpectedResponseType",
                        error_message=error["error"],
                        usage=getattr(response, "usage_metadata", None),
                    ),
                )

            result = _normalize_keys(result, key_aliases)
            missing = [
                key for key in (required_keys or ())
                if key not in result
            ]
            if missing:
                error = {
                    "error": f"Missing required keys: {', '.join(missing)}",
                    "raw": raw[:500],
                }
                return TraceableDict(
                    error,
                    model_trace=_finish_trace(
                        trace,
                        started_at=started_at,
                        attempts=attempts,
                        status="error",
                        raw=raw,
                        result=error,
                        error_type="MissingRequiredKeys",
                        error_message=error["error"],
                        usage=getattr(response, "usage_metadata", None),
                    ),
                )
            return TraceableDict(
                result,
                model_trace=_finish_trace(
                    trace,
                    started_at=started_at,
                    attempts=attempts,
                    status="ok",
                    raw=raw,
                    result=result,
                    usage=getattr(response, "usage_metadata", None),
                ),
            )
        except json.JSONDecodeError as exc:
            if attempt < max_retries:
                time.sleep(3)
                continue
            error = {
                "error": f"JSON parse failed: {str(exc)}",
                "raw": raw[:500],
            }
            return TraceableDict(
                error,
                model_trace=_finish_trace(
                    trace,
                    started_at=started_at,
                    attempts=attempts,
                    status="error",
                    raw=raw,
                    result=error,
                    error_type=exc.__class__.__name__,
                    error_message=error["error"],
                ),
            )
        except Exception as exc:
            if attempt < max_retries and _is_retryable_error(exc):
                time.sleep(10)
                continue
            error = {"error": str(exc)}
            return TraceableDict(
                error,
                model_trace=_finish_trace(
                    trace,
                    started_at=started_at,
                    attempts=attempts,
                    status="error",
                    raw=raw,
                    result=error,
                    error_type=exc.__class__.__name__,
                    error_message=str(exc),
                ),
            )
