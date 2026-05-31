from typing import Annotated

from app.features.doc_parse.usecases.parsing import DocumentParsingUseCase
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from rag_core.parsers.schemas import ParsedDocument

router = APIRouter(prefix="/doc_parse", tags=["Document Parse"], dependencies=[])


@router.post("/parse", status_code=status.HTTP_200_OK, response_model=ParsedDocument)
async def document_parse(
    use_case: Annotated[DocumentParsingUseCase, Depends()],
    file: UploadFile = File(...),  # noqa: B008
    provider: str | None = Form(None),
    ignore_cache: bool = Form(False),
) -> ParsedDocument:
    """Parse an uploaded document using the specified or default parser engine."""
    return await use_case.execute(file=file, provider=provider, ignore_cache=ignore_cache)
