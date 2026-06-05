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
    import fitz  # PyMuPDF
    from PIL import Image

    mimetype = f"image/{image_format}"
    asset_refs: list[AssetRef] = []

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page_no in range(len(doc)):
            page = doc.load_page(page_no)
            rect = page.rect
            width, height = rect.width, rect.height

            # 1. Calculate zoom ratio based on the target maximum dimension (target_max_dim)
            max_dim = max(width, height)
            zoom = target_max_dim / max_dim if max_dim > target_max_dim else 150 / 72.0

            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            # 2. Wrap the PyMuPDF Pixmap data into a Pillow Image object
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

            # 3. Lightly compress to JPEG using Pillow (recommended quality is 80)
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format=image_format.upper(), quality=jpeg_quality)
            img_bytes = img_byte_arr.getvalue()

            storage_key = f"page_images/{doc_id}/page_{page_no + 1:04d}.{image_format}"

            await storage_client.upload_file(storage_key, img_bytes)
            asset_refs.append(
                AssetRef(
                    path=storage_key,
                    mimetype=mimetype,
                    width=float(pix.width),
                    height=float(pix.height),
                    dpi=int(zoom * 72),
                )
            )
            logger.debug(f"Rendered, compressed and uploaded page {page_no + 1}: {storage_key}")
    finally:
        doc.close()

    logger.info(f"Rendered {len(asset_refs)} pages for doc_id={doc_id}")
    return asset_refs
