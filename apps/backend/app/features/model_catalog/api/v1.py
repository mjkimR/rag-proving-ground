from typing import Annotated

from app.features.model_catalog.schemas import ModelCatalogOptions
from app.features.model_catalog.usecases.options import GetModelCatalogOptionsUseCase
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/model_catalog", tags=["ModelCatalog"])


@router.get("/options", response_model=ModelCatalogOptions)
async def get_model_catalog_options(
    use_case: Annotated[GetModelCatalogOptionsUseCase, Depends()],
):
    return await use_case.execute()
