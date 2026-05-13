from __future__ import annotations

from typing import Any


RETRIABLE_ERROR_TYPES = {"capacity", "timeout", "provider_unavailable", "rate_limit"}


def classify_model_error(error: Any) -> dict[str, Any]:
    message = _short_error(error)
    lowered = message.lower()
    error_type = "unknown"

    if "capacity" in lowered or "at capacity" in lowered:
        error_type = "capacity"
    elif "rate limit" in lowered or "429" in lowered:
        error_type = "rate_limit"
    elif "timeout" in lowered or "timed out" in lowered:
        error_type = "timeout"
    elif "bad gateway" in lowered or "502" in lowered or "503" in lowered or "unavailable" in lowered:
        error_type = "provider_unavailable"
    elif "image" in lowered or "图片" in message or "vision" in lowered:
        error_type = "image_unsupported"
    elif "json" in lowered or "无法解析" in message or "必须是对象" in message:
        error_type = "invalid_json"
    elif "unauthorized" in lowered or "api key" in lowered or "401" in lowered:
        error_type = "auth"

    return {
        "error": message,
        "error_type": error_type,
        "retriable": error_type in RETRIABLE_ERROR_TYPES,
    }


def model_failure(model: str, error: Any) -> dict[str, Any]:
    return {
        "model": model,
        **classify_model_error(error),
        "degraded": True,
    }


def _short_error(error: Any) -> str:
    return str(error).strip().replace("\n", " ")[:120] or "unknown error"
