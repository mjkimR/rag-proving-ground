from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, BinaryIO, ClassVar


@dataclass(frozen=True)
class ParserInput:
    """Represents the input document and metadata sent to document parser providers.

    Attributes:
        source: The URI or file path of the source document, if parsed directly.
        content: The raw binary bytes of the document.
        filename: The filename of the document.
        content_type: The MIME type of the document.
        metadata: Additional metadata key-value pairs associated with the document.
    """

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
        """Creates a ParserInput instance from a synchronous binary file object.

        Args:
            file: A binary file-like object to read content bytes from.
            filename: Optional filename. If omitted, resolved from the file object name.
            content_type: Optional MIME type of the document.
            metadata: Optional dictionary of metadata.

        Returns:
            ParserInput: The parser input object.
        """
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
        """Creates a ParserInput instance from an asynchronous FastAPI/Starlette UploadFile.

        Args:
            upload_file: The uploaded file object (expected to have async read() method).
            filename: Optional filename. If omitted, fetched from upload_file attributes.
            content_type: Optional MIME type. If omitted, fetched from upload_file attributes.
            metadata: Optional dictionary of metadata.

        Returns:
            ParserInput: The parser input object.
        """
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
    """Base interface for document parser engines (e.g., Docling, Azure AI Document Intelligence)."""

    name: ClassVar[str]
    schema_version: ClassVar[str] = "raw"

    @classmethod
    @abstractmethod
    def from_config(cls) -> "Parser":
        """Creates a parser provider instance from application settings/configuration.

        Returns:
            Parser: An instance of the parser provider.
        """
        pass

    @abstractmethod
    async def parse(self, parser_input: ParserInput) -> Any:
        """Parses a document according to the provider's specific engine.

        Args:
            parser_input: The input document configuration containing the source, bytes, or file info.

        Returns:
            Any: The parsed result object (e.g., ParsedDocument or provider-specific raw structure).
        """
        pass

    def to_cache_data(self, result: Any) -> dict[str, Any]:
        """Converts the parser result to a JSON-serializable dictionary for storage cache.

        Args:
            result: The parsed document returned from `parse()`.

        Returns:
            dict[str, Any]: The JSON-serializable cache payload.

        Raises:
            TypeError: If the result type cannot be serialized.
        """
        if isinstance(result, dict):
            return self._to_jsonable(result)
        if hasattr(result, "model_dump"):
            return result.model_dump(mode="json")
        raise TypeError(f"{self.name} parser result is not cacheable: {type(result)!r}")

    def from_cache_data(self, data: dict[str, Any]) -> Any:
        """Restores a parsed document result from cached JSON-serializable data.

        Args:
            data: The cached JSON-serializable dictionary.

        Returns:
            Any: The reconstructed parsed result object.
        """
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
