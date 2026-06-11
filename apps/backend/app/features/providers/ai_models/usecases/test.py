from typing import Annotated, Any
from uuid import UUID

from app.features.providers.ai_models.services import AIModelService
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from rag_core.ai.models import get_embedding_model, get_llm_model, get_reranker_model


class TestAIModelConnectionUseCase(BaseUseCase):
    def __init__(self, service: Annotated[AIModelService, Depends()]) -> None:
        self.service = service

    async def execute(self, ai_model_id: UUID) -> dict[str, Any]:
        async with AsyncTransaction() as session:
            model = await self.service.repo.get_by_pk(session, ai_model_id)
            if not model:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"AI Model with ID '{ai_model_id}' not found."
                )

            try:
                if model.model_type == "llm":
                    llm = get_llm_model(model.name)
                    # Attempt a simple, quick invocation
                    await llm.ainvoke([HumanMessage(content="ping")], config={"timeout": 5.0})  # type: ignore
                elif model.model_type == "embedding":
                    embed = get_embedding_model(model.name)
                    if hasattr(embed, "aembed_query"):
                        await embed.aembed_query("ping")
                    else:
                        embed.embed_query("ping")
                elif model.model_type == "reranker":
                    reranker = get_reranker_model(model.name)
                    docs = [Document(page_content="ping")]
                    if hasattr(reranker, "acompress_documents"):
                        await reranker.acompress_documents(documents=docs, query="ping")
                    else:
                        reranker.compress_documents(documents=docs, query="ping")
                else:
                    raise ValueError(f"Unsupported model type: {model.model_type}")

                return {"success": True, "message": "Connection test completed successfully."}
            except Exception as e:
                return {"success": False, "message": f"Connection test failed: {e}", "error": str(e)}
