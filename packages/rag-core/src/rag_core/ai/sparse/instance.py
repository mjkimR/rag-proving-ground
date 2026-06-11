from collections import OrderedDict
from typing import Any

from rag_core.ai.sparse.factory import SparseEmbeddingFactory
from rag_core.ai.sparse.interface import SparseEmbeddingModel
from rag_core.ai.sparse.schemas import SparseEmbeddings

_SPARSE_EMBEDDING_MODEL_CACHE: OrderedDict[str, SparseEmbeddingModel] = OrderedDict()
_MAX_CACHE_SIZE = 32


def get_sparse_embedding_model(model_name: str | None = None, **kwargs: Any) -> SparseEmbeddings:
    """Retrieve or create a cached instance of the configured sparse embedding model."""
    from rag_core.ai.models import _json_cache_key

    constructor_kwargs = dict(kwargs)
    cache_key = _json_cache_key({"model_name": model_name, **constructor_kwargs})

    if cache_key in _SPARSE_EMBEDDING_MODEL_CACHE:
        _SPARSE_EMBEDDING_MODEL_CACHE.move_to_end(cache_key)
        return _SPARSE_EMBEDDING_MODEL_CACHE[cache_key]

    model = SparseEmbeddingFactory.create_embeddings(model_name=model_name, **constructor_kwargs)
    _SPARSE_EMBEDDING_MODEL_CACHE[cache_key] = model

    if len(_SPARSE_EMBEDDING_MODEL_CACHE) > _MAX_CACHE_SIZE:
        _SPARSE_EMBEDDING_MODEL_CACHE.popitem(last=False)

    return model
