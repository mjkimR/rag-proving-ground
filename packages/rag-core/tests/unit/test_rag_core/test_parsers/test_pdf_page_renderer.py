from unittest.mock import MagicMock, patch

from rag_core.parsers.pdf_page_renderer import render_and_store_pdf_pages


async def test_render_and_store_pdf_pages(mocker):
    # Mock storage client
    mock_storage = MagicMock()
    mock_storage.upload_file = mocker.AsyncMock()

    # Mock fitz
    mock_doc = MagicMock()
    mock_page_1 = MagicMock()
    mock_page_1.rect.width = 1000
    mock_page_1.rect.height = 2000
    mock_pixmap_1 = MagicMock()
    mock_pixmap_1.width = 500
    mock_pixmap_1.height = 1000
    mock_pixmap_1.samples = b"raw_pixels"
    mock_page_1.get_pixmap.return_value = mock_pixmap_1

    mock_doc.__len__.return_value = 1
    mock_doc.load_page.return_value = mock_page_1
    mock_doc.close = MagicMock()

    # Mock Pillow Image
    mock_image_class = mocker.patch("PIL.Image.frombytes")
    mock_img_instance = MagicMock()
    mock_image_class.return_value = mock_img_instance

    with patch("fitz.open", return_value=mock_doc):
        asset_refs = await render_and_store_pdf_pages(
            pdf_bytes=b"dummy_pdf",
            doc_id="doc1",
            storage_client=mock_storage,
            target_max_dim=1000,
            image_format="jpeg",
            jpeg_quality=80,
        )

    assert len(asset_refs) == 1
    assert asset_refs[0].path == "page_images/doc1/page_0001.jpeg"
    assert asset_refs[0].mimetype == "image/jpeg"
    mock_storage.upload_file.assert_called_once()
    mock_doc.close.assert_called_once()
