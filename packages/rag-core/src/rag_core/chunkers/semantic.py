import re
from dataclasses import dataclass
from typing import Any, ClassVar

from rag_core.chunkers.recursive import RAGFallbackTextSplitter
from rag_core.chunkers.schemas import ChunkedDocument, ChunkingConfig
from rag_core.parsers import BoundingBox, ContentFormat, ElementType, ParsedDocument, ParsedElement, Provenance


@dataclass(slots=True)
class _SemanticBlock:
    text: str
    raw_text: str
    type: ElementType
    level: int | None
    breadcrumb: list[str]
    source_element_ids: list[str]
    source_element_orders: list[int]
    source_element_types: list[str]
    source_bboxes: list[dict[str, Any]]
    page_ids: list[str]
    page_numbers: list[int]
    source: str | None
    filename: str | None
    metadata_element_type: str

    def copy(self) -> "_SemanticBlock":
        return _SemanticBlock(
            text=self.text,
            raw_text=self.raw_text,
            type=self.type,
            level=self.level,
            breadcrumb=list(self.breadcrumb),
            source_element_ids=list(self.source_element_ids),
            source_element_orders=list(self.source_element_orders),
            source_element_types=list(self.source_element_types),
            source_bboxes=list(self.source_bboxes),
            page_ids=list(self.page_ids),
            page_numbers=list(self.page_numbers),
            source=self.source,
            filename=self.filename,
            metadata_element_type=self.metadata_element_type,
        )

    def merge(self, block: "_SemanticBlock") -> None:
        self.text = f"{self.text.rstrip()}\n{block.raw_text.strip()}"
        self.raw_text = f"{self.raw_text.rstrip()}\n{block.raw_text.strip()}"
        self.source_element_ids.extend(block.source_element_ids)
        self.source_element_orders.extend(block.source_element_orders)
        self.source_element_types.extend(block.source_element_types)
        self.source_bboxes.extend(block.source_bboxes)
        self.page_ids = _unique_strings([*self.page_ids, *block.page_ids])
        self.page_numbers = _unique_ints([*self.page_numbers, *block.page_numbers])
        self.metadata_element_type = "merged"

    def to_metadata(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "filename": self.filename,
            "element_type": self.metadata_element_type,
            "breadcrumb": list(self.breadcrumb),
            "source_element_orders": list(self.source_element_orders),
            "source_element_types": list(self.source_element_types),
            "element_order_start": min(self.source_element_orders) if self.source_element_orders else None,
            "element_order_end": max(self.source_element_orders) if self.source_element_orders else None,
            "page_numbers": list(self.page_numbers),
            "source_bboxes": list(self.source_bboxes),
        }


