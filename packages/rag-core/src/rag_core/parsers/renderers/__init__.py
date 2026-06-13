"""Render ParsedDocument instances into exchange formats.

This module acts as a facade re-exporting rendering engines for Markdown and HTML.
"""

from rag_core.parsers.renderers.html import parsed_document_to_html, to_html
from rag_core.parsers.renderers.markdown import parsed_document_to_markdown, to_markdown

__all__ = [
    "parsed_document_to_html",
    "parsed_document_to_markdown",
    "to_html",
    "to_markdown",
]
