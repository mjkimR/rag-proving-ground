"""Utility to render PDF pages as images and upload them to storage."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from loguru import logger

from rag_core.parsers.schemas import AssetRef

if TYPE_CHECKING:
    from app_file_storage import FileStorageClient


async def render_and_store_pdf_pages(
    pdf_bytes: bytes,
    doc_id: str,
    storage_client: FileStorageClient,
    *,
    target_max_dim: int = 1280,
    image_format: str = "jpeg",
    jpeg_quality: int = 80,
) -> list[AssetRef]:
    """Render PDF pages as images and upload them to object storage.

    TODO: This function is a CPU-bound operation (rendering PDF pages and PIL JPEG encoding)
    mixed with I/O-bound object storage uploads. Currently, it runs synchronously on the main
    async event loop. Consider offloading the CPU-bound parts (page rendering & image compression)
    to a separate thread using `asyncio.to_thread` or decoupling it into an external containerized
    rendering service to prevent event loop blocking under heavy loads.
    """
    import pypdfium2 as pdfium

    mimetype = f"image/{image_format}"
    asset_refs: list[AssetRef] = []

    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        for page_no in range(len(doc)):
            page = doc[page_no]
            # get_size() returns (width, height) in PDF points (1 point = 1/72 inch)
            width, height = page.get_size()

            # 1. Calculate zoom ratio based on the target maximum dimension (target_max_dim)
            max_dim = max(width, height)
            scale = target_max_dim / max_dim if max_dim > target_max_dim else 150 / 72.0

            bitmap = page.render(scale=scale)  # type: ignore
            img = bitmap.to_pil()

            # Ensure image is in RGB mode if saving as JPEG
            if img.mode != "RGB" and image_format.lower() in ("jpeg", "jpg"):
                img = img.convert("RGB")

            # 2. Lightly compress to JPEG using Pillow (recommended quality is 80)
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format=image_format.upper(), quality=jpeg_quality)
            img_bytes = img_byte_arr.getvalue()

            storage_key = f"page_images/{doc_id}/page_{page_no + 1:04d}.{image_format}"

            await storage_client.upload_file(storage_key, img_bytes)
            asset_refs.append(
                AssetRef(
                    path=storage_key,
                    mimetype=mimetype,
                    width=float(img.width),
                    height=float(img.height),
                    dpi=int(scale * 72),
                )
            )
            logger.debug(f"Rendered, compressed and uploaded page {page_no + 1}: {storage_key}")
    finally:
        doc.close()

    logger.info(f"Rendered {len(asset_refs)} pages for doc_id={doc_id}")
    return asset_refs
