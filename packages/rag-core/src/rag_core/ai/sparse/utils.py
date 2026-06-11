"""Utilities shared by sparse embedding implementations."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from typing import Any

from rag_core.ai.sparse.schemas import SparseVector


def stable_token_id(token: str) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def coerce_sparse_vector(value: Any) -> SparseVector:
    if isinstance(value, SparseVector):
        return value
    if hasattr(value, "indices") and hasattr(value, "values"):
        return SparseVector(indices=list(value.indices), values=[float(item) for item in value.values])
    if isinstance(value, Mapping):
        indices = value.get("indices")
        values = value.get("values")
        if isinstance(indices, Iterable) and isinstance(values, Iterable):
            return SparseVector(indices=[int(item) for item in indices], values=[float(item) for item in values])
    raise ValueError("Sparse vector must provide 'indices' and 'values'.")
