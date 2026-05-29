from typing import ClassVar

from rag_core.adapters.file_storage.interface import FileStorageClient


class FileStorageRegistry:
    """Registry for file storage providers keyed by provider name."""

    _providers: ClassVar[dict[str, type[FileStorageClient]]] = {}

    @classmethod
    def register(cls, provider_name: str, provider_class: type[FileStorageClient]) -> None:
        if provider_name in cls._providers:
            raise ValueError(f"File storage provider is already registered: {provider_name}")

        cls._providers[provider_name] = provider_class

    @classmethod
    def get_provider_class(cls, provider_name: str) -> type[FileStorageClient]:
        try:
            return cls._providers[provider_name]
        except KeyError as exc:
            raise ValueError(f"Unsupported file storage client: {provider_name}") from exc

    @classmethod
    async def create_client(cls, provider: str) -> FileStorageClient:
        provider_class = cls.get_provider_class(provider)
        return await provider_class.from_env()

    @classmethod
    def list_providers(cls) -> list[str]:
        return sorted(cls._providers)
