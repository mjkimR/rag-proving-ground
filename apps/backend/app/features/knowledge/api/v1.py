from typing import Annotated

from app.features.knowledge.usecases.delete import DeleteKnowledgeDocumentUseCase
from app.features.knowledge.usecases.download import DownloadKnowledgeDocumentUseCase
from app.features.knowledge.usecases.list_bases import ListKnowledgeBasesUseCase
from app.features.knowledge.usecases.list_files import ListKnowledgeFilesUseCase
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


class KnowledgeFileEntry(BaseModel):
    md5_hash: str
    filename: str
    original_file_path: str
    parsed_data_path: str
    element_count: int
    size_bytes: int


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=list[str],
)
async def list_knowledge_bases(
    use_case: Annotated[ListKnowledgeBasesUseCase, Depends()],
) -> list[str]:
    """List all unique active knowledge base names from S3/MinIO storage."""
    return await use_case.execute()


@router.get(
    "/{knowledge_name}/files",
    status_code=status.HTTP_200_OK,
    response_model=list[KnowledgeFileEntry],
)
async def list_knowledge_files(
    knowledge_name: str,
    use_case: Annotated[ListKnowledgeFilesUseCase, Depends()],
) -> list[KnowledgeFileEntry]:
    """List all uploaded document assets and parsed element counts inside a knowledge base."""
    result = await use_case.execute(knowledge_name=knowledge_name)
    return [KnowledgeFileEntry(**item) for item in result]


@router.get(
    "/{knowledge_name}/files/{file_md5}/parsed",
    status_code=status.HTTP_200_OK,
    response_model=ParsedDocument,
)
async def get_parsed_document(
    knowledge_name: str,
    file_md5: str,
) -> ParsedDocument:
    """Get the parsed elements document structure (parsed_data.json) for a document."""
    import json

    from app_file_storage import get_storage_client
    from fastapi import HTTPException

    storage_client = get_storage_client()
    key = f"knowledge/{knowledge_name}/{file_md5}/parsed_data.json"
    if not await storage_client.file_exists(key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parsed document data not found.",
        )
    data = await storage_client.download_file(key)
    return ParsedDocument(**json.loads(data.decode("utf-8")))


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
