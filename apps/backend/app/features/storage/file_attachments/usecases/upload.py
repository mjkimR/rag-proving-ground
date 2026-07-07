import hashlib
import os
from typing import Annotated, Any

from app_file_storage import get_storage_client
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, UploadFile, status
from loguru import logger

from app.features.storage.file_attachments.schemas import FileAttachmentCreate
from app.features.storage.file_attachments.services import FileAttachmentService

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def file_content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class UploadFileAttachmentUseCase(BaseUseCase):
    def __init__(self, service: Annotated[FileAttachmentService, Depends()]):
        self.service = service

    async def execute(self, file: UploadFile) -> Any:
        # Resolve Any type import or just return the object
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file must have a filename.",
            )
        filename = os.path.basename(file.filename)

        content = await file.read(MAX_FILE_SIZE + 1)
        if len(content) > MAX_FILE_SIZE:
            logger.warning(f"Attachment upload blocked: {filename} exceeded size limit of 10MB.")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded file size exceeds the 10MB limit.",
            )

        sha256 = file_content_hash(content)
        mime_type = file.content_type or "application/octet-stream"
        size_bytes = len(content)
        storage_path = f"raw-attachments/{sha256}"

        async with AsyncTransaction() as session:
            # Check for global deduplication
            existing = await self.service.repo.get_all(
                session,
                where=(self.service.repo.model.sha256 == sha256,),
            )
            if existing:
                logger.info(f"File attachment with hash {sha256} already exists. Reusing.")
                return existing[0]

            # Create new record in DB
            create_in = FileAttachmentCreate(
                sha256=sha256,
                filename=filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
                storage_path=storage_path,
            )
            new_file = await self.service.create(session, create_in)

        # Upload raw file content to MinIO
        storage_client = get_storage_client()
        try:
            logger.info(f"Uploading file '{filename}' (hash: {sha256}) to MinIO path '{storage_path}'")
            await storage_client.upload_file(storage_path, content)
        except Exception as exc:
            logger.error(f"Failed to upload file attachment to storage: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file to storage: {exc}",
            ) from exc

        return new_file
