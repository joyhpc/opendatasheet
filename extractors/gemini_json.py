"""Shared Gemini JSON extraction helpers for extractor modules."""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Mapping

from google.genai import types


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
) -> dict:
    """Call Gemini Vision and normalize the response into a JSON object."""
    contents = [prompt]
    for image in images:
        contents.append(types.Part.from_bytes(data=image, mime_type="image/png"))

    raw = ""
    for attempt in range(max_retries + 1):
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
                return {"error": f"Unexpected type: {type(result).__name__}"}

            result = _normalize_keys(result, key_aliases)
            missing = [
                key for key in (required_keys or ())
                if key not in result
            ]
            if missing:
                return {
                    "error": f"Missing required keys: {', '.join(missing)}",
                    "raw": raw[:500],
                }
            return result
        except json.JSONDecodeError as exc:
            if attempt < max_retries:
                time.sleep(3)
                continue
            return {
                "error": f"JSON parse failed: {str(exc)}",
                "raw": raw[:500],
            }
        except Exception as exc:
            if attempt < max_retries and _is_retryable_error(exc):
                time.sleep(10)
                continue
            return {"error": str(exc)}
