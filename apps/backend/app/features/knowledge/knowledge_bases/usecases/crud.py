from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from app.features.knowledge.knowledge_bases.schemas import KnowledgeBaseCreate, KnowledgeBasePatch, KnowledgeBasePut
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseContextKwargs, KnowledgeBaseService
from app_file_storage import get_storage_client
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseGetMultiUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from loguru import logger
from qdrant_client.http import models as qmodels
from rag_core.adapters.vector_store.instance import get_vector_store_provider


class GetKnowledgeBaseUseCase(BaseUseCase):
    def __init__(self, service: Annotated[KnowledgeBaseService, Depends()]) -> None:
        self.service = service

    async def execute(self, knowledge_base_id: UUID) -> KnowledgeBase | None:
        async with AsyncTransaction() as session:
            return await self.service.repo.get_by_pk(session, knowledge_base_id)


class GetMultiKnowledgeBaseUseCase(
    BaseGetMultiUseCase[KnowledgeBaseService, KnowledgeBase, KnowledgeBaseContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeBaseService, Depends()]) -> None:
        super().__init__(service)


class CreateKnowledgeBaseUseCase(
    BaseCreateUseCase[KnowledgeBaseService, KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeBaseService, Depends()]) -> None:
        super().__init__(service)


class PatchKnowledgeBaseUseCase(
    BasePatchUseCase[
        KnowledgeBaseService, KnowledgeBase, KnowledgeBasePut, KnowledgeBasePatch, KnowledgeBaseContextKwargs
    ]
):
    def __init__(self, service: Annotated[KnowledgeBaseService, Depends()]) -> None:
        super().__init__(service)


class PutKnowledgeBaseUseCase(
    BasePutUseCase[
        KnowledgeBaseService, KnowledgeBase, KnowledgeBasePut, KnowledgeBasePatch, KnowledgeBaseContextKwargs
    ]
):
    def __init__(self, service: Annotated[KnowledgeBaseService, Depends()]) -> None:
        super().__init__(service)


class DeleteKnowledgeBaseUseCase(BaseUseCase):
    def __init__(
        self,
        service: Annotated[KnowledgeBaseService, Depends()],
        doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
    ) -> None:
        self.service = service
        self.doc_service = doc_service

    async def execute(self, knowledge_base_id: UUID) -> dict:
        async with AsyncTransaction() as session:
            kb = await self.service.repo.get_by_pk(session, knowledge_base_id)
            if not kb:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Knowledge base with ID '{knowledge_base_id}' not found.",
                )

            # Retrieve all documents belonging to this KB
            docs = await self.doc_service.repo.get_all(
                session,
                where=(self.doc_service.repo.model.knowledge_base_id == knowledge_base_id,),
            )

            for doc in docs:
                # 1. Clean up Vector store points
                if kb.embed_config_hash:
                    try:
                        collection_name = f"vector_store_{kb.embed_config_hash}"
                        provider_client = get_vector_store_provider().client
                        provider_client.delete(
                            collection_name=collection_name,
                            points_selector=qmodels.FilterSelector(
                                filter=qmodels.Filter(
                                    must=[
                                        qmodels.FieldCondition(
                                            key="metadata.doc_id",
                                            match=qmodels.MatchValue(value=str(doc.id)),
                                        )
                                    ]
                                )
                            ),
                        )
                    except Exception as ve:
                        logger.warning(f"Failed to delete points from vector store for doc {doc.id}: {ve}")

                # 2. Clean up S3/MinIO files
                try:
                    storage_client = get_storage_client()
                    prefix = f"knowledge/{kb.name}/{doc.file_md5}/"
                    async for file_path in storage_client.list_files(prefix):
                        await storage_client.delete_file(file_path)
                except Exception as se:
                    logger.warning(f"Failed to delete assets from storage for doc {doc.id}: {se}")

            # 3. Delete database record
            success = await self.service.repo.delete_by_pk(session, knowledge_base_id)
            return {
                "status": "success" if success else "failed",
                "message": "Successfully deleted knowledge base and all associated child assets.",
            }
