#!/usr/bin/env python3
"""Smoke script for the local Infinity ColPali service using text query embeddings."""

from __future__ import annotations

import os
from typing import Any

from http_client import post_json, require_number

BASE_URL = os.environ.get("INFINITY_COLPALI_URL", "http://127.0.0.1:7997")
MODEL = os.environ.get("COLPALI_MODEL", "vidore/colpali-v1.3-merged")
TIMEOUT = float(os.environ.get("MODEL_SMOKE_TIMEOUT", "60"))


def _extract_multivector(data: Any) -> list[list[float]]:
    if isinstance(data, dict) and isinstance(data.get("data"), list) and data["data"]:
        embedding = data["data"][0].get("embedding")
        if isinstance(embedding, list) and embedding and isinstance(embedding[0], list):
            return embedding
    raise AssertionError(f"Could not find ColPali multi-vector embedding in response: {data!r}")


def main() -> None:
    data = post_json(
        f"{BASE_URL}/embeddings",
        {"model": MODEL, "input": ["ColPali text query embedding smoke test."]},
        timeout=TIMEOUT,
    )
    embedding = _extract_multivector(data)
    token_count = len(embedding)
    dim = len(embedding[0])
    if dim != 128:
        raise AssertionError(f"Expected ColPali vector dimension 128, got {dim}")
    first = require_number(embedding[0][0], label="embedding[0][0]")
    print(f"OK infinity-colpali: tokens={token_count} dim={dim} first={first:.6f}")


if __name__ == "__main__":
    main()
