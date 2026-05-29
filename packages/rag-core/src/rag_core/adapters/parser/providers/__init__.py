from rag_core.adapters.parser.providers.docling import DoclingParser
from rag_core.adapters.parser.registry import ParserRegistry

_DEFAULTS_REGISTERED = False


def register_default_parsers() -> None:
    global _DEFAULTS_REGISTERED
    if _DEFAULTS_REGISTERED:
        return

    ParserRegistry.register(DoclingParser)
    _DEFAULTS_REGISTERED = True


__all__ = [
    "DoclingParser",
    "register_default_parsers",
]
