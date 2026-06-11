from typing import Annotated, Any
from uuid import UUID

from app.features.providers.document_parsers.services import DocumentParserService
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from rag_core.adapters.parser.instance import parse_file


class TestDocumentParserConnectionUseCase(BaseUseCase):
    def __init__(self, service: Annotated[DocumentParserService, Depends()]) -> None:
        self.service = service

    async def execute(self, document_parser_id: UUID) -> dict[str, Any]:
        async with AsyncTransaction() as session:
            parser = await self.service.repo.get_by_pk(session, document_parser_id)
            if not parser:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document Parser with ID '{document_parser_id}' not found.",
                )

            try:
                # Attempt to parse a simple text file
                dummy_content = b"ping"
                await parse_file(
                    content=dummy_content,
                    filename="test_ping.txt",
                    content_type="text/plain",
                    provider=parser.name,
                    ignore_cache=True,
                )

                return {"success": True, "message": "Connection test completed successfully."}
            except Exception as e:
                return {"success": False, "message": f"Connection test failed: {e}", "error": str(e)}
