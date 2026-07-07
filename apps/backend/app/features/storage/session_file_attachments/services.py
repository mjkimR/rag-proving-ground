from typing import Annotated

from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from fastapi import Depends

from app.features.storage.session_file_attachments.models import SessionFileAttachment
from app.features.storage.session_file_attachments.repos import SessionFileAttachmentRepository
from app.features.storage.session_file_attachments.schemas import (
    SessionFileAttachmentCreate,
    SessionFileAttachmentPatch,
    SessionFileAttachmentPut,
)


class SessionFileAttachmentContextKwargs(BaseContextKwargs):
    pass


class SessionFileAttachmentService(
    BaseCreateServiceMixin[
        SessionFileAttachmentRepository,
        SessionFileAttachment,
        SessionFileAttachmentCreate,
        SessionFileAttachmentContextKwargs,
    ],
    BaseGetMultiServiceMixin[
        SessionFileAttachmentRepository, SessionFileAttachment, SessionFileAttachmentContextKwargs
    ],
    BaseGetServiceMixin[SessionFileAttachmentRepository, SessionFileAttachment, SessionFileAttachmentContextKwargs],
    BaseUpdateServiceMixin[
        SessionFileAttachmentRepository,
        SessionFileAttachment,
        SessionFileAttachmentPut,
        SessionFileAttachmentPatch,
        SessionFileAttachmentContextKwargs,
    ],
    BaseDeleteServiceMixin[SessionFileAttachmentRepository, SessionFileAttachment, SessionFileAttachmentContextKwargs],
):
    def __init__(self, repo: Annotated[SessionFileAttachmentRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> SessionFileAttachmentRepository:
        return self._repo

    @property
    def context_model(self):
        return SessionFileAttachmentContextKwargs
