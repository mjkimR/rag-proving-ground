from app_layer_base.base.repos.base import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.storage.session_file_attachments.models import SessionFileAttachment
from app.features.storage.session_file_attachments.schemas import (
    SessionFileAttachmentCreate,
    SessionFileAttachmentPatch,
    SessionFileAttachmentPut,
)


class SessionFileAttachmentRepository(
    BaseRepository[
        SessionFileAttachment,
        SessionFileAttachmentCreate,
        SessionFileAttachmentPut,
        SessionFileAttachmentPatch,
    ]
):
    model = SessionFileAttachment

    async def get_by_thread_id(self, session: AsyncSession, thread_id: str) -> list[SessionFileAttachment]:
        stmt = select(self.model).where(self.model.thread_id == thread_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())
