from rag_core.adapters.parser.interface import Parser
from rag_core.adapters.parser.providers import register_default_parsers
from rag_core.adapters.parser.registry import ParserRegistry


class ParserFactory:
    """Factory facade for parser creation."""

    @classmethod
    def create_parser(cls, provider: str) -> Parser:
        register_default_parsers()
        return ParserRegistry.create_parser(provider)
