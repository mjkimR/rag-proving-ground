from typing import TYPE_CHECKING

from rag_core.adapters.parser.registry import ParserRegistry

if TYPE_CHECKING:
    from rag_core.adapters.parser.providers.docling.parser import DoclingParser
    from rag_core.adapters.parser.providers.native_text.parser import NativeTextParser

_DEFAULTS_REGISTERED = False

__all__ = [
    "DoclingParser",
    "NativeTextParser",
    "register_default_parsers",
]

_lazy_imports: dict[str, str] = {
    "DoclingParser": ".docling.parser",
    "NativeTextParser": ".native_text.parser",
}


def __getattr__(name: str):
    if name in _lazy_imports:
        import importlib

        module = importlib.import_module(_lazy_imports[name], package=__name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def register_default_parsers() -> None:
    global _DEFAULTS_REGISTERED
    if _DEFAULTS_REGISTERED:
        return

    from rag_core.adapters.parser.providers.docling.parser import DoclingParser
    from rag_core.adapters.parser.providers.native_text.parser import NativeTextParser

    ParserRegistry.register(DoclingParser)
    ParserRegistry.register(NativeTextParser)
    _DEFAULTS_REGISTERED = True
