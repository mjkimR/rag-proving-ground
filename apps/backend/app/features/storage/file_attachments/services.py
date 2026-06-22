from typing import Annotated

from app.features.storage.file_attachments.models import FileAttachment
from app.features.storage.file_attachments.repos import FileAttachmentRepository
from app.features.storage.file_attachments.schemas import (
    FileAttachmentCreate,
    FileAttachmentPatch,
    FileAttachmentPut,
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
