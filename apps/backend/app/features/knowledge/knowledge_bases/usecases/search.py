from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_bases.schemas import (
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeBaseSearchResultItem,
)
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from loguru import logger
from rag_core.embeddings import resolve_knowledge_embedding_config
from rag_core.retrieval import retrieve_knowledge_chunks


class SearchKnowledgeBaseUseCase(BaseUseCase):
    """UseCase to handle knowledge base search operations."""

    def __init__(self, service: Annotated[KnowledgeBaseService, Depends()]) -> None:
        self.service = service

    async def execute(
        self, knowledge_base_id: UUID, search_request: KnowledgeBaseSearchRequest
    ) -> KnowledgeBaseSearchResponse:
        async with AsyncTransaction() as session:
            kb = await self.service.repo.get_by_pk(session, knowledge_base_id)
            if not kb:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Knowledge base with ID {knowledge_base_id} not found.",
                )
            embedding_config = kb.embedding_config

        # Resolve the embedding configuration (resolving defaults if None)
        resolved_config = resolve_knowledge_embedding_config(embedding_config)

        # Retrieve chunks from the core library
        try:
            chunks = await retrieve_knowledge_chunks(
                query=search_request.query,
                knowledge_base_id=knowledge_base_id,
                embedding_config=resolved_config,
                limit=search_request.limit,
            )
        except Exception as e:
            logger.error(f"Failed to retrieve chunks from vector store for KB {knowledge_base_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Vector database side error occurred during search.",
            ) from e

        results = [
            KnowledgeBaseSearchResultItem(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                content=chunk.content,
                score=chunk.score,
                metadata=chunk.metadata,
            )
            for chunk in chunks
        ]

        # Note: 'total' represents the count of retrieved results under the requested limit.
        return KnowledgeBaseSearchResponse(
            query=search_request.query,
            results=results,
            total=len(results),
        )
