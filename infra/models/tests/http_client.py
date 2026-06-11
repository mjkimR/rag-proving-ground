#!/usr/bin/env python3
"""HTTP helpers for local model smoke scripts."""

from __future__ import annotations

from typing import Any

import httpx


def post_json(url: str, payload: dict[str, Any], *, timeout: float = 30.0) -> Any:
    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"HTTP {exc.response.status_code} from {url}: {exc.response.text}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Failed to call {url}: {exc}") from exc
    return response.json()


def require_number(value: Any, *, label: str) -> float:
    if not isinstance(value, int | float):
        raise AssertionError(f"{label} must be numeric, got {type(value).__name__}: {value!r}")
    return float(value)