class RAGSemanticChunker:
    """Parser-aware chunker for normalized ParsedDocument objects.

    The parser's structured elements are treated as the first chunking pass.
    This class enriches those units with heading breadcrumbs, merges small
    sibling fragments, and only falls back to recursive splitting for oversized
    text.
    """

    _MERGEABLE_TYPES: ClassVar[set[ElementType]] = {
        ElementType.LIST,
        ElementType.LIST_ITEM,
        ElementType.CAPTION,
        ElementType.FOOTNOTE,
    }

    def __init__(
        self,
        config: ChunkingConfig | None = None,
        fallback_splitter: RAGFallbackTextSplitter | None = None,
    ) -> None:
        """Initializes the RAGSemanticChunker.

        Args:
            config: Optional ChunkingConfig configuration values.
            fallback_splitter: Optional fallback text splitter for oversized elements.
        """
        self.config = config or ChunkingConfig()
        self.fallback_splitter = fallback_splitter or RAGFallbackTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )

    def chunk_document(self, document: ParsedDocument, summary: str | None = None) -> list[ChunkedDocument]:
        """Creates embedding chunks from a normalized parsed document.

        The method enriches parsed elements with heading breadcrumbs, merges small
        sibling fragments, and falls back to recursive splitting for oversized text.

        Args:
            document: The input ParsedDocument object to split.
            summary: Optional summary to prepend to each chunk for contextual retrieval.

        Returns:
            list[ChunkedDocument]: A list of chunked document instances with metadata.
        """

        blocks = self._build_enriched_blocks(document)
        merged_blocks = self._merge_micro_chunks(blocks)

        chunks: list[ChunkedDocument] = []

        prepend_text = ""
        available_chunk_size = self.config.chunk_size
        fallback_splitter = self.fallback_splitter

        if summary:
            # We want to ensure at least some meaningful chunk size for actual content.
            # If summary is too long, we might need to truncate it to fit within a reasonable ratio (e.g. 50% of chunk size).
            max_summary_len = int(self.config.chunk_size * 0.5)
            if len(summary) > max_summary_len:
                summary = summary[:max_summary_len] + "..."

            prepend_text = f"[Document Summary: {summary}]\n\n"
            prepend_len = len(prepend_text)

            # Calculate reduced chunk size allowing room for prepend_text
            available_chunk_size = max(100, self.config.chunk_size - prepend_len)

            # Re-initialize the fallback splitter with the reduced chunk size
            fallback_splitter = RAGFallbackTextSplitter(
                chunk_size=available_chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            )

        for block in merged_blocks:
            text = block.text.strip()
            if not text:
                continue

            parts = [text]
            if len(text) > available_chunk_size:
                parts = [part.strip() for part in fallback_splitter.split_text(text) if part.strip()]

            for part_index, part in enumerate(parts):
                metadata = block.to_metadata()
                metadata.update(
                    {
                        "chunk_part_index": part_index,
                        "chunk_part_count": len(parts),
                        "is_split_chunk": len(parts) > 1,
                    }
                )

                final_content = f"{prepend_text}{part}" if prepend_text else part

                chunks.append(
                    ChunkedDocument(
                        chunk_id=f"{document.doc_id}:chunk:{len(chunks) + 1:04d}",
                        doc_id=document.doc_id,
                        page_content=final_content,
                        order=len(chunks) + 1,
                        source_element_ids=list(block.source_element_ids),
                        page_ids=list(block.page_ids),
                        metadata=metadata,
                    )
                )

        _attach_chunk_navigation_metadata(chunks)
        return chunks

    def _build_enriched_blocks(self, document: ParsedDocument) -> list[_SemanticBlock]:
        """Builds blocks enriched with heading breadcrumbs and bounding box metadata.

        Args:
            document: The ParsedDocument from which to extract elements.

        Returns:
            list[_SemanticBlock]: The generated semantic blocks.
        """
        headings: list[tuple[int, str]] = []
        blocks: list[_SemanticBlock] = []
        page_no_by_id = {page.page_id: page.page_no for page in document.pages}

        for element in sorted(document.elements, key=lambda item: item.order):
            if element.ignored:
                continue
            if element.type == ElementType.HEADING:
                heading = self._element_text(element)
                if heading:
                    level = self._safe_level(element.level)
                    headings = [item for item in headings if item[0] < level]
                    headings.append((level, heading))
                continue

            content = self._element_text(element)
            if not content:
                continue

            breadcrumb = self._trim_breadcrumb([heading for _, heading in headings])
            text = self._with_breadcrumb(content, breadcrumb)
            page_ids = [element.page_id] if element.page_id else []
            page_numbers = _page_numbers(page_ids, page_no_by_id, element.provenance)
            source_bboxes = _compact_dicts([_bbox_to_dict(element.bbox)])
            blocks.append(
                _SemanticBlock(
                    text=text,
                    raw_text=content,
                    type=element.type,
                    level=element.level,
                    breadcrumb=breadcrumb,
                    source_element_ids=[element.element_id],
                    source_element_orders=[element.order],
                    source_element_types=[element.type.value],
                    source_bboxes=source_bboxes,
                    page_ids=page_ids,
                    page_numbers=page_numbers,
                    source=document.source,
                    filename=document.filename,
                    metadata_element_type=element.type.value,
                )
            )

        if blocks:
            return blocks

        fallback_text = document.to_markdown(prefer_document=True).strip()
        if not fallback_text:
            return []
        return [
            _SemanticBlock(
                text=fallback_text,
                raw_text=fallback_text,
                type=ElementType.UNKNOWN,
                level=None,
                breadcrumb=[],
                source_element_ids=[],
                source_element_orders=[],
                source_element_types=[ElementType.UNKNOWN.value],
                source_bboxes=[],
                page_ids=[],
                page_numbers=[],
                source=document.source,
                filename=document.filename,
                metadata_element_type=ElementType.UNKNOWN.value,
            )
        ]

    def _merge_micro_chunks(self, blocks: list[_SemanticBlock]) -> list[_SemanticBlock]:
        """Merges small sibling blocks to build chunks of optimal size.

        Args:
            blocks: The list of raw semantic blocks.

        Returns:
            list[_SemanticBlock]: The merged list of semantic blocks.
        """
        merged: list[_SemanticBlock] = []
        buffer: _SemanticBlock | None = None

        for block in blocks:
            if buffer is not None and self._can_merge(buffer, block):
                buffer.merge(block)
                continue

            if buffer is not None:
                merged.append(buffer)
            buffer = block.copy()

        if buffer is not None:
            merged.append(buffer)

        return merged

    def _can_merge(self, left: _SemanticBlock, right: _SemanticBlock) -> bool:
        if left.type not in self._MERGEABLE_TYPES or right.type not in self._MERGEABLE_TYPES:
            return False
        if left.breadcrumb != right.breadcrumb or left.level != right.level:
            return False
        if left.page_ids and right.page_ids and left.page_ids[-1] != right.page_ids[0]:
            return False
        return len(left.text) + 1 + len(right.raw_text) <= self.config.merge_max_chars

    def _trim_breadcrumb(self, headings: list[str]) -> list[str]:
        if self.config.breadcrumb_depth == 0:
            return []
        if len(headings) <= self.config.breadcrumb_depth:
            return headings
        tail = headings[-self.config.breadcrumb_depth :]
        if self.config.include_root_breadcrumb and headings[0] not in tail:
            return [headings[0], *tail[1:]]
        return tail

    def _with_breadcrumb(self, content: str, breadcrumb: list[str]) -> str:
        if not breadcrumb:
            return content.strip()
        return f"{self.config.breadcrumb_separator.join(breadcrumb)}: {content.strip()}"

    def _element_text(self, element: ParsedElement) -> str:
        content = element.content.strip()

        if element.type == ElementType.HEADING:
            return _strip_markdown_heading(content)

        if element.type == ElementType.IMAGE:
            source = ""
            if element.asset is not None:
                source = element.asset.uri or element.asset.path or ""
            if not source and element.format == ContentFormat.ASSET_REF:
                source = content
            if not source:
                return content
            alt = element.metadata.get("alt") or element.metadata.get("caption") or content
            return f"![{_escape_markdown_alt(str(alt))}]({source})"

        return content

    def _safe_level(self, level: int | None) -> int:
        return min(max(level or 1, 1), 6)


