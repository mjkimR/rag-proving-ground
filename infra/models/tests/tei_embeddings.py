#!/usr/bin/env python3
"""Smoke script for the local TEI BGE-M3 embedding service."""

from __future__ import annotations

import os
from typing import Any

from http_client import post_json, require_number

BASE_URL = os.environ.get("TEI_EMBEDDINGS_URL", "http://127.0.0.1:7998")
TIMEOUT = float(os.environ.get("MODEL_SMOKE_TIMEOUT", "60"))


def _extract_embedding(data: Any) -> list[float]:
    if isinstance(data, list) and data and isinstance(data[0], list):
        return data[0]
    if isinstance(data, dict):
        if isinstance(data.get("data"), list) and data["data"]:
            embedding = data["data"][0].get("embedding")
            if isinstance(embedding, list):
                return embedding
        if isinstance(data.get("embeddings"), list) and data["embeddings"]:
            embedding = data["embeddings"][0]
            if isinstance(embedding, list):
                return embedding
    raise AssertionError(f"Could not find embedding vector in response: {data!r}")


def main() -> None:
    data = post_json(
        f"{BASE_URL}/embed",
        {"inputs": ["BGE-M3 embedding smoke test for a local RAG pipeline."]},
        timeout=TIMEOUT,
    )
    embedding = _extract_embedding(data)
    if len(embedding) != 1024:
        raise AssertionError(f"Expected BGE-M3 dimension 1024, got {len(embedding)}")
    first = require_number(embedding[0], label="embedding[0]")
    print(f"OK tei-embeddings: dim={len(embedding)} first={first:.6f}")


if __name__ == "__main__":
    main()
