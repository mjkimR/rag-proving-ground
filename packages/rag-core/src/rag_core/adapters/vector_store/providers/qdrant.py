import asyncio
from typing import Any

from rag_core.adapters.vector_store.config import get_qdrant_settings
from rag_core.adapters.vector_store.interface import VectorStoreProvider, import_error_handler
from rag_core.ai.models import get_embedding_model


class QdrantProvider(VectorStoreProvider):
    @classmethod
    def from_env(cls) -> VectorStoreProvider:
        with import_error_handler("qdrant"):
            from qdrant_client import AsyncQdrantClient, QdrantClient
        config = get_qdrant_settings()
        api_key = config.api_key.get_secret_value() if config.api_key else None
        client = QdrantClient(url=config.url, api_key=api_key)
        async_client = AsyncQdrantClient(url=config.url, api_key=api_key)
        return QdrantProvider(client, async_client=async_client)

    def __init__(self, client: Any, *, async_client: Any | None = None) -> None:
        super().__init__(client)
        self.async_client = async_client

    async def close(self) -> None:
        if self.client:
            self.client.close()
        if self.async_client:
            await self.async_client.close()

    async def check_health(self) -> bool:
        if not self.async_client:
            return False
        try:
            await self.async_client.get_collections()
            return True
        except Exception:
            return False

    async def create_vector_store(
        self,
        collection_name: str,
        model_name: str,
        *,
        distance: str = "cosine",
        retrieval_mode: str = "dense",
        sparse_model: str | None = None,
    ) -> Any:
        from rag_core.embeddings import is_colpali_model

        if is_colpali_model(model_name):
            with import_error_handler("qdrant"):
                from qdrant_client.http import models as conf
                from qdrant_client.http.exceptions import ApiException
            from rag_core.adapters.vector_store.providers.colpali_qdrant import ColPaliQdrantStore
            from rag_core.ai.colpali import ColPaliModel

            colpali_model = ColPaliModel(model_name)
            distance_metric = _qdrant_distance(distance, conf)

            if not self.async_client:
                raise RuntimeError("Qdrant async client is not initialized.")

            if not await self.async_client.collection_exists(collection_name=collection_name):
                try:
                    await self.async_client.create_collection(
                        collection_name=collection_name,
                        vectors_config=conf.VectorParams(
                            size=colpali_model.embedding_dim,
                            distance=distance_metric,
                            multivector_config=conf.MultiVectorConfig(
                                comparator=conf.MultiVectorComparator.MAX_SIM,
                            ),
                        ),
                    )
                    # Create payload index on metadata.knowledge_id as partition key
                    await self.async_client.create_payload_index(
                        collection_name=collection_name,
                        field_name="metadata.knowledge_id",
                        field_schema=conf.PayloadSchemaType.KEYWORD,
                    )
                except ApiException as e:
                    if "exists" not in str(e):
                        raise e

            return ColPaliQdrantStore(
                client=self.client,
                async_client=self.async_client,
                collection_name=collection_name,
                colpali_model=colpali_model,
            )

        with import_error_handler("qdrant"):
            from langchain_qdrant import QdrantVectorStore
            from qdrant_client.http import models as conf
            from qdrant_client.http.exceptions import ApiException

        embedding_model = get_embedding_model(model_name)
        distance_metric = _qdrant_distance(distance, conf)

        if not self.async_client:
            raise RuntimeError("Qdrant async client is not initialized.")

        if not await self.async_client.collection_exists(collection_name=collection_name):
            try:
                dummy_embedding = await asyncio.to_thread(embedding_model.embed_query, "dummy")
                dimension = len(dummy_embedding)
            except Exception as exc:
                raise RuntimeError(f"Failed to retrieve embedding dimension for '{model_name}': {exc}") from exc

            requires_idf = False
            if retrieval_mode in ("hybrid", "sparse") and sparse_model:
                from loguru import logger

                from rag_core.ai.sparse.providers import register_default_sparse_models
                from rag_core.ai.sparse.registry import SparseEmbeddingRegistry

                register_default_sparse_models()
                try:
                    model_class = SparseEmbeddingRegistry.get_model_class(sparse_model)
                    requires_idf = getattr(model_class, "requires_server_side_idf", False)
                except ValueError as exc:
                    logger.error(
                        f"Unsupported sparse model variant: {sparse_model}. Ingestion scoring will be compromised."
                    )
                    raise RuntimeError(
                        f"Cannot configure vector store with unknown sparse provider: {sparse_model}"
                    ) from exc

            try:
                await self.async_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=conf.VectorParams(size=dimension, distance=distance_metric),
                    sparse_vectors_config=(
                        {
                            "sparse": conf.SparseVectorParams(
                                index=conf.SparseIndexParams(),
                                modifier=(conf.Modifier.IDF if requires_idf else None),
                            )
                        }
                        if retrieval_mode in ("hybrid", "sparse")
                        else None
                    ),
                )
                # Create payload index on metadata.knowledge_id as partition key
                await self.async_client.create_payload_index(
                    collection_name=collection_name,
                    field_name="metadata.knowledge_id",
                    field_schema=conf.PayloadSchemaType.KEYWORD,
                )
            except ApiException as e:
                if "exists" in str(e):
                    pass
                else:
                    raise e

        if retrieval_mode in ("hybrid", "sparse"):
            with import_error_handler("qdrant"):
                from langchain_qdrant import RetrievalMode
            from rag_core.ai.models import get_sparse_embedding_model

            sparse_embedding = get_sparse_embedding_model(sparse_model)
            mode = RetrievalMode.HYBRID if retrieval_mode == "hybrid" else RetrievalMode.SPARSE

            return QdrantVectorStore(
                client=self.client,
                collection_name=collection_name,
                embedding=embedding_model,
                sparse_embedding=sparse_embedding,
                retrieval_mode=mode,
                sparse_vector_name="sparse",
            )

        return QdrantVectorStore(
            client=self.client,
            collection_name=collection_name,
            embedding=embedding_model,
        )

    async def delete_points(self, collection_name: str, points_selector: Any) -> None:
        if not self.async_client:
            raise RuntimeError("Qdrant async client is not initialized.")
        if not await self.async_client.collection_exists(collection_name=collection_name):
            return
        await self.async_client.delete(collection_name=collection_name, points_selector=points_selector)


def _qdrant_distance(distance: str, conf: Any) -> Any:
    distance_by_name = {
        "cosine": conf.Distance.COSINE,
        "dot": conf.Distance.DOT,
        "euclid": conf.Distance.EUCLID,
    }
    try:
        return distance_by_name[distance.lower()]
    except KeyError as exc:
        supported = ", ".join(sorted(distance_by_name))
        raise ValueError(f"Unsupported Qdrant distance metric '{distance}'. Supported: {supported}.") from exc
