from typing import Annotated

from app.features.storage.file_attachments.models import FileAttachment, SessionFileAttachment
from app.features.storage.file_attachments.repos import FileAttachmentRepository, SessionFileAttachmentRepository
from app.features.storage.file_attachments.schemas import (
    FileAttachmentCreate,
    FileAttachmentPatch,
    FileAttachmentPut,
    SessionFileAttachmentCreate,
    SessionFileAttachmentPatch,
    SessionFileAttachmentPut,
)
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from fastapi import Depends


class FileAttachmentContextKwargs(BaseContextKwargs):
    pass


class FileAttachmentService(
    BaseCreateServiceMixin[FileAttachmentRepository, FileAttachment, FileAttachmentCreate, FileAttachmentContextKwargs],
    BaseGetMultiServiceMixin[FileAttachmentRepository, FileAttachment, FileAttachmentContextKwargs],
    BaseGetServiceMixin[FileAttachmentRepository, FileAttachment, FileAttachmentContextKwargs],
    BaseUpdateServiceMixin[
        FileAttachmentRepository, FileAttachment, FileAttachmentPut, FileAttachmentPatch, FileAttachmentContextKwargs
    ],
    BaseDeleteServiceMixin[FileAttachmentRepository, FileAttachment, FileAttachmentContextKwargs],
):
    def __init__(self, repo: Annotated[FileAttachmentRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> FileAttachmentRepository:
        return self._repo

    @property
    def context_model(self):
        return FileAttachmentContextKwargs


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
