from app.features.providers.ai_models.models import AIModel
from app.features.providers.ai_models.schemas import AIModelCreate, AIModelPatch, AIModelPut
from app_layer_base.base.repos.base import BaseRepository


class AIModelRepository(BaseRepository[AIModel, AIModelCreate, AIModelPut, AIModelPatch]):
    model = AIModel
