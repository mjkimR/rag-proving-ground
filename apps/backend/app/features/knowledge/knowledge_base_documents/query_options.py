from uuid import UUID

from app_layer_base.base.deps.filters.combine import create_combined_filter_dependency
from app_layer_base.base.deps.filters.decorators import filter_for
from app_layer_base.base.deps.ordering.base import order_by_for
from app_layer_base.base.deps.ordering.combine import create_order_by_dependency
from app_layer_base.base.deps.query_options import create_list_query_options_dependency

from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument


# Filters definition
@filter_for(bound_type=str)
def name(value: str | None):
    """Filter by name (case-insensitive substring)"""
    if value is not None:
        return KnowledgeBaseDocument.name.ilike(f"%{value}%")
    return None


@filter_for(bound_type=str)
def status(value: str | None):
    """Filter by status (exact match)"""
    if value is not None:
        return KnowledgeBaseDocument.status == value
    return None


@filter_for(bound_type=UUID)
def knowledge_base_id(value: UUID | None):
    """Filter by knowledge base ID (exact match)"""
    if value is not None:
        return KnowledgeBaseDocument.knowledge_base_id == value
    return None


knowledge_base_documents_filters_dependency = create_combined_filter_dependency(
    name,
    status,
    knowledge_base_id,
)


# Ordering definition
@order_by_for()
def created_at(desc: bool):
    """Sort by creation time"""
    return KnowledgeBaseDocument.created_at.desc() if desc else KnowledgeBaseDocument.created_at.asc()


@order_by_for()
def updated_at(desc: bool):
    """Sort by update time"""
    return KnowledgeBaseDocument.updated_at.desc() if desc else KnowledgeBaseDocument.updated_at.asc()


@order_by_for(alias="name")
def name_order(desc: bool):
    """Sort by name"""
    return KnowledgeBaseDocument.name.desc() if desc else KnowledgeBaseDocument.name.asc()


knowledge_base_documents_order_by_dependency = create_order_by_dependency(
    created_at,
    updated_at,
    name_order,
    default_order="-created_at",
)

# Combined Query Options dependency
get_knowledge_base_documents_query_options = create_list_query_options_dependency(
    filters_dependency=knowledge_base_documents_filters_dependency,
    order_by_dependency=knowledge_base_documents_order_by_dependency,
)
