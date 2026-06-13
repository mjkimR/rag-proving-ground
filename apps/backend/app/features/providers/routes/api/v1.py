from typing import Annotated

from app.features.providers.routes.schemas import ProviderOptions
from app.features.providers.routes.usecases.options import GetProviderOptionsUseCase
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/providers", tags=["Providers"])


@router.get("/options", response_model=ProviderOptions)
async def get_provider_options(
    use_case: Annotated[GetProviderOptionsUseCase, Depends()],
):
    return await use_case.execute()