def chunk_document(
    document: ParsedDocument, config: ChunkingConfig | None = None, summary: str | None = None
) -> list[ChunkedDocument]:
    """Convenience function for default semantic chunking.

    Args:
        document: The input ParsedDocument object to chunk.
        config: Optional ChunkingConfig for tuning chunking thresholds.
        summary: Optional summary to prepend to each chunk for contextual retrieval.

    Returns:
        list[ChunkedDocument]: A list of chunked document instances.
    """

    return RAGSemanticChunker(config=config).chunk_document(document, summary=summary)


def _strip_markdown_heading(content: str) -> str:
    return re.sub(r"^#{1,6}\s+", "", content.strip())


def _escape_markdown_alt(value: str) -> str:
    return value.replace("[", r"\[").replace("]", r"\]")


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _unique_ints(values: list[int]) -> list[int]:
    seen: set[int] = set()
    unique: list[int] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _page_numbers(
    page_ids: list[str],
    page_no_by_id: dict[str, int],
    provenance: list[Provenance],
) -> list[int]:
    numbers = [page_no_by_id[page_id] for page_id in page_ids if page_id in page_no_by_id]
    numbers.extend(item.page_no for item in provenance if item.page_no is not None)
    return _unique_ints(numbers)


def _bbox_to_dict(bbox: BoundingBox | None) -> dict[str, Any] | None:
    if bbox is None:
        return None
    return {
        "left": bbox.left,
        "top": bbox.top,
        "right": bbox.right,
        "bottom": bbox.bottom,
        "coord_origin": bbox.coord_origin,
    }


def _compact_dicts(values: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
    return [value for value in values if value is not None]


def _attach_chunk_navigation_metadata(chunks: list[ChunkedDocument]) -> None:
    if not chunks:
        return

    ordered_chunks = sorted(chunks, key=lambda chunk: chunk.order)
    page_chunks: dict[str, list[ChunkedDocument]] = {}
    for chunk in ordered_chunks:
        for page_id in chunk.page_ids:
            page_chunks.setdefault(page_id, []).append(chunk)

    page_positions_by_chunk_id: dict[str, list[dict[str, Any]]] = {chunk.chunk_id: [] for chunk in ordered_chunks}
    for page_id, chunks_on_page in page_chunks.items():
        total = len(chunks_on_page)
        for index, chunk in enumerate(chunks_on_page, start=1):
            page_positions_by_chunk_id[chunk.chunk_id].append(
                {
                    "page_id": page_id,
                    "page_chunk_index": index,
                    "page_chunk_count": total,
                    "is_first_chunk_on_page": index == 1,
                    "is_last_chunk_on_page": index == total,
                }
            )

    for index, chunk in enumerate(ordered_chunks):
        page_positions = page_positions_by_chunk_id[chunk.chunk_id]
        chunk.metadata.update(
            {
                "previous_chunk_id": ordered_chunks[index - 1].chunk_id if index > 0 else None,
                "next_chunk_id": ordered_chunks[index + 1].chunk_id if index < len(ordered_chunks) - 1 else None,
                "page_chunk_positions": page_positions,
                "is_first_chunk_on_page": any(item["is_first_chunk_on_page"] for item in page_positions),
                "is_last_chunk_on_page": any(item["is_last_chunk_on_page"] for item in page_positions),
            }
        )
