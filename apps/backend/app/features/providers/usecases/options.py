from app.features.providers.schemas import ProviderOptions
from app_layer_base.base.usecases.base import BaseUseCase
from rag_core.adapters.parser.instance import _ACTIVE_PARSERS
from rag_core.adapters.parser.providers import register_default_parsers
from rag_core.adapters.parser.registry import ParserRegistry
from rag_core.ai.models import _ACTIVE_MODELS, get_model_options

register_default_parsers()


class GetProviderOptionsUseCase(BaseUseCase):
    """UseCase to retrieve all dynamic models and parser options from the providers registry."""

    async def execute(self) -> ProviderOptions:
        # 1. Retrieve AI models from the DB active models registry (fallback to LiteLLM config if empty)
        if _ACTIVE_MODELS:
            llm_models = [name for name, m in _ACTIVE_MODELS.items() if m.get("model_type") == "llm"]
            embedding_models = [name for name, m in _ACTIVE_MODELS.items() if m.get("model_type") == "embedding"]
            reranker_models = [name for name, m in _ACTIVE_MODELS.items() if m.get("model_type") == "reranker"]
        else:
            model_options = get_model_options()
            llm_models = model_options["llm_models"]
            embedding_models = model_options["embedding_models"]
            reranker_models = model_options["reranker_models"]

        # 2. Retrieve document parsers from the DB active parsers registry (fallback to ParserRegistry if empty)
        parsers = list(_ACTIVE_PARSERS.keys()) if _ACTIVE_PARSERS else ParserRegistry.list_parsers()

        return ProviderOptions(
            embedding_models=embedding_models,
            llm_models=llm_models,
            reranker_models=reranker_models,
            parser_providers=parsers,
        )
