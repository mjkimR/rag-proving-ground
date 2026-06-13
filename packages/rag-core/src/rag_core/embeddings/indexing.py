"""Helpers for indexing knowledge chunks into vector stores."""

from collections.abc import Iterable
from uuid import UUID

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from qdrant_client.http import models as qmodels

from rag_core.adapters.vector_store import check_vector_store_health
from rag_core.adapters.vector_store.instance import get_vector_store, get_vector_store_provider
from rag_core.chunkers.schemas import ChunkedDocument
from rag_core.embeddings.schemas import (
    KnowledgeEmbeddingConfig,
    knowledge_embedding_config_hash,
    knowledge_vector_collection_name,
)


async def get_knowledge_vector_store(config: KnowledgeEmbeddingConfig) -> tuple[VectorStore, str, str]:
    """Returns the VectorStore instance, collection name, and configuration hash for a resolved embedding config.

    Args:
        config: The knowledge embedding configuration. Must be resolved (i.e., contain a model).

    Returns:
        tuple[VectorStore, str, str]: A tuple containing:
            - VectorStore: The active LangChain VectorStore instance.
            - str: The name of the vector database collection.
            - str: The configuration hash for the resolved embedding config.

    Raises:
        ValueError: If the configuration has not been resolved (e.g., config.model is None).
        RuntimeError: If the vector database is not healthy or is uninitialized.
    """

    if config.model is None:
        raise ValueError("Knowledge embedding config must be resolved before creating a vector store.")

    vector_store_healthy = await check_vector_store_health()
    if not vector_store_healthy:
        raise RuntimeError("Vector Database is not healthy or uninitialized.")

    embed_config_hash = knowledge_embedding_config_hash(config)
    collection_name = knowledge_vector_collection_name(embed_config_hash)
    vector_store = await get_vector_store(
        collection_name=collection_name,
        model_name=config.model,
        distance=config.distance.value,
        retrieval_mode=config.retrieval_mode.value,
        sparse_model=config.sparse_model,
    )
    return vector_store, collection_name, embed_config_hash


def chunks_to_langchain_documents(chunks: Iterable[ChunkedDocument], *, knowledge_base_id: UUID) -> list[Document]:
    """Converts chunk records into LangChain Document instances with knowledge base metadata.

    Args:
        chunks: An iterable of chunked document records.
        knowledge_base_id: The ID of the knowledge base to associate the documents with.

    Returns:
        list[Document]: A list of converted LangChain documents.
    """

    documents: list[Document] = []
    for chunk in chunks:
        document = chunk.to_langchain_document()
        document.metadata["knowledge_id"] = str(knowledge_base_id)
        documents.append(document)
    return documents


async def delete_document_vectors(collection_name: str, document_id: UUID | str) -> None:
    """Deletes all indexed vectors for a specific document from the configured collection.

    Args:
        collection_name: The name of the collection from which vectors should be deleted.
        document_id: The unique identifier of the document to delete.
    """

    provider = get_vector_store_provider()
    await provider.delete_points(
        collection_name=collection_name,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="metadata.doc_id",
                        match=qmodels.MatchValue(value=str(document_id)),
                    )
                ]
            )
        ),
    )
