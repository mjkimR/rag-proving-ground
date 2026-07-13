from app_layer_base.base.repos.base import BaseRepository
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.providers.ai_models.models import AIModel
from app.features.providers.ai_models.schemas import AIModelCreate, AIModelPatch, AIModelPut


class AIModelRepository(BaseRepository[AIModel, AIModelCreate, AIModelPut, AIModelPatch]):
    model = AIModel

    async def clear_default(self, session: AsyncSession, model_type: str) -> None:
        """Unset is_default on every model of the given type."""
        await session.execute(update(AIModel).where(AIModel.model_type == model_type).values(is_default=False))
