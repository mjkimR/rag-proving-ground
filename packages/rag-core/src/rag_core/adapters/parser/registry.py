from typing import ClassVar

from rag_core.adapters.parser.interface import Parser

SUPPORTED_PDF_PROVIDERS: list[str] = ["docling", "pymupdf4llm", "pypdfium2", "pdf_oxide"]


class ParserRegistry:
    """Registry for parser engine providers keyed by provider name."""

    _parsers: ClassVar[dict[str, type[Parser]]] = {}

    @classmethod
    def register(cls, parser_class: type[Parser]) -> None:
        parser_name = parser_class.name
        if parser_name in cls._parsers:
            raise ValueError(f"Parser is already registered: {parser_name}")

        cls._parsers[parser_name] = parser_class

    @classmethod
    def get_parser_class(cls, parser_name: str) -> type[Parser]:
        try:
            return cls._parsers[parser_name]
        except KeyError as exc:
            raise ValueError(f"Unsupported parser: {parser_name}") from exc

    @classmethod
    def create_parser(cls, provider: str) -> Parser:
        parser_class = cls.get_parser_class(provider)
        return parser_class.from_config()

    @classmethod
    def list_parsers(cls) -> list[str]:
        return sorted(cls._parsers)
