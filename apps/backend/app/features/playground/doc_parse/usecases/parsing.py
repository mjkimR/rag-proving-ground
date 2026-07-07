import os
from typing import Annotated

from app_layer_base.base.usecases.base import BaseUseCase
from fastapi import Depends, HTTPException, UploadFile, status
from loguru import logger
from rag_core.adapters.parser.instance import parse_file
from rag_core.parsers.schemas import ParsedDocument

from app.features.playground.doc_parse.services import DocumentParseService

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".html", ".htm", ".md", ".docx", ".txt"}


class DocumentParsingUseCase(BaseUseCase):
    def __init__(
        self,
        service: Annotated[DocumentParseService, Depends()],
    ) -> None:
        self.service = service

    async def execute(
        self,
        file: UploadFile,
        provider: str | None = None,
        ignore_cache: bool = False,
    ) -> ParsedDocument:
        """Validate, sanitize, and parse an uploaded file using rag-core."""
        # 1. Sanitize filename to prevent directory traversal
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file must have a filename.",
            )
        filename = os.path.basename(file.filename)

        # 2. Validate file extension
        _, ext = os.path.splitext(filename.lower())
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: '{ext}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        # 3. Read content with size enforcement
        content = await file.read(MAX_FILE_SIZE + 1)
        if len(content) > MAX_FILE_SIZE:
            logger.warning(f"File upload blocked: {filename} exceeded size limit of 10MB.")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded file size exceeds the 10MB limit.",
            )

        logger.info(
            f"Parsing uploaded file '{filename}' ({len(content)} bytes) using provider: {provider or 'default'} (ignore_cache: {ignore_cache})"
        )

        try:
            parsed_doc = await parse_file(
                content=content,
                filename=filename,
                content_type=file.content_type,
                provider=provider,
                ignore_cache=ignore_cache,
            )
            logger.info(f"Successfully parsed '{filename}'. Generated doc_id: {parsed_doc.doc_id}")
            return parsed_doc
        except Exception as e:
            logger.exception(f"Failed to parse uploaded file '{filename}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document parsing failed: {e}",
            ) from e
