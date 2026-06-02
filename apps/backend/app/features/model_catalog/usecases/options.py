from app.features.model_catalog.schemas import ModelCatalogOptions
from app_layer_base.base.usecases.base import BaseUseCase
from rag_core.adapters.parser.providers import register_default_parsers
from rag_core.adapters.parser.registry import ParserRegistry
from rag_core.ai.models import get_model_options

# Register default parsers once at import time
register_default_parsers()


class GetModelCatalogOptionsUseCase(BaseUseCase):
    """UseCase to retrieve all dynamic models and parser options from the catalog."""

    async def execute(self) -> ModelCatalogOptions:
        # Load and parse models.yaml options
        model_options = get_model_options()

        parsers = ParserRegistry.list_parsers()

        return ModelCatalogOptions(
            embedding_models=model_options["embedding_models"],
            llm_models=model_options["llm_models"],
            reranker_models=model_options["reranker_models"],
            parser_providers=parsers,
        )
