from typing import TYPE_CHECKING

from rag_core.adapters.parser.registry import ParserRegistry

if TYPE_CHECKING:
    from rag_core.adapters.parser.providers.docling.parser import DoclingParser
    from rag_core.adapters.parser.providers.native_text.parser import NativeTextParser
    from rag_core.adapters.parser.providers.pdf_oxide.parser import PdfOxideParser
    from rag_core.adapters.parser.providers.pymupdf4llm.parser import PyMuPDF4LLMParser
    from rag_core.adapters.parser.providers.pypdfium2.parser import PyPdfium2Parser

_DEFAULTS_REGISTERED = False

__all__ = [
    "DoclingParser",
    "NativeTextParser",
    "PdfOxideParser",
    "PyMuPDF4LLMParser",
    "PyPdfium2Parser",
    "register_default_parsers",
]

_lazy_imports: dict[str, str] = {
    "DoclingParser": ".docling.parser",
    "NativeTextParser": ".native_text.parser",
    "PyMuPDF4LLMParser": ".pymupdf4llm.parser",
    "PyPdfium2Parser": ".pypdfium2.parser",
    "PdfOxideParser": ".pdf_oxide.parser",
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
    from rag_core.adapters.parser.providers.pdf_oxide.parser import PdfOxideParser
    from rag_core.adapters.parser.providers.pymupdf4llm.parser import PyMuPDF4LLMParser
    from rag_core.adapters.parser.providers.pypdfium2.parser import PyPdfium2Parser

    ParserRegistry.register(DoclingParser)
    ParserRegistry.register(NativeTextParser)
    ParserRegistry.register(PyMuPDF4LLMParser)
    ParserRegistry.register(PyPdfium2Parser)
    ParserRegistry.register(PdfOxideParser)
    _DEFAULTS_REGISTERED = True
