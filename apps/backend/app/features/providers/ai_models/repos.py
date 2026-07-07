from app_layer_base.base.repos.base import BaseRepository

from app.features.providers.ai_models.models import AIModel
from app.features.providers.ai_models.schemas import AIModelCreate, AIModelPatch, AIModelPut


class AIModelRepository(BaseRepository[AIModel, AIModelCreate, AIModelPut, AIModelPatch]):
    model = AIModel
