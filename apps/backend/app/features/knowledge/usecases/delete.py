from app_file_storage import get_storage_client
from app_layer_base.base.usecases.base import BaseUseCase
from fastapi import HTTPException, status
from loguru import logger


class DeleteKnowledgeDocumentUseCase(BaseUseCase):
    async def execute(self, knowledge_name: str, file_md5: str) -> dict:
        """Find and delete all documents/assets under knowledge/{knowledge_name}/{file_md5}/."""
        storage_client = get_storage_client()
        prefix = f"knowledge/{knowledge_name}/{file_md5}/"

        deleted_files = []
        try:
            async for file_path in storage_client.list_files(prefix):
                await storage_client.delete_file(file_path)
                deleted_files.append(file_path)
        except Exception as e:
            logger.exception(f"Failed to delete files under prefix '{prefix}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete files from storage: {e}",
            ) from e

        if not deleted_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No assets found for knowledge base '{knowledge_name}' with MD5 '{file_md5}'.",
            )

        logger.info(
            f"Successfully deleted all {len(deleted_files)} assets from knowledge base '{knowledge_name}' under prefix '{prefix}'."
        )
        return {
            "status": "success",
            "message": f"Successfully deleted document and its parsing assets from knowledge '{knowledge_name}'.",
            "deleted_files": deleted_files,
        }
