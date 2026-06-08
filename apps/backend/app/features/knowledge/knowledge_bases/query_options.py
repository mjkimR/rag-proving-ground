from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from app_layer_base.base.deps.filters.combine import create_combined_filter_dependency
from app_layer_base.base.deps.filters.decorators import filter_for
from app_layer_base.base.deps.ordering.base import order_by_for
from app_layer_base.base.deps.ordering.combine import create_order_by_dependency
from app_layer_base.base.deps.query_options import create_list_query_options_dependency


# Filters definition
@filter_for(bound_type=str)
def name(value: str | None):
    """Filter by name (case-insensitive substring)"""
    if value is not None:
        return KnowledgeBase.name.ilike(f"%{value}%")
    return None


@filter_for(bound_type=str)
def status(value: str | None):
    """Filter by status (exact match)"""
    if value is not None:
        return KnowledgeBase.status == value
    return None


knowledge_bases_filters_dependency = create_combined_filter_dependency(
    name,
    status,
)


# Ordering definition
@order_by_for()
def created_at(desc: bool):
    """Sort by creation time"""
    return KnowledgeBase.created_at.desc() if desc else KnowledgeBase.created_at.asc()


@order_by_for()
def updated_at(desc: bool):
    """Sort by update time"""
    return KnowledgeBase.updated_at.desc() if desc else KnowledgeBase.updated_at.asc()


@order_by_for()
def name_order(desc: bool, alias="name"):
    """Sort by name"""
    return KnowledgeBase.name.desc() if desc else KnowledgeBase.name.asc()


knowledge_bases_order_by_dependency = create_order_by_dependency(
    created_at,
    updated_at,
    name_order,
    default_order="-created_at",
)

# Combined Query Options dependency
get_knowledge_bases_query_options = create_list_query_options_dependency(
    filters_dependency=knowledge_bases_filters_dependency,
    order_by_dependency=knowledge_bases_order_by_dependency,
)
