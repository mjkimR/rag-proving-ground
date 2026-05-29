from typing import Annotated

from fastapi.params import Depends

from rag_core.adapters.file_storage.config import FileProviderType, FileStorageSettings, get_file_storage_settings
from rag_core.adapters.file_storage.interface import FileStorageClient
from rag_core.adapters.file_storage.providers import register_default_providers
from rag_core.adapters.file_storage.registry import FileStorageRegistry


class FileStorageFactory:
    @classmethod
    async def create_client(
        cls, config: Annotated[FileStorageSettings, Depends(get_file_storage_settings)]
    ) -> FileStorageClient:
        if config.provider == FileProviderType.NONE:
            raise ValueError("File storage provider is set to 'none' but a client was requested.")

        register_default_providers()
        return await FileStorageRegistry.create_client(config.provider)
