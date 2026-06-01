from app.features.knowledge.knowledge_chunking_histories.api.v1 import router as chunking_router
from app.features.knowledge.knowledge_embedding_histories.api.v1 import router as embedding_router
from app.features.knowledge.knowledge_parsing_histories.api.v1 import router as parsing_router
from fastapi.routing import APIRoute


def test_history_routers_expose_only_read_methods() -> None:
    for router in [parsing_router, chunking_router, embedding_router]:
        route_methods = {method for route in router.routes if isinstance(route, APIRoute) for method in route.methods}
        assert route_methods == {"GET"}
