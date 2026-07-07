from typing import Annotated

from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends
from rag_core.ai.gateway import fetch_raw_model_info_from_gateway
from rag_core.ai.models import clear_gateway_cache
from sqlalchemy import select

from app.features.providers.ai_models.models import AIModel
from app.features.providers.ai_models.schemas import AIModelCreate
from app.features.providers.ai_models.services import AIModelService
from app.features.providers.routes.cache import refresh_ai_models_cache


class SyncAIModelsUseCase(BaseUseCase):
    def __init__(self, service: Annotated[AIModelService, Depends()]) -> None:
        self.service = service

    async def execute(self) -> list[AIModel]:
        # Clear LiteLLM gateway cache first
        clear_gateway_cache()

        # Fetch raw models from LiteLLM gateway
        try:
            model_list = fetch_raw_model_info_from_gateway()
        except Exception:
            model_list = []

        async with AsyncTransaction() as session:
            # Query existing models in DB
            stmt = select(AIModel)
            res = await session.execute(stmt)
            existing_models = {m.name: m for m in res.scalars().all()}

            new_models = []
            for entry in model_list:
                name = entry.get("model_name")
                if not name:
                    continue

                # Determine type/role from metadata or tags
                metadata = entry.get("metadata") or {}
                role = metadata.get("role") or metadata.get("type")
                if not role and "tags" in metadata:
                    tags = metadata.get("tags") or []
                    if "embedding" in tags:
                        role = "embedding"
                    elif "reranker" in tags:
                        role = "reranker"
                    elif "llm" in tags or "chat" in tags:
                        role = "llm"
                if not role:
                    name_lower = name.lower()
                    if "embedding" in name_lower or ("bge" in name_lower and "rerank" not in name_lower):
                        role = "embedding"
                    elif "reranker" in name_lower or "rerank" in name_lower:
                        role = "reranker"
                    else:
                        role = "llm"

                # Parse provider
                litellm_params = entry.get("litellm_params") or {}
                raw_model_val = litellm_params.get("model") or ""
                provider = "custom"
                if "/" in raw_model_val:
                    provider = raw_model_val.split("/")[0]
                elif "/" in name:
                    provider = name.split("/")[0]

                # Extract connection info
                connection_info = {}

                # Merge parameters
                model_params = metadata.get("model_params") or {}

                if name not in existing_models:
                    # New model discovered, create record schema
                    new_models.append(
                        AIModelCreate(
                            name=name,
                            provider=provider,
                            model_type=role,
                            is_active=True,
                            is_default=False,
                            connection_info=connection_info,
                            extra_metadata={"model_params": model_params},
                        )
                    )

            if new_models:
                await self.service.create_multi(session, new_models)

            await session.flush()
            # Reload registry cache
            await refresh_ai_models_cache(session)

            # Fetch all from DB to return complete list
            stmt = select(AIModel)
            res = await session.execute(stmt)
            return list(res.scalars().all())
