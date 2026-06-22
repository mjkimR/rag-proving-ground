from typing import Annotated

from app.features.storage.session_file_attachments.models import SessionFileAttachment
from app.features.storage.session_file_attachments.schemas import (
    SessionFileAttachmentCreate,
    SessionFileAttachmentPatch,
    SessionFileAttachmentPut,
)
from app.features.storage.session_file_attachments.services import (
    SessionFileAttachmentContextKwargs,
    SessionFileAttachmentService,
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


class GetSessionFileAttachmentUseCase(
    BaseGetUseCase[SessionFileAttachmentService, SessionFileAttachment, SessionFileAttachmentContextKwargs]
):
    def __init__(self, service: Annotated[SessionFileAttachmentService, Depends()]) -> None:
        super().__init__(service)


class GetMultiSessionFileAttachmentUseCase(
    BaseGetMultiUseCase[SessionFileAttachmentService, SessionFileAttachment, SessionFileAttachmentContextKwargs]
):
    def __init__(self, service: Annotated[SessionFileAttachmentService, Depends()]) -> None:
        super().__init__(service)


class CreateSessionFileAttachmentUseCase(
    BaseCreateUseCase[
        SessionFileAttachmentService,
        SessionFileAttachment,
        SessionFileAttachmentCreate,
        SessionFileAttachmentContextKwargs,
    ]
):
    def __init__(self, service: Annotated[SessionFileAttachmentService, Depends()]) -> None:
        super().__init__(service)


class PatchSessionFileAttachmentUseCase(
    BasePatchUseCase[
        SessionFileAttachmentService,
        SessionFileAttachment,
        SessionFileAttachmentPut,
        SessionFileAttachmentPatch,
        SessionFileAttachmentContextKwargs,
    ]
):
    def __init__(self, service: Annotated[SessionFileAttachmentService, Depends()]) -> None:
        super().__init__(service)


class PutSessionFileAttachmentUseCase(
    BasePutUseCase[
        SessionFileAttachmentService,
        SessionFileAttachment,
        SessionFileAttachmentPut,
        SessionFileAttachmentPatch,
        SessionFileAttachmentContextKwargs,
    ]
):
    def __init__(self, service: Annotated[SessionFileAttachmentService, Depends()]) -> None:
        super().__init__(service)


class DeleteSessionFileAttachmentUseCase(
    BaseDeleteUseCase[SessionFileAttachmentService, SessionFileAttachment, SessionFileAttachmentContextKwargs]
):
    def __init__(self, service: Annotated[SessionFileAttachmentService, Depends()]) -> None:
        super().__init__(service)
