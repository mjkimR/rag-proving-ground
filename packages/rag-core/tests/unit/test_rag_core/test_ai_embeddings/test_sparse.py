import math
from dataclasses import dataclass
from typing import Any, ClassVar

import pytest
from rag_core.ai.sparse import SparseVector
from rag_core.ai.sparse.providers.kiwi_bm25 import KoreanMorphemeBM25Embeddings
from rag_core.ai.sparse.providers.qdrant_bm25 import (
    QDRANT_BM25_MODEL,
    QdrantBM25SparseEmbeddings,
)


def test_korean_morpheme_bm25_embeddings_maps_tokens_to_sparse_vectors() -> None:
    embeddings = KoreanMorphemeBM25Embeddings(
        tokenizer=lambda text: text.split(),
        token_mapper={"한국어": 10, "검색": 20, "테스트": 30}.__getitem__,
    )

    vectors = embeddings.embed_documents(["한국어 검색 검색", "한국어 테스트"])
    query = embeddings.embed_query("검색 테스트")

    assert vectors[0].indices == [10, 20]
    assert vectors[0].values[1] > vectors[0].values[0]
    assert query.indices == [20, 30]
    assert all(value > 0 for value in query.values)


def test_korean_morpheme_bm25_embeddings_calculates_tf_saturation() -> None:
    embeddings = KoreanMorphemeBM25Embeddings(
        tokenizer=lambda text: text.split(),
        token_mapper={"token": 1}.__getitem__,
        k1=1.5,
        b=0.75,
        avg_length=100.0,
    )
    # 10 tokens: len = 10
    # frequency of "token" = 10
    vector = embeddings.embed_documents([" ".join(["token"] * 10)])[0]

    assert len(vector.indices) == 1
    assert vector.indices[0] == 1
    assert math.isclose(vector.values[0], 2.38379, rel_tol=1e-4)


def test_korean_morpheme_bm25_embeddings_filters_kiwi_pos_tags() -> None:
    @dataclass
    class Token:
        form: str
        tag: str

    class DummyKiwi:
        def tokenize(self, text: str) -> list[Token]:
            return [Token("검색", "NNG"), Token("을", "JKO"), Token("하다", "VV")]

    embeddings = KoreanMorphemeBM25Embeddings(
        token_mapper={"검색": 10, "하다": 20}.__getitem__,
        allowed_poses=("NNG", "VV"),
    )
    embeddings._kiwi = DummyKiwi()

    vector = embeddings.embed_query("검색을 하다")

    assert vector.indices == [10, 20]
    assert vector.values == [1.0, 1.0]


def test_qdrant_bm25_sparse_embeddings_wraps_fastembed_bm25(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class DummyFastEmbedSparse:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def embed_documents(self, texts: list[str]) -> list[SparseVector]:
            return [SparseVector(indices=[11], values=[float(len(text))]) for text in texts]

        def embed_query(self, text: str) -> SparseVector:
            return SparseVector(indices=[12], values=[float(len(text))])

    import langchain_qdrant

    monkeypatch.setattr(langchain_qdrant, "FastEmbedSparse", DummyFastEmbedSparse)

    embeddings = QdrantBM25SparseEmbeddings(batch_size=16, model_kwargs={"lazy_load": True})

    assert calls[0]["model_name"] == QDRANT_BM25_MODEL
    assert calls[0]["batch_size"] == 16
    assert calls[0]["lazy_load"] is True
    assert embeddings.embed_documents(["abc"])[0] == SparseVector(indices=[11], values=[3.0])
    assert embeddings.embed_query("abcd") == SparseVector(indices=[12], values=[4.0])


def test_sparse_embedding_registry_registers_and_resolves_classes() -> None:
    from rag_core.ai.sparse.interface import SparseEmbeddingModel
    from rag_core.ai.sparse.registry import SparseEmbeddingRegistry

    # Clear first to ensure a clean state
    SparseEmbeddingRegistry.clear()

    class DummyModel(SparseEmbeddingModel):
        name: ClassVar[str] = "dummy"

        def __init__(self, param: str) -> None:
            self.param = param

        @classmethod
        def from_config(cls, **kwargs) -> "DummyModel":
            return cls(**kwargs)

        def embed_documents(self, texts: list[str]) -> list[SparseVector]:
            return []

        def embed_query(self, text: str) -> SparseVector:
            return SparseVector(indices=[], values=[])

    SparseEmbeddingRegistry.register(DummyModel)
    assert "dummy" in SparseEmbeddingRegistry.list_models()

    # Resolve it
    model_class = SparseEmbeddingRegistry.get_model_class("dummy")
    instance = model_class.from_config(param="test-value")
    assert isinstance(instance, DummyModel)
    assert instance.param == "test-value"


def test_sparse_embedding_factory_resolves_default_models(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class DummyFastEmbedSparse:
        def __init__(self, **kwargs: Any) -> None:
            self.model_name = kwargs.get("model_name")
            calls.append(kwargs)

    import langchain_qdrant

    monkeypatch.setattr(langchain_qdrant, "FastEmbedSparse", DummyFastEmbedSparse)

    from rag_core.ai.sparse.factory import SparseEmbeddingFactory
    from rag_core.ai.sparse.providers.kiwi_bm25 import KoreanMorphemeBM25Embeddings
    from rag_core.ai.sparse.providers.qdrant_bm25 import QdrantBM25SparseEmbeddings

    # 1. Test resolving "ko-kiwi-bm25"
    ko_kiwi_bm25 = SparseEmbeddingFactory.create_embeddings("ko-kiwi-bm25", token_mapper=lambda x: 1)
    assert isinstance(ko_kiwi_bm25, KoreanMorphemeBM25Embeddings)

    # 2. Test resolving "en-bm25"
    en_bm25 = SparseEmbeddingFactory.create_embeddings("en-bm25")
    assert isinstance(en_bm25, QdrantBM25SparseEmbeddings)
    assert en_bm25.model_name == "Qdrant/bm25"

    # 3. Test resolving wildcard fallback (default to en-bm25 -> Qdrant/bm25)
    default_sparse = SparseEmbeddingFactory.create_embeddings()
    assert isinstance(default_sparse, QdrantBM25SparseEmbeddings)
    assert default_sparse.model_name == "Qdrant/bm25"

    # 4. Test resolving unsupported model raises ValueError
    with pytest.raises(ValueError, match="Unsupported sparse embedding model"):
        SparseEmbeddingFactory.create_embeddings(model_name="unsupported-model")

    # 5. Test list_supported_models()
    supported = SparseEmbeddingFactory.list_supported_models()
    assert "en-bm25" in supported
    assert "ko-kiwi-bm25" in supported
