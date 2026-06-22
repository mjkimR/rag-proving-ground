from typing import Annotated

from app.features.storage.file_attachments.models import FileAttachment
from app.features.storage.file_attachments.schemas import (
    FileAttachmentCreate,
    FileAttachmentPatch,
    FileAttachmentPut,
)
from app.features.storage.file_attachments.services import (
    FileAttachmentContextKwargs,
    FileAttachmentService,
)
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from fastapi import Depends


class GetFileAttachmentUseCase(BaseGetUseCase[FileAttachmentService, FileAttachment, FileAttachmentContextKwargs]):
    def __init__(self, service: Annotated[FileAttachmentService, Depends()]) -> None:
        super().__init__(service)


class GetMultiFileAttachmentUseCase(
    BaseGetMultiUseCase[FileAttachmentService, FileAttachment, FileAttachmentContextKwargs]
):
    def __init__(self, service: Annotated[FileAttachmentService, Depends()]) -> None:
        super().__init__(service)


class CreateFileAttachmentUseCase(
    BaseCreateUseCase[FileAttachmentService, FileAttachment, FileAttachmentCreate, FileAttachmentContextKwargs]
):
    def __init__(self, service: Annotated[FileAttachmentService, Depends()]) -> None:
        super().__init__(service)


class PatchFileAttachmentUseCase(
    BasePatchUseCase[
        FileAttachmentService, FileAttachment, FileAttachmentPut, FileAttachmentPatch, FileAttachmentContextKwargs
    ]
):
    def __init__(self, service: Annotated[FileAttachmentService, Depends()]) -> None:
        super().__init__(service)


class PutFileAttachmentUseCase(
    BasePutUseCase[
        FileAttachmentService, FileAttachment, FileAttachmentPut, FileAttachmentPatch, FileAttachmentContextKwargs
    ]
):
    def __init__(self, service: Annotated[FileAttachmentService, Depends()]) -> None:
        super().__init__(service)


class DeleteFileAttachmentUseCase(
    BaseDeleteUseCase[FileAttachmentService, FileAttachment, FileAttachmentContextKwargs]
):
    def __init__(self, service: Annotated[FileAttachmentService, Depends()]) -> None:
        super().__init__(service)
