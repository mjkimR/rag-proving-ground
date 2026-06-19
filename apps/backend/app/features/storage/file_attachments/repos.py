from app.features.storage.file_attachments.models import FileAttachment, SessionFileAttachment
from app.features.storage.file_attachments.schemas import (
    FileAttachmentCreate,
    FileAttachmentPatch,
    FileAttachmentPut,
    SessionFileAttachmentCreate,
    SessionFileAttachmentPatch,
    SessionFileAttachmentPut,
)
from app_layer_base.base.repos.base import BaseRepository


class FileAttachmentRepository(
    BaseRepository[FileAttachment, FileAttachmentCreate, FileAttachmentPut, FileAttachmentPatch]
):
    model = FileAttachment


class SessionFileAttachmentRepository(
    BaseRepository[
        SessionFileAttachment,
        SessionFileAttachmentCreate,
        SessionFileAttachmentPut,
        SessionFileAttachmentPatch,
    ]
):
    model = SessionFileAttachment
