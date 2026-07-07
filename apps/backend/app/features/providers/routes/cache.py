from rag_core.adapters.parser.instance import update_parser_registry
from rag_core.ai.models import update_model_registry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.providers.ai_models.models import AIModel
from app.features.providers.document_parsers.models import DocumentParser


async def refresh_ai_models_cache(session: AsyncSession) -> None:
    """Load active/default models from DB and update the rag_core registry."""
    stmt = select(AIModel)
    res = await session.execute(stmt)
    models = res.scalars().all()
    models_list = [
        {
            "name": m.name,
            "provider": m.provider,
            "model_type": m.model_type,
            "is_active": m.is_active,
            "is_default": m.is_default,
            "connection_info": m.connection_info or {},
            "metadata": m.extra_metadata or {},
        }
        for m in models
    ]
    update_model_registry(models_list)


async def refresh_document_parsers_cache(session: AsyncSession) -> None:
    """Load active/default document parsers from DB and update the rag_core registry."""
    stmt = select(DocumentParser)
    res = await session.execute(stmt)
    parsers = res.scalars().all()
    parsers_list = [
        {
            "name": m.name,
            "is_active": m.is_active,
            "is_default": m.is_default,
            "connection_info": m.connection_info or {},
            "metadata": m.extra_metadata or {},
        }
        for m in parsers
    ]
    update_parser_registry(parsers_list)
