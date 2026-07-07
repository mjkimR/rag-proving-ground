from typing import Annotated
from uuid import UUID

from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, status

from app.features.knowledge.synonyms.query_options import get_synonyms_query_options
from app.features.knowledge.synonyms.schemas import SynonymMapCreate, SynonymMapPatch, SynonymMapPut, SynonymMapRead
from app.features.knowledge.synonyms.usecases.crud import (
    CreateSynonymMapUseCase,
    DeleteSynonymMapUseCase,
    GetMultiSynonymMapUseCase,
    GetSynonymMapUseCase,
    PatchSynonymMapUseCase,
    PutSynonymMapUseCase,
)

router = APIRouter(prefix="/synonyms", tags=["Synonyms"], dependencies=[])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SynonymMapRead)
async def create_synonym_map(
    use_case: Annotated[CreateSynonymMapUseCase, Depends()],
    synonym_map_in: SynonymMapCreate,
):
    return await use_case.execute(synonym_map_in)


@router.get("", response_model=PaginatedList[SynonymMapRead])
async def get_synonym_maps(
    use_case: Annotated[GetMultiSynonymMapUseCase, Depends()],
    query_options: Annotated[ListQueryOptions, Depends(get_synonyms_query_options)],
):
    return await use_case.execute(query_options=query_options)


@router.get("/{synonym_id}", response_model=SynonymMapRead)
async def get_synonym_map(
    use_case: Annotated[GetSynonymMapUseCase, Depends()],
    synonym_id: UUID,
):
    synonym_map = await use_case.execute(synonym_id)
    if not synonym_map:
        raise NotFoundException()
    return synonym_map


@router.patch("/{synonym_id}", response_model=SynonymMapRead)
async def patch_synonym_map(
    use_case: Annotated[PatchSynonymMapUseCase, Depends()],
    synonym_id: UUID,
    synonym_map_in: SynonymMapPatch,
):
    synonym_map = await use_case.execute(synonym_id, synonym_map_in)
    if not synonym_map:
        raise NotFoundException()
    return synonym_map


@router.put("/{synonym_id}", response_model=SynonymMapRead)
async def put_synonym_map(
    use_case: Annotated[PutSynonymMapUseCase, Depends()],
    synonym_id: UUID,
    synonym_map_in: SynonymMapPut,
):
    synonym_map = await use_case.execute(synonym_id, synonym_map_in)
    if not synonym_map:
        raise NotFoundException()
    return synonym_map


@router.delete("/{synonym_id}", response_model=DeleteResponse)
async def delete_synonym_map(
    use_case: Annotated[DeleteSynonymMapUseCase, Depends()],
    synonym_id: UUID,
):
    return await use_case.execute(synonym_id)
