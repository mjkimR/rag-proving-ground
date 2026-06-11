#!/usr/bin/env python3
"""Smoke script for the local TEI BGE reranker service."""

from __future__ import annotations

import os
from typing import Any

from http_client import post_json, require_number

BASE_URL = os.environ.get("TEI_RERANKER_URL", "http://127.0.0.1:7999")
TIMEOUT = float(os.environ.get("MODEL_SMOKE_TIMEOUT", "60"))


def _extract_results(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return [item for item in data["results"] if isinstance(item, dict)]
    raise AssertionError(f"Could not find rerank results in response: {data!r}")


def _score(result: dict[str, Any]) -> float:
    for key in ("score", "relevance_score"):
        if key in result:
            return require_number(result[key], label=key)
    raise AssertionError(f"Rerank result has no score field: {result!r}")


def main() -> None:
    data = post_json(
        f"{BASE_URL}/rerank",
        {
            "query": "What service generates embeddings?",
            "texts": [
                "Text Embeddings Inference serves embedding vectors for retrieval.",
                "A tomato is a fruit often used like a vegetable.",
            ],
        },
        timeout=TIMEOUT,
    )
    results = _extract_results(data)
    if len(results) < 2:
        raise AssertionError(f"Expected at least 2 rerank results, got {len(results)}: {data!r}")
    top_score = _score(results[0])
    print(f"OK tei-reranker: results={len(results)} top_score={top_score:.6f} top={results[0]}")


if __name__ == "__main__":
    main()
