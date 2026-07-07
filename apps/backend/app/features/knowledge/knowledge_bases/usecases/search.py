from typing import Annotated, Any
from uuid import UUID

from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from loguru import logger
from rag_core.embeddings import RetrievalMode, resolve_knowledge_embedding_config
from rag_core.retrieval import RetrievedChunk, retrieve_knowledge_chunks, retrieve_multi_knowledge_chunks

from app.features.knowledge.knowledge_base_pages.repos import KnowledgeBasePageRepository
from app.features.knowledge.knowledge_bases.schemas import (
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    KnowledgeBaseSearchResultItem,
    MultiKnowledgeBaseSearchRequest,
)
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService


class SearchKnowledgeBaseUseCase(BaseUseCase):
    """UseCase to handle knowledge base search operations."""

    def __init__(
        self,
        service: Annotated[KnowledgeBaseService, Depends()],
        page_repo: Annotated[KnowledgeBasePageRepository, Depends()],
    ) -> None:
        self.service = service
        self.page_repo = page_repo

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

        # Resolve and apply search overrides
        try:
            resolved_config = _resolve_with_overrides(
                kb.name,
                kb.embedding_config,
                search_request.retrieval_mode,
                search_request.sparse_model,
                language=kb.language,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        # Retrieve chunks from the core library
        queries = search_request.queries
        try:
            chunks = await retrieve_knowledge_chunks(
                query=queries,
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

        # Fetch parent page content from Postgres
        async with AsyncTransaction() as session:
            await self.page_repo.enrich_chunks_with_page_content(session, chunks)

        results = [_search_result_from_chunk(chunk) for chunk in chunks]

        # Note: 'total' represents the count of retrieved results under the requested limit.
        return KnowledgeBaseSearchResponse(
            queries=queries,
            results=results,
            total=len(results),
        )


class SearchMultiKnowledgeBaseUseCase(BaseUseCase):
    """UseCase to search and merge results from multiple knowledge bases."""

    def __init__(
        self,
        service: Annotated[KnowledgeBaseService, Depends()],
        page_repo: Annotated[KnowledgeBasePageRepository, Depends()],
    ) -> None:
        self.service = service
        self.page_repo = page_repo

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

        kb_configs = []
        for kb_id in requested_ids:
            kb = found_by_id[kb_id]
            try:
                resolved_config = _resolve_with_overrides(
                    kb.name,
                    kb.embedding_config,
                    search_request.retrieval_mode,
                    search_request.sparse_model,
                    language=kb.language,
                )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                ) from e
            kb_configs.append((kb_id, resolved_config))

        queries = search_request.queries
        try:
            chunks = await retrieve_multi_knowledge_chunks(
                query=queries,
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

        # Fetch parent page content from Postgres
        async with AsyncTransaction() as session:
            await self.page_repo.enrich_chunks_with_page_content(session, chunks)

        results = [_search_result_from_chunk(chunk) for chunk in chunks]
        return KnowledgeBaseSearchResponse(
            queries=queries,
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
        page_content=chunk.page_content,
    )


def _resolve_with_overrides(
    kb_name: str,
    db_config: Any,
    override_mode: RetrievalMode | None,
    override_sparse_model: str | None,
    language: str = "en",
) -> Any:
    # First, resolve the database configuration
    resolved = resolve_knowledge_embedding_config(db_config, language=language)

    if override_mode is not None:
        # Check if the override mode requires a sparse index
        if override_mode in (RetrievalMode.SPARSE, RetrievalMode.HYBRID):
            # If the database configuration itself is DENSE, it doesn't have a sparse index!
            actual_mode = resolved.retrieval_mode
            if actual_mode == RetrievalMode.DENSE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Knowledge base '{kb_name}' cannot be searched in '{override_mode.value}' mode "
                        "because its active index was created in 'dense' mode. To support hybrid or sparse "
                        "retrieval, please change the retrieval mode of the Knowledge Base in strategy settings "
                        "and re-process the files."
                    ),
                )

        # Apply the retrieval mode override
        resolved = resolved.model_copy(update={"retrieval_mode": override_mode})

    if override_sparse_model is not None:
        resolved = resolved.model_copy(update={"sparse_model": override_sparse_model})

    return resolved
