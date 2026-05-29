from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, BinaryIO, ClassVar


@dataclass(frozen=True)
class ParserInput:
    """Input accepted by document parser providers."""

    source: str | None = None
    content: bytes | None = None
    filename: str | None = None
    content_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(
        cls,
        file: BinaryIO,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ParserInput":
        """Create parser input from a sync binary file object."""
        return cls(
            content=file.read(),
            filename=filename or _file_name(file),
            content_type=content_type,
            metadata=metadata or {},
        )

    @classmethod
    async def from_upload_file(
        cls,
        upload_file: Any,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ParserInput":
        """Create parser input from FastAPI/Starlette UploadFile."""
        return cls(
            content=await upload_file.read(),
            filename=filename or getattr(upload_file, "filename", None),
            content_type=content_type or getattr(upload_file, "content_type", None),
            metadata=metadata or {},
        )


def _file_name(file: BinaryIO) -> str | None:
    name = getattr(file, "name", None)
    if isinstance(name, str):
        return name
    return None


class Parser(ABC):
    """Base interface for document parser engines such as Docling or Azure."""

    name: ClassVar[str]
    schema_version: ClassVar[str] = "raw"

    @classmethod
    @abstractmethod
    def from_config(cls) -> "Parser":
        """Create a parser provider from configuration."""
        pass

    @abstractmethod
    async def parse(self, parser_input: ParserInput) -> Any:
        """Parse a document with the provider."""
        pass

    def to_cache_data(self, result: Any) -> dict[str, Any]:
        """Convert provider result to JSON-serializable cache data."""
        if isinstance(result, dict):
            return self._to_jsonable(result)
        if hasattr(result, "model_dump"):
            return result.model_dump(mode="json")
        raise TypeError(f"{self.name} parser result is not cacheable: {type(result)!r}")

    def from_cache_data(self, data: dict[str, Any]) -> Any:
        """Restore provider result from cached JSON data."""
        return data

    def _to_jsonable(self, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {key: self._to_jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._to_jsonable(item) for item in value]
        if isinstance(value, tuple):
            return [self._to_jsonable(item) for item in value]
        return value
