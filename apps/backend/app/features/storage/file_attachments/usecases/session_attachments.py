from typing import Annotated

from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends

from app.features.storage.session_file_attachments.schemas import SessionFileAttachmentRead
from app.features.storage.session_file_attachments.services import SessionFileAttachmentService


class GetSessionAttachmentsUseCase(BaseUseCase):
    def __init__(
        self,
        session_file_service: Annotated[SessionFileAttachmentService, Depends()],
    ) -> None:
        self.session_file_service = session_file_service

    async def execute(self, thread_id: str) -> list[SessionFileAttachmentRead]:
        async with AsyncTransaction() as session:
            db_attachments = await self.session_file_service.repo.get_by_thread_id(session, thread_id)
            return [SessionFileAttachmentRead.model_validate(att) for att in db_attachments]
