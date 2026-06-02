from rag_core.chunkers import RAGFallbackTextSplitter


def test_fallback_splitter_preserves_markdown_image_urls() -> None:
    splitter = RAGFallbackTextSplitter(chunk_size=25, chunk_overlap=0)
    image = "![chart](https://example.com/reports/chart.png)"

    chunks = splitter.split_text(f"앞 문장입니다. {image} 뒤 문장입니다.")

    assert any(chunk == image for chunk in chunks)
    assert all("__IMG_" not in chunk for chunk in chunks)
