from app_layer_base.base.repos.base import BaseRepository

from app.features.knowledge.synonyms.models import SynonymMap
from app.features.knowledge.synonyms.schemas import SynonymMapCreate, SynonymMapPatch, SynonymMapPut


class SynonymMapRepository(BaseRepository[SynonymMap, SynonymMapCreate, SynonymMapPut, SynonymMapPatch]):
    model = SynonymMap
