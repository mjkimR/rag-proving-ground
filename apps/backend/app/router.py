from app.features.doc_parse.api.v1 import router as v1_doc_parse_router
from fastapi import APIRouter, status

router = APIRouter(prefix="/api")
v1_router = APIRouter(prefix="/v1", dependencies=[])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health():
    return {"status": "ok"}


# Feature routers
v1_router.include_router(v1_doc_parse_router)
router.include_router(v1_router)
