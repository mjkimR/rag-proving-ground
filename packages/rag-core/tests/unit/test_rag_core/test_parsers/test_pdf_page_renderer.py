from unittest.mock import MagicMock, patch

from rag_core.parsers.pdf_page_renderer import render_and_store_pdf_pages


async def test_render_and_store_pdf_pages(mocker):
    # Mock storage client
    mock_storage = MagicMock()
    mock_storage.upload_file = mocker.AsyncMock()

    # Mock pypdfium2
    mock_doc = MagicMock()
    mock_page_1 = MagicMock()
    mock_page_1.get_size.return_value = (1000, 2000)

    mock_bitmap = MagicMock()
    mock_img_instance = MagicMock()
    mock_img_instance.width = 500
    mock_img_instance.height = 1000
    mock_img_instance.mode = "RGB"

    mock_bitmap.to_pil.return_value = mock_img_instance
    mock_page_1.render.return_value = mock_bitmap

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.return_value = mock_page_1
    mock_doc.close = MagicMock()

    with patch("pypdfium2.PdfDocument", return_value=mock_doc):
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
