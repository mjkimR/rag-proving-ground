from app.features.storage.file_attachments.models import FileAttachment
from app.features.storage.file_attachments.schemas import (
    FileAttachmentCreate,
    FileAttachmentPatch,
    FileAttachmentPut,
)
from app_layer_base.base.repos.base import BaseRepository


class FileAttachmentRepository(
    BaseRepository[FileAttachment, FileAttachmentCreate, FileAttachmentPut, FileAttachmentPatch]
):
    model = FileAttachment
