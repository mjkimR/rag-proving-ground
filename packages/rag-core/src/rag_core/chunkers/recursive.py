import re
from typing import ClassVar

from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_core.tokenizers import BaseTokenizer


class RAGFallbackTextSplitter(RecursiveCharacterTextSplitter):
    """Fallback splitter for oversized parser elements.

    This keeps RecursiveCharacterTextSplitter as the splitting engine, but adds
    RAG-specific protection for markdown image blocks so URLs are not cut apart.
    """

    DEFAULT_SEPARATORS: ClassVar[list[str]] = [
        "\n\n",
        "\n",
        ". ",
        "? ",
        "! ",
        " ",
        "",
    ]

    _MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*]\([^)\s]+(?:\s+\"[^\"]*\")?\)")
    _IMAGE_PLACEHOLDER_PATTERN = re.compile(r"(__IMG_\d{4}__)")

    def __init__(
        self,
        chunk_size: int = 450,
        chunk_overlap: int = 50,
        separators: list[str] | None = None,
        tokenizer: BaseTokenizer | None = None,
        **kwargs,
    ) -> None:
        self.tokenizer = tokenizer
        length_function = tokenizer.count_tokens if tokenizer else len
        super().__init__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators or self.DEFAULT_SEPARATORS,
            length_function=length_function,
            **kwargs,
        )

    def split_text(self, text: str) -> list[str]:
        protected_text, image_map = self._protect_markdown_images(text)
        chunks = self._isolate_image_placeholders(super().split_text(protected_text))
        return [self._restore_markdown_images(chunk, image_map) for chunk in chunks]

    def _protect_markdown_images(self, text: str) -> tuple[str, dict[str, str]]:
        image_map: dict[str, str] = {}

        def replace(match: re.Match[str]) -> str:
            placeholder = f"__IMG_{len(image_map) + 1:04d}__"
            image_map[placeholder] = match.group(0)
            return f"\n\n{placeholder}\n\n"

        return self._MARKDOWN_IMAGE_PATTERN.sub(replace, text), image_map

    def _restore_markdown_images(self, text: str, image_map: dict[str, str]) -> str:
        for placeholder, markdown_image in image_map.items():
            text = text.replace(placeholder, markdown_image)
        return text

    def _isolate_image_placeholders(self, chunks: list[str]) -> list[str]:
        isolated: list[str] = []
        for chunk in chunks:
            parts = [part.strip() for part in self._IMAGE_PLACEHOLDER_PATTERN.split(chunk) if part.strip()]
            isolated.extend(parts)
        return isolated
