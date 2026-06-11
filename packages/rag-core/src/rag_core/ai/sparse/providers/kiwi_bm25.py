"""BM25 sparse embeddings for Korean text."""

from __future__ import annotations

import math
import warnings
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any, ClassVar

from rag_core.ai.sparse.interface import SparseEmbeddingModel
from rag_core.ai.sparse.schemas import SparseVector
from rag_core.ai.sparse.utils import stable_token_id

TokenMapper = Callable[[str], int]
Tokenizer = Callable[[str], Sequence[str]]
QUERY_WITHOUT_CORPUS_WARNING = (
    "KoreanMorphemeBM25Embeddings.embed_query() was called before embed_documents(); "
    "query weights will use default_idf because corpus document-frequency statistics are unavailable."
)


class KoreanMorphemeBM25Embeddings(SparseEmbeddingModel):
    """BM25 sparse embeddings using Kiwi Korean morpheme tokenization.

    The class keeps corpus document-frequency statistics from the latest
    ``embed_documents`` call. ``embed_query`` uses those statistics when
    available, which matches the usual index-then-query lifecycle.
    """

    name: ClassVar[str] = "ko-kiwi-bm25"

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
        default_idf: float = 1.0,
        lowercase: bool = True,
        min_token_length: int = 1,
        allowed_poses: Sequence[str] | None = None,
        kiwi_kwargs: Mapping[str, Any] | None = None,
    ) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be greater than 0.")
        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1.")
        if default_idf <= 0:
            raise ValueError("default_idf must be greater than 0.")
        if min_token_length < 1:
            raise ValueError("min_token_length must be greater than 0.")

        self._tokenizer = tokenizer
        self._token_mapper = token_mapper or stable_token_id
        self._k1 = k1
        self._b = b
        self._default_idf = default_idf
        self._lowercase = lowercase
        self._min_token_length = min_token_length
        self._allowed_poses = frozenset(allowed_poses) if allowed_poses is not None else None
        self._kiwi_kwargs = dict(kiwi_kwargs or {})
        self._kiwi: Any | None = None
        self._document_count = 0
        self._average_document_length = 0.0
        self._document_frequency_by_token: dict[str, int] = {}

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        tokenized_texts = [self._tokenize(text) for text in texts]
        self._fit_corpus(tokenized_texts)
        return [self._bm25_vector(tokens, query=False) for tokens in tokenized_texts]

    def embed_query(self, text: str) -> SparseVector:
        if self._document_count == 0:
            warnings.warn(QUERY_WITHOUT_CORPUS_WARNING, RuntimeWarning, stacklevel=2)
        return self._bm25_vector(self._tokenize(text), query=True)

    def _fit_corpus(self, tokenized_texts: Sequence[Sequence[str]]) -> None:
        self._document_count = len(tokenized_texts)
        self._average_document_length = (
            sum(len(tokens) for tokens in tokenized_texts) / self._document_count if self._document_count else 0.0
        )
        document_frequency: Counter[str] = Counter()
        for tokens in tokenized_texts:
            document_frequency.update(set(tokens))
        self._document_frequency_by_token = dict(document_frequency)

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
        document_length = len(tokens)
        denominator_norm = 1.0
        if not query and self._average_document_length > 0:
            denominator_norm = 1 - self._b + self._b * (document_length / self._average_document_length)

        weights_by_index: dict[int, float] = {}
        for token, frequency in term_frequency.items():
            idf = self._idf(token)
            tf_weight = (frequency * (self._k1 + 1)) / (frequency + self._k1 * denominator_norm)
            index = self._token_mapper(token)
            weights_by_index[index] = weights_by_index.get(index, 0.0) + idf * tf_weight

        sorted_items = sorted(weights_by_index.items())
        return SparseVector(
            indices=[index for index, _ in sorted_items],
            values=[float(value) for _, value in sorted_items],
        )

    def _idf(self, token: str) -> float:
        if self._document_count <= 0:
            return self._default_idf
        document_frequency = self._document_frequency_by_token.get(token, 0)
        return math.log(1 + (self._document_count - document_frequency + 0.5) / (document_frequency + 0.5))
