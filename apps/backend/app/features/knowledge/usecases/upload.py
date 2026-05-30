import hashlib
import os

from app_file_storage import get_storage_client
from app_layer_base.base.usecases.base import BaseUseCase
from fastapi import HTTPException, UploadFile, status
from loguru import logger
from rag_core.adapters.parser.instance import parse_file
from rag_core.parsers.schemas import ParsedDocument

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".html", ".htm", ".md", ".docx", ".txt"}


class UploadKnowledgeDocumentUseCase(BaseUseCase):
    async def execute(self, knowledge_name: str, file: UploadFile, provider: str | None = None) -> dict:
        """Validate, parse using rag-core, and save original file & parsed JSON to storage under knowledge/{knowledge_name}/{file_md5}/."""
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

        # 4. Calculate MD5 hash
        md5_hash = hashlib.md5(content).hexdigest()

        # 5. Parse file (leverages the global cache under parser_cache/ automatically)
        logger.info(
            f"Parsing uploaded file '{filename}' ({len(content)} bytes) for knowledge base '{knowledge_name}' using provider: {provider or 'default'}"
        )
        try:
            parsed_doc: ParsedDocument = await parse_file(
                content=content,
                filename=filename,
                content_type=file.content_type,
                provider=provider,
            )
        except Exception as e:
            logger.exception(f"Failed to parse file '{filename}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document parsing failed: {e}",
            ) from e

        # 6. Save original file and parsed JSON under knowledge/{knowledge_name}/{file_md5}/
        storage_client = get_storage_client()

        # Paths
        base_path = f"knowledge/{knowledge_name}/{md5_hash}"
        original_file_key = f"{base_path}/{filename}"
        parsed_data_key = f"{base_path}/parsed_data.json"

        try:
            # Save original file
            await storage_client.upload_file(original_file_key, content)

            # Save parsed JSON (ParsedDocument model_dump_json)
            parsed_json_bytes = parsed_doc.model_dump_json(indent=2).encode("utf-8")
            await storage_client.upload_file(parsed_data_key, parsed_json_bytes)

            logger.info(
                f"Successfully uploaded and stored document '{filename}' in knowledge base '{knowledge_name}'. MD5: {md5_hash}"
            )
        except Exception as e:
            logger.exception(f"Failed to store documents in S3: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save document assets to storage: {e}",
            ) from e

        return {
            "knowledge_name": knowledge_name,
            "md5_hash": md5_hash,
            "filename": filename,
            "original_file_path": original_file_key,
            "parsed_data_path": parsed_data_key,
            "parsed_document": parsed_doc,
        }
