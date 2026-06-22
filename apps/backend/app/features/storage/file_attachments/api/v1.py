from typing import Annotated
from uuid import UUID

from app.features.storage.file_attachments.schemas import (
    FileAttachmentCreate,
    FileAttachmentPatch,
    FileAttachmentPut,
    FileAttachmentRead,
)
from app.features.storage.file_attachments.usecases.bind import BindFileToSessionUseCase
from app.features.storage.file_attachments.usecases.crud import (
    CreateFileAttachmentUseCase,
    DeleteFileAttachmentUseCase,
    GetFileAttachmentUseCase,
    GetMultiFileAttachmentUseCase,
    PatchFileAttachmentUseCase,
    PutFileAttachmentUseCase,
)
from app.features.storage.file_attachments.usecases.upload import UploadFileAttachmentUseCase
from app.features.storage.session_file_attachments.schemas import (
    SessionFileAttachmentCreate,
    SessionFileAttachmentPatch,
    SessionFileAttachmentPut,
    SessionFileAttachmentRead,
)
from app.features.storage.session_file_attachments.usecases.crud import (
    CreateSessionFileAttachmentUseCase,
    DeleteSessionFileAttachmentUseCase,
    GetMultiSessionFileAttachmentUseCase,
    GetSessionFileAttachmentUseCase,
    PatchSessionFileAttachmentUseCase,
    PutSessionFileAttachmentUseCase,
)
from app_layer_base.base.deps.params.page import PaginationParam
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, File, UploadFile, status

router = APIRouter(tags=["FileAttachment"], dependencies=[])


# Phase 1: Upload raw file
@router.post(
    "/file_attachments/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=FileAttachmentRead,
)
async def upload_file_attachment(
    use_case: Annotated[UploadFileAttachmentUseCase, Depends()],
    file: UploadFile = File(...),  # noqa: B008
):
    """Phase 1: Upload raw file, check for deduplication, and return metadata."""
    return await use_case.execute(file)


# Phase 2: Bind to session
@router.post(
    "/sessions/{thread_id}/files",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SessionFileAttachmentRead,
)
async def bind_file_to_session(
    thread_id: str,
    binding_in: SessionFileAttachmentCreate,
    use_case: Annotated[BindFileToSessionUseCase, Depends()],
):
    """Phase 2: Bind file to session and trigger async pipeline processing."""
    return await use_case.execute(thread_id, binding_in)


# FileAttachment CRUD
@router.post(
    "/file_attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=FileAttachmentRead,
)
async def create_file_attachment(
    use_case: Annotated[CreateFileAttachmentUseCase, Depends()],
    file_attachment_in: FileAttachmentCreate,
):
    return await use_case.execute(file_attachment_in)


@router.get("/file_attachments", response_model=PaginatedList[FileAttachmentRead])
async def get_file_attachments(
    use_case: Annotated[GetMultiFileAttachmentUseCase, Depends()],
    pagination: PaginationParam,
):
    query_options = ListQueryOptions(offset=pagination.offset, limit=pagination.limit)
    return await use_case.execute(query_options=query_options)


@router.get("/file_attachments/{file_attachment_id}", response_model=FileAttachmentRead)
async def get_file_attachment(
    use_case: Annotated[GetFileAttachmentUseCase, Depends()],
    file_attachment_id: UUID,
):
    file_attachment = await use_case.execute(file_attachment_id)
    if not file_attachment:
        raise NotFoundException()
    return file_attachment


@router.patch("/file_attachments/{file_attachment_id}", response_model=FileAttachmentRead)
async def patch_file_attachment(
    use_case: Annotated[PatchFileAttachmentUseCase, Depends()],
    file_attachment_id: UUID,
    file_attachment_in: FileAttachmentPatch,
):
    file_attachment = await use_case.execute(file_attachment_id, file_attachment_in)
    if not file_attachment:
        raise NotFoundException()
    return file_attachment


@router.put("/file_attachments/{file_attachment_id}", response_model=FileAttachmentRead)
async def put_file_attachment(
    use_case: Annotated[PutFileAttachmentUseCase, Depends()],
    file_attachment_id: UUID,
    file_attachment_in: FileAttachmentPut,
):
    file_attachment = await use_case.execute(file_attachment_id, file_attachment_in)
    if not file_attachment:
        raise NotFoundException()
    return file_attachment


@router.delete("/file_attachments/{file_attachment_id}", response_model=DeleteResponse)
async def delete_file_attachment(
    use_case: Annotated[DeleteFileAttachmentUseCase, Depends()],
    file_attachment_id: UUID,
):
    return await use_case.execute(file_attachment_id)


# SessionFileAttachment CRUD
@router.post(
    "/session_file_attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionFileAttachmentRead,
)
async def create_session_file_attachment(
    use_case: Annotated[CreateSessionFileAttachmentUseCase, Depends()],
    session_file_attachment_in: SessionFileAttachmentCreate,
):
    return await use_case.execute(session_file_attachment_in)


@router.get(
    "/session_file_attachments",
    response_model=PaginatedList[SessionFileAttachmentRead],
)
async def get_session_file_attachments(
    use_case: Annotated[GetMultiSessionFileAttachmentUseCase, Depends()],
    pagination: PaginationParam,
):
    query_options = ListQueryOptions(offset=pagination.offset, limit=pagination.limit)
    return await use_case.execute(query_options=query_options)


@router.get(
    "/session_file_attachments/{session_file_attachment_id}",
    response_model=SessionFileAttachmentRead,
)
async def get_session_file_attachment(
    use_case: Annotated[GetSessionFileAttachmentUseCase, Depends()],
    session_file_attachment_id: UUID,
):
    session_file_attachment = await use_case.execute(session_file_attachment_id)
    if not session_file_attachment:
        raise NotFoundException()
    return session_file_attachment


@router.patch(
    "/session_file_attachments/{session_file_attachment_id}",
    response_model=SessionFileAttachmentRead,
)
async def patch_session_file_attachment(
    use_case: Annotated[PatchSessionFileAttachmentUseCase, Depends()],
    session_file_attachment_id: UUID,
    session_file_attachment_in: SessionFileAttachmentPatch,
):
    session_file_attachment = await use_case.execute(session_file_attachment_id, session_file_attachment_in)
    if not session_file_attachment:
        raise NotFoundException()
    return session_file_attachment


@router.put(
    "/session_file_attachments/{session_file_attachment_id}",
    response_model=SessionFileAttachmentRead,
)
async def put_session_file_attachment(
    use_case: Annotated[PutSessionFileAttachmentUseCase, Depends()],
    session_file_attachment_id: UUID,
    session_file_attachment_in: SessionFileAttachmentPut,
):
    session_file_attachment = await use_case.execute(session_file_attachment_id, session_file_attachment_in)
    if not session_file_attachment:
        raise NotFoundException()
    return session_file_attachment


@router.delete(
    "/session_file_attachments/{session_file_attachment_id}",
    response_model=DeleteResponse,
)
async def delete_session_file_attachment(
    use_case: Annotated[DeleteSessionFileAttachmentUseCase, Depends()],
    session_file_attachment_id: UUID,
):
    return await use_case.execute(session_file_attachment_id)
