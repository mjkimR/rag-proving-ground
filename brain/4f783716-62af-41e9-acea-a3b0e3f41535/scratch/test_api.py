import sys
from pathlib import Path

# Add backend and package sources to path
sys.path.insert(0, str(Path("/home/mj/projects/rag-proving-ground/apps/backend")))
sys.path.insert(0, str(Path("/home/mj/projects/rag-proving-ground/packages/rag-core/src")))

import asyncio
from unittest.mock import AsyncMock, patch

from app.main import create_app
from app_file_storage import get_storage_client
from fastapi.testclient import TestClient

# Import ParsedDocument schemas for mocking
from rag_core.parsers.schemas import ContentFormat, ElementType, ParsedDocument, ParsedElement, ParsedPage


async def main():
    # Setup mock ParsedDocument
    mock_doc = ParsedDocument(
        doc_id="test_doc_id",
        parser="mock_parser",
        filename="test.txt",
        text="This is test content.",
        pages=[ParsedPage(page_id="page_1", page_no=1)],
        elements=[
            ParsedElement(
                element_id="elem_1",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.TEXT,
                content="This is a test content for semantic chunking and parsing verification.",
                page_id="page_1",
                order=0,
            )
        ],
    )

    # Patch parse_file globally
    with patch("app.features.knowledge.usecases.upload.parse_file", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = mock_doc

        app = create_app()

        with TestClient(app) as client:
            # 1. Upload a file
            filename = "test.txt"
            content = b"This is a test content for semantic chunking and parsing verification."

            print("--- 1. Testing Upload ---")
            response = client.post(
                "/api/v1/knowledge/test_kb/upload",
                files={"file": (filename, content, "text/plain")},
            )
            print("Upload Response status:", response.status_code)
            if response.status_code != 200:
                print("Upload error details:", response.text)
                return

            data = response.json()
            md5_hash = data["md5_hash"]
            print("Uploaded successfully. MD5 Hash:", md5_hash)
            print("Filename:", data["filename"])
            print("Original file path:", data["original_file_path"])
            print("Parsed data path:", data["parsed_data_path"])
            print("Number of elements in parsed doc:", len(data["parsed_document"]["elements"]))

            # Verify mock was called
            print("Mock parse called:", mock_parse.called)

            # 2. Download the original file
            print("\n--- 2. Testing Download ---")
            download_response = client.get(f"/api/v1/knowledge/test_kb/files/{md5_hash}/download")
            print("Download status:", download_response.status_code)
            print("Downloaded file bytes matches upload:", download_response.content == content)

            # 3. Check storage structure
            print("\n--- 3. Checking Storage Keys ---")
            storage = get_storage_client()
            print("Listing 'knowledge/':")
            async for f in storage.list_files("knowledge/"):
                print("  -", f)

            print("Listing 'parser_cache/':")
            async for f in storage.list_files("parser_cache/"):
                print("  -", f)

            # 4. Delete the document
            print("\n--- 4. Testing Delete ---")
            delete_response = client.delete(f"/api/v1/knowledge/test_kb/files/{md5_hash}")
            print("Delete status:", delete_response.status_code)
            print("Delete response:", delete_response.json())

            # Verify it was deleted in storage
            print("\nListing 'knowledge/' after deletion:")
            async for f in storage.list_files("knowledge/"):
                print("  -", f)


if __name__ == "__main__":
    asyncio.run(main())
