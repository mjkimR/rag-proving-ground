from typing import TYPE_CHECKING

from rag_core.ai.sparse.registry import SparseEmbeddingRegistry

if TYPE_CHECKING:
    from rag_core.ai.sparse.providers.kiwi_bm25 import KoreanMorphemeBM25Embeddings
    from rag_core.ai.sparse.providers.qdrant_bm25 import QdrantBM25SparseEmbeddings

_DEFAULTS_REGISTERED = False

__all__ = [
    "KoreanMorphemeBM25Embeddings",
    "QdrantBM25SparseEmbeddings",
    "register_default_sparse_models",
]

_lazy_imports: dict[str, str] = {
    "KoreanMorphemeBM25Embeddings": ".kiwi_bm25",
    "QdrantBM25SparseEmbeddings": ".qdrant_bm25",
}


def __getattr__(name: str):
    if name in _lazy_imports:
        import importlib

        module = importlib.import_module(_lazy_imports[name], package=__name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def register_default_sparse_models() -> None:
    """Register all built-in sparse embedding models with the registry."""
    global _DEFAULTS_REGISTERED
    if _DEFAULTS_REGISTERED and "ko-kiwi-bm25" in SparseEmbeddingRegistry.list_models():
        return

    from rag_core.ai.sparse.providers.kiwi_bm25 import KoreanMorphemeBM25Embeddings
    from rag_core.ai.sparse.providers.qdrant_bm25 import QdrantBM25SparseEmbeddings

    SparseEmbeddingRegistry.register(KoreanMorphemeBM25Embeddings)
    SparseEmbeddingRegistry.register(QdrantBM25SparseEmbeddings)
    _DEFAULTS_REGISTERED = True
