"""BM25 sparse embeddings for Korean text."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any, ClassVar

from rag_core.ai.sparse.interface import SparseEmbeddingModel
from rag_core.ai.sparse.schemas import SparseVector
from rag_core.ai.sparse.utils import stable_token_id

TokenMapper = Callable[[str], int]
Tokenizer = Callable[[str], Sequence[str]]


class KoreanMorphemeBM25Embeddings(SparseEmbeddingModel):
    """BM25 sparse embeddings using Kiwi Korean morpheme tokenization.

    The class is completely stateless, relying on client-side TF Saturation
    and server-side (Qdrant) dynamic IDF calculations.
    """

    name: ClassVar[str] = "ko-kiwi-bm25"
    requires_server_side_idf: ClassVar[bool] = True

    @classmethod
    def from_config(cls, **kwargs: Any) -> KoreanMorphemeBM25Embeddings:
        """Create a KoreanMorphemeBM25Embeddings instance from configuration/kwargs."""
        return cls(**kwargs)

    def __init__(
        self,
        *,
        tokenizer: Tokenizer | None = None,
        token_mapper: TokenMapper | None = None,
        k1: float = 1.5,
        b: float = 0.75,
        avg_length: float = 300.0,
        lowercase: bool = True,
        min_token_length: int = 1,
        allowed_poses: Sequence[str] | None = None,
        kiwi_kwargs: Mapping[str, Any] | None = None,
    ) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be greater than 0.")
        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1.")
        if avg_length <= 0:
            raise ValueError("avg_length must be greater than 0.")
        if min_token_length < 1:
            raise ValueError("min_token_length must be greater than 0.")

        self._tokenizer = tokenizer
        self._token_mapper = token_mapper or stable_token_id
        self._k1 = k1
        self._b = b
        self._avg_length = avg_length
        self._lowercase = lowercase
        self._min_token_length = min_token_length
        self._allowed_poses = frozenset(allowed_poses) if allowed_poses is not None else None
        self._kiwi_kwargs = dict(kiwi_kwargs or {})
        self._kiwi: Any | None = None

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        return [self._bm25_vector(self._tokenize(text), query=False) for text in texts]

    def embed_query(self, text: str) -> SparseVector:
        return self._bm25_vector(self._tokenize(text), query=True)

    def _tokenize(self, text: str) -> list[str]:
        tokens = self._tokenizer(text) if self._tokenizer else self._tokenize_with_kiwi(text)
        normalized_tokens = []
        for token in tokens:
            normalized = token.strip()
            if self._lowercase:
                normalized = normalized.lower()
            if len(normalized) >= self._min_token_length:
                normalized_tokens.append(normalized)
        return normalized_tokens

    def _tokenize_with_kiwi(self, text: str) -> list[str]:
        if self._kiwi is None:
            try:
                from kiwipiepy import Kiwi  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ValueError("The 'kiwipiepy' package is required when no tokenizer is provided.") from exc
            self._kiwi = Kiwi(**self._kiwi_kwargs)
        assert self._kiwi is not None
        kiwi = self._kiwi
        tokens = kiwi.tokenize(text)
        if self._allowed_poses is None:
            return [token.form for token in tokens]
        return [token.form for token in tokens if token.tag in self._allowed_poses]

    def _bm25_vector(self, tokens: Sequence[str], *, query: bool) -> SparseVector:
        if not tokens:
            return SparseVector(indices=[], values=[])

        term_frequency = Counter(tokens)
        weights_by_index: dict[int, float] = {}

        if query:
            for token in term_frequency:
                index = self._token_mapper(token)
                weights_by_index[index] = 1.0
        else:
            document_length = len(tokens)
            denominator_norm = 1.0 - self._b + self._b * (document_length / self._avg_length)

            index_frequencies: dict[int, int] = {}
            for token, frequency in term_frequency.items():
                index = self._token_mapper(token)
                index_frequencies[index] = index_frequencies.get(index, 0) + frequency

            for index, frequency in index_frequencies.items():
                weights_by_index[index] = (frequency * (self._k1 + 1)) / (frequency + self._k1 * denominator_norm)

        sorted_items = sorted(weights_by_index.items())
        return SparseVector(
            indices=[index for index, _ in sorted_items],
            values=[float(value) for _, value in sorted_items],
        )
