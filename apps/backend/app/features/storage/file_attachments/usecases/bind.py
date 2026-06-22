from typing import Annotated, Any

from app.features.storage.file_attachments.services import FileAttachmentService
from app.features.storage.session_file_attachments.schemas import (
    SessionFileAttachmentCreate,
)
from app.features.storage.session_file_attachments.services import (
    SessionFileAttachmentService,
)
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from loguru import logger


def detect_purpose(mime_type: str) -> str:
    mime_type = mime_type.lower()
    if mime_type.startswith("image/"):
        return "vision"
    elif mime_type.startswith("audio/"):
        return "audio"
    elif (
        mime_type.startswith("text/")
        or "pdf" in mime_type
        or "word" in mime_type
        or "document" in mime_type
        or "html" in mime_type
    ):
        return "temp_kb"
    return "context"


class BindFileToSessionUseCase(BaseUseCase):
    def __init__(
        self,
        file_service: Annotated[FileAttachmentService, Depends()],
        session_file_service: Annotated[SessionFileAttachmentService, Depends()],
    ):
        self.file_service = file_service
        self.session_file_service = session_file_service

    async def execute(self, thread_id: str, binding_in: SessionFileAttachmentCreate) -> Any:
        async with AsyncTransaction() as session:
            # 1. Fetch the FileAttachment
            file_attachment = await self.file_service.repo.get_by_pk(session, binding_in.file_attachment_id)
            if not file_attachment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"FileAttachment with ID '{binding_in.file_attachment_id}' not found.",
                )

            # 2. Detect purpose if omitted
            purpose = binding_in.purpose
            if not purpose:
                purpose = detect_purpose(file_attachment.mime_type)

            # 3. Check for existing binding
            existing_bindings = await self.session_file_service.repo.get_all(
                session,
                where=(
                    self.session_file_service.repo.model.thread_id == thread_id,
                    self.session_file_service.repo.model.file_attachment_id == binding_in.file_attachment_id,
                ),
            )

            if existing_bindings:
                session_file = existing_bindings[0]
                if session_file.status != "FAILED":
                    logger.info(
                        f"File attachment {binding_in.file_attachment_id} already bound to thread {thread_id} with status {session_file.status}. Fast path return."
                    )
                    return session_file
                else:
                    # Retry flow for FAILED bindings
                    logger.info(f"Retrying failed session file attachment {session_file.id}")
                    session_file.status = "PENDING"
                    session_file.error_message = None
                    session_file.task_id = None
                    session_file.purpose = purpose
            else:
                # Create a new SessionFileAttachment mapping
                new_binding_data = SessionFileAttachmentCreate(
                    thread_id=thread_id,
                    file_attachment_id=binding_in.file_attachment_id,
                    purpose=purpose,
                    status="PENDING",
                )
                session_file = await self.session_file_service.create(session, new_binding_data)

            await session.flush()
            session_file_id = session_file.id

        # 4. Trigger the Taskiq worker task (outside transaction to avoid lock contention)
        try:
            from app.worker.handlers.attachment import process_file_attachment

            logger.info(f"Dispatching process task for SessionFileAttachment {session_file_id}")
            task = await process_file_attachment.kiq(session_file_attachment_id=session_file_id)
            task_id = task.task_id
        except Exception as exc:
            logger.error(f"Failed to dispatch Taskiq task for SessionFileAttachment {session_file_id}: {exc}")
            async with AsyncTransaction() as session:
                await self.session_file_service.repo.update_by_pk(
                    session,
                    session_file_id,
                    {"status": "FAILED", "error_message": f"Taskiq dispatch failed: {exc}"},
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to queue processing task: {exc}",
            ) from exc

        # 5. Update task_id in DB
        async with AsyncTransaction() as session:
            updated_session_file = await self.session_file_service.repo.update_by_pk(
                session,
                session_file_id,
                {"task_id": task_id},
            )
            return updated_session_file
