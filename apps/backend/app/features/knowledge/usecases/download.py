import os

from app_file_storage import get_storage_client
from app_layer_base.base.usecases.base import BaseUseCase
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from loguru import logger


class DownloadKnowledgeDocumentUseCase(BaseUseCase):
    async def execute(self, knowledge_name: str, file_md5: str) -> StreamingResponse:
        """Find the original document under knowledge/{knowledge_name}/{file_md5}/ and stream it."""
        storage_client = get_storage_client()
        prefix = f"knowledge/{knowledge_name}/{file_md5}/"

        original_file_key = None
        try:
            async for file_path in storage_client.list_files(prefix):
                if not file_path.endswith("parsed_data.json"):
                    original_file_key = file_path
                    break
        except Exception as e:
            logger.exception(f"Failed to list files under prefix '{prefix}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to query storage: {e}",
            ) from e

        if not original_file_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Original file not found under knowledge base '{knowledge_name}' with MD5 '{file_md5}'.",
            )

        filename = os.path.basename(original_file_key)

        try:

            async def file_streamer():
                async for chunk in storage_client.download_file_stream(original_file_key):
                    yield chunk

            return StreamingResponse(
                file_streamer(),
                media_type="application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as e:
            logger.exception(f"Failed to download file '{original_file_key}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to stream file from storage: {e}",
            ) from e
