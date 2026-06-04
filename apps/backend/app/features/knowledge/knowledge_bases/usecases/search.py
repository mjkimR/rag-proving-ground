from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_bases.schemas import (
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeBaseSearchResultItem,
    MultiKnowledgeBaseSearchRequest,
)
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from loguru import logger
from rag_core.embeddings import resolve_knowledge_embedding_config
from rag_core.retrieval import RetrievedChunk, retrieve_knowledge_chunks, retrieve_multi_knowledge_chunks


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
            logger.exception(f"Failed to retrieve chunks from vector store for KB {knowledge_base_id}.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Vector database side error occurred during search.",
            ) from e

        results = [_search_result_from_chunk(chunk) for chunk in chunks]

        # Note: 'total' represents the count of retrieved results under the requested limit.
        return KnowledgeBaseSearchResponse(
            query=search_request.query,
            results=results,
            total=len(results),
        )


class SearchMultiKnowledgeBaseUseCase(BaseUseCase):
    """UseCase to search and merge results from multiple knowledge bases."""

    def __init__(self, service: Annotated[KnowledgeBaseService, Depends()]) -> None:
        self.service = service

    async def execute(self, search_request: MultiKnowledgeBaseSearchRequest) -> KnowledgeBaseSearchResponse:
        requested_ids = list(dict.fromkeys(search_request.knowledge_base_ids))
        async with AsyncTransaction() as session:
            knowledge_bases = await self.service.repo.get_all(
                session,
                where=(self.service.repo.model.id.in_(requested_ids),),
            )

        found_by_id = {kb.id: kb for kb in knowledge_bases}
        missing_ids = [knowledge_base_id for knowledge_base_id in requested_ids if knowledge_base_id not in found_by_id]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "One or more knowledge bases were not found.",
                    "missing_knowledge_base_ids": [str(knowledge_base_id) for knowledge_base_id in missing_ids],
                },
            )

        kb_configs = [
            (
                knowledge_base_id,
                resolve_knowledge_embedding_config(found_by_id[knowledge_base_id].embedding_config),
            )
            for knowledge_base_id in requested_ids
        ]

        try:
            chunks = await retrieve_multi_knowledge_chunks(
                query=search_request.query,
                kb_configs=kb_configs,
                limit=search_request.limit,
                reranker_config=search_request.reranker_config,
                candidate_limit=search_request.candidate_limit,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        except Exception as e:
            logger.exception("Failed to retrieve chunks from vector store for multiple KBs.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Vector database side error occurred during search.",
            ) from e

        results = [_search_result_from_chunk(chunk) for chunk in chunks]
        return KnowledgeBaseSearchResponse(
            query=search_request.query,
            results=results,
            total=len(results),
        )


def _search_result_from_chunk(chunk: RetrievedChunk) -> KnowledgeBaseSearchResultItem:
    return KnowledgeBaseSearchResultItem(
        chunk_id=chunk.chunk_id,
        doc_id=chunk.doc_id,
        content=chunk.content,
        score=chunk.score,
        knowledge_base_id=chunk.knowledge_base_id,
        vector_score=chunk.vector_score,
        rerank_score=chunk.rerank_score,
        metadata=chunk.metadata,
    )
