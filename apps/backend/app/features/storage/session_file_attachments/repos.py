from app.features.storage.session_file_attachments.models import SessionFileAttachment
from app.features.storage.session_file_attachments.schemas import (
    SessionFileAttachmentCreate,
    SessionFileAttachmentPatch,
    SessionFileAttachmentPut,
)
from app_layer_base.base.repos.base import BaseRepository


class SessionFileAttachmentRepository(
    BaseRepository[
        SessionFileAttachment,
        SessionFileAttachmentCreate,
        SessionFileAttachmentPut,
        SessionFileAttachmentPatch,
    ]
):
    model = SessionFileAttachment
