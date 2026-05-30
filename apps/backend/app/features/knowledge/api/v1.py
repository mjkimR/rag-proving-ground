from typing import Annotated

from app.features.knowledge.usecases.delete import DeleteKnowledgeDocumentUseCase
from app.features.knowledge.usecases.download import DownloadKnowledgeDocumentUseCase
from app.features.knowledge.usecases.upload import UploadKnowledgeDocumentUseCase
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from rag_core.parsers.schemas import ParsedDocument

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"], dependencies=[])


class KnowledgeDocumentResponse(BaseModel):
    knowledge_name: str
    md5_hash: str
    filename: str
    original_file_path: str
    parsed_data_path: str
    parsed_document: ParsedDocument


class DeleteKnowledgeDocumentResponse(BaseModel):
    status: str
    message: str
    deleted_files: list[str]


@router.post(
    "/{knowledge_name}/upload",
    status_code=status.HTTP_200_OK,
    response_model=KnowledgeDocumentResponse,
)
async def upload_document(
    knowledge_name: str,
    use_case: Annotated[UploadKnowledgeDocumentUseCase, Depends()],
    file: UploadFile = File(...),  # noqa: B008
    provider: str | None = Form(None),
) -> KnowledgeDocumentResponse:
    """Upload a document to a specific knowledge base, parse it, and save the assets in storage."""
    result = await use_case.execute(knowledge_name=knowledge_name, file=file, provider=provider)
    return KnowledgeDocumentResponse(**result)


@router.get(
    "/{knowledge_name}/files/{file_md5}/download",
    status_code=status.HTTP_200_OK,
    response_class=StreamingResponse,
)
async def download_document(
    knowledge_name: str,
    file_md5: str,
    use_case: Annotated[DownloadKnowledgeDocumentUseCase, Depends()],
) -> StreamingResponse:
    """Download the original uploaded document from a specific knowledge base."""
    return await use_case.execute(knowledge_name=knowledge_name, file_md5=file_md5)


@router.delete(
    "/{knowledge_name}/files/{file_md5}",
    status_code=status.HTTP_200_OK,
    response_model=DeleteKnowledgeDocumentResponse,
)
async def delete_document(
    knowledge_name: str,
    file_md5: str,
    use_case: Annotated[DeleteKnowledgeDocumentUseCase, Depends()],
) -> DeleteKnowledgeDocumentResponse:
    """Delete all document assets (original file and parsed JSON) from a specific knowledge base."""
    result = await use_case.execute(knowledge_name=knowledge_name, file_md5=file_md5)
    return DeleteKnowledgeDocumentResponse(**result)
