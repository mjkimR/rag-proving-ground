from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentPatch,
    KnowledgeBaseDocumentPut,
)
from app.features.knowledge.knowledge_base_documents.services import (
    KnowledgeBaseDocumentContextKwargs,
    KnowledgeBaseDocumentService,
)
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app_file_storage import get_storage_client
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from loguru import logger
from qdrant_client.http import models as qmodels
from rag_core.adapters.vector_store.instance import get_vector_store_provider


class GetKnowledgeBaseDocumentUseCase(
    BaseGetUseCase[KnowledgeBaseDocumentService, KnowledgeBaseDocument, KnowledgeBaseDocumentContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeBaseDocumentService, Depends()]) -> None:
        super().__init__(service)


class GetMultiKnowledgeBaseDocumentUseCase(
    BaseGetMultiUseCase[KnowledgeBaseDocumentService, KnowledgeBaseDocument, KnowledgeBaseDocumentContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeBaseDocumentService, Depends()]) -> None:
        super().__init__(service)


class CreateKnowledgeBaseDocumentUseCase(
    BaseCreateUseCase[
        KnowledgeBaseDocumentService,
        KnowledgeBaseDocument,
        KnowledgeBaseDocumentCreate,
        KnowledgeBaseDocumentContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeBaseDocumentService, Depends()]) -> None:
        super().__init__(service)


class PatchKnowledgeBaseDocumentUseCase(
    BasePatchUseCase[
        KnowledgeBaseDocumentService,
        KnowledgeBaseDocument,
        KnowledgeBaseDocumentPut,
        KnowledgeBaseDocumentPatch,
        KnowledgeBaseDocumentContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeBaseDocumentService, Depends()]) -> None:
        super().__init__(service)


class PutKnowledgeBaseDocumentUseCase(
    BasePutUseCase[
        KnowledgeBaseDocumentService,
        KnowledgeBaseDocument,
        KnowledgeBaseDocumentPut,
        KnowledgeBaseDocumentPatch,
        KnowledgeBaseDocumentContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeBaseDocumentService, Depends()]) -> None:
        super().__init__(service)


class DeleteKnowledgeBaseDocumentUseCase(BaseUseCase):
    def __init__(
        self,
        service: Annotated[KnowledgeBaseDocumentService, Depends()],
        kb_service: Annotated[KnowledgeBaseService, Depends()],
    ) -> None:
        self.service = service
        self.kb_service = kb_service

    async def execute(self, document_id: UUID, context: KnowledgeBaseDocumentContextKwargs | None = None) -> dict:
        async with AsyncTransaction() as session:
            doc = await self.service.repo.get_by_pk(session, document_id)
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document with ID '{document_id}' not found.",
                )

            kb = await self.kb_service.repo.get_by_pk(session, doc.knowledge_base_id)

            file_md5 = doc.file_md5
            doc_id_str = str(document_id)
            kb_name = kb.name if kb else "unknown"

            # 1. Clean up Vector store points
            if kb and kb.embed_config_hash:
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
                                        match=qmodels.MatchValue(value=doc_id_str),
                                    )
                                ]
                            )
                        ),
                    )
                except Exception as ve:
                    logger.warning(f"Failed to delete points from vector store: {ve}")

            # 2. Clean up S3/MinIO files
            try:
                storage_client = get_storage_client()
                prefix = f"knowledge/{kb_name}/{file_md5}/"
                async for file_path in storage_client.list_files(prefix):
                    await storage_client.delete_file(file_path)
            except Exception as se:
                logger.warning(f"Failed to delete assets from storage: {se}")

            # 3. Delete database record
            success = await self.service.repo.delete_by_pk(session, document_id)
            return {
                "status": "success" if success else "failed",
                "message": "Successfully deleted document and all associated assets.",
            }
