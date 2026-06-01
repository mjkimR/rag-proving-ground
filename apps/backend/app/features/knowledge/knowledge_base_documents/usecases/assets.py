import json
import urllib.parse
from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app_file_storage import get_storage_client
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends
from fastapi.responses import StreamingResponse
from rag_core.parsers import ParsedDocument


class DownloadKnowledgeBaseDocumentUseCase(BaseUseCase):
    def __init__(self, doc_service: Annotated[KnowledgeBaseDocumentService, Depends()]) -> None:
        self.doc_service = doc_service

    async def execute(self, document_id: UUID) -> StreamingResponse:
        async with AsyncTransaction() as session:
            doc = await self.doc_service.repo.get_by_pk(session, document_id)
            if not doc or not doc.document_info:
                raise NotFoundException("Document not found or has no storage info.")
            original_file_key = doc.document_info.get("original_file_path")
            filename = doc.document_info.get("filename")

        if not original_file_key:
            raise NotFoundException("Original file storage key is missing.")

        encoded_filename = urllib.parse.quote(filename or "file")
        storage_client = get_storage_client()

        async def file_streamer():
            async for chunk in storage_client.download_file_stream(original_file_key):
                yield chunk

        return StreamingResponse(
            file_streamer(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}"},
        )


class GetParsedKnowledgeBaseDocumentUseCase(BaseUseCase):
    def __init__(self, doc_service: Annotated[KnowledgeBaseDocumentService, Depends()]) -> None:
        self.doc_service = doc_service

    async def execute(self, document_id: UUID) -> ParsedDocument:
        async with AsyncTransaction() as session:
            doc = await self.doc_service.repo.get_by_pk(session, document_id)
            if not doc or not doc.document_info:
                raise NotFoundException("Document not found or has no storage info.")
            parsed_data_path = doc.document_info.get("parsed_data_path")

        if not parsed_data_path:
            raise NotFoundException("Parsed data storage key is missing.")

        storage_client = get_storage_client()
        if not await storage_client.file_exists(parsed_data_path):
            raise NotFoundException("Parsed document data not found in storage.")

        data = await storage_client.download_file(parsed_data_path)
        return ParsedDocument(**json.loads(data.decode("utf-8")))
