from app.features.doc_parse.api.v1 import router as v1_doc_parse_router
from app.features.knowledge.api.v1 import router as v1_knowledge_router
from fastapi import APIRouter, status
from rag_core.adapters.vector_store import check_vector_store_health

router = APIRouter(prefix="/api")
v1_router = APIRouter(prefix="/v1", dependencies=[])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health():
    vector_store_healthy = await check_vector_store_health()
    return {
        "status": "ok",
        "vector_db": "healthy" if vector_store_healthy else "unhealthy",
    }


# Feature routers
v1_router.include_router(v1_doc_parse_router)
v1_router.include_router(v1_knowledge_router)
router.include_router(v1_router)
