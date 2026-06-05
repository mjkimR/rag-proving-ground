"""페이지 단위 비전 청커 — ColPali 파이프라인용."""

from __future__ import annotations

from loguru import logger

from rag_core.chunkers.schemas import ChunkedDocument
from rag_core.parsers.schemas import ParsedDocument


def visual_chunk_document(document: ParsedDocument) -> list[ChunkedDocument]:
    chunks: list[ChunkedDocument] = []
    sorted_pages = sorted(document.pages, key=lambda p: p.page_no)

    for order, page in enumerate(sorted_pages):
        if not page.image or not page.image.path:
            logger.warning(f"Page {page.page_no} (page_id={page.page_id}) has no image reference, skipping.")
            continue

        page_elements = document.elements_for_page(page.page_id)
        page_text = "\n\n".join(e.content for e in page_elements if not e.ignored and e.content.strip())

        chunks.append(
            ChunkedDocument(
                chunk_id=f"{document.doc_id}:vchunk:{order:04d}",
                doc_id=document.doc_id,
                page_content=page_text,
                order=order,
                page_ids=[page.page_id],
                metadata={
                    "image_storage_path": page.image.path,
                    "page_number": page.page_no,
                },
            )
        )
    return chunks
