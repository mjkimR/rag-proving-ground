from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

class FileStorageClient(ABC):
    @classmethod
    @abstractmethod
    async def from_env(cls) -> "FileStorageClient":
        """Create a file storage client from environment configuration."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the file storage client."""
        pass

    @abstractmethod
    async def download_file(self, file_path: str) -> bytes:
        """Downloads a file and returns its content as bytes."""
        pass

    @abstractmethod
    def download_file_stream(self, file_path: str) -> AsyncIterator[bytes]:
        """Downloads a file as a stream of bytes."""
        pass

    @abstractmethod
    async def upload_file(self, file_path: str, data: bytes) -> None:
        """Uploads a file with the given data."""
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> None:
        """Deletes a file at the given path."""
        pass

    @abstractmethod
    def list_files(self, prefix: str) -> AsyncIterator[str]:
        """Lists files matching a given prefix."""
        pass

    @abstractmethod
    async def file_exists(self, file_path: str) -> bool:
        """Checks if a file exists at the given path."""
        pass

    @abstractmethod
    async def get_file_metadata(self, file_path: str) -> dict[str, Any]:
        """Gets metadata for a file at the given path."""
        pass
