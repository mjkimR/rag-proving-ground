from typing import Annotated, Any

from app.features.knowledge.synonyms.models import SynonymMap
from app.features.knowledge.synonyms.schemas import SynonymMapCreate, SynonymMapPatch, SynonymMapPut
from app.features.knowledge.synonyms.services import SynonymContextKwargs, SynonymMapService
from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


async def _invalidate_cache() -> None:
    try:
        from rag_core.query_rewrite.synonym_expander import invalidate_synonyms_cache

        await invalidate_synonyms_cache()
    except ImportError:
        pass


class GetSynonymMapUseCase(BaseGetUseCase[SynonymMapService, SynonymMap, SynonymContextKwargs]):
    def __init__(self, service: Annotated[SynonymMapService, Depends()]) -> None:
        super().__init__(service)


class GetMultiSynonymMapUseCase(BaseGetMultiUseCase[SynonymMapService, SynonymMap, SynonymContextKwargs]):
    def __init__(self, service: Annotated[SynonymMapService, Depends()]) -> None:
        super().__init__(service)


class CreateSynonymMapUseCase(BaseCreateUseCase[SynonymMapService, SynonymMap, SynonymMapCreate, SynonymContextKwargs]):
    def __init__(self, service: Annotated[SynonymMapService, Depends()]) -> None:
        super().__init__(service)

    async def _execute(
        self,
        session: AsyncSession,
        obj_data: SynonymMapCreate,
        context: SynonymContextKwargs | None,
    ) -> SynonymMap:
        created = await super()._execute(session, obj_data, context)
        await _invalidate_cache()
        return created


class PatchSynonymMapUseCase(
    BasePatchUseCase[SynonymMapService, SynonymMap, SynonymMapPut, SynonymMapPatch, SynonymContextKwargs]
):
    def __init__(self, service: Annotated[SynonymMapService, Depends()]) -> None:
        super().__init__(service)

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: SynonymMapPatch,
        context: SynonymContextKwargs | None,
    ) -> SynonymMap | None:
        updated = await super()._execute(session, obj_pk, obj_data, context)
        await _invalidate_cache()
        return updated


class PutSynonymMapUseCase(
    BasePutUseCase[SynonymMapService, SynonymMap, SynonymMapPut, SynonymMapPatch, SynonymContextKwargs]
):
    def __init__(self, service: Annotated[SynonymMapService, Depends()]) -> None:
        super().__init__(service)

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: SynonymMapPut,
        context: SynonymContextKwargs | None,
    ) -> SynonymMap | None:
        updated = await super()._execute(session, obj_pk, obj_data, context)
        await _invalidate_cache()
        return updated


class DeleteSynonymMapUseCase(BaseDeleteUseCase[SynonymMapService, SynonymMap, SynonymContextKwargs]):
    def __init__(self, service: Annotated[SynonymMapService, Depends()]) -> None:
        super().__init__(service)

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        context: SynonymContextKwargs | None,
    ) -> Any:
        deleted = await super()._execute(session, obj_pk, context)
        await _invalidate_cache()
        return deleted
