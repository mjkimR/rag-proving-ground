from uuid import UUID

from app_layer_base.base.deps.filters.combine import create_combined_filter_dependency
from app_layer_base.base.deps.filters.decorators import filter_for
from app_layer_base.base.deps.ordering.base import order_by_for
from app_layer_base.base.deps.ordering.combine import create_order_by_dependency
from app_layer_base.base.deps.query_options import create_list_query_options_dependency

from app.features.knowledge.knowledge_base_pages.models import KnowledgeBasePage


# Filters definition
@filter_for(bound_type=UUID)
def document_id(value: UUID | None):
    """Filter by document ID (exact match)"""
    if value is not None:
        return KnowledgeBasePage.document_id == value
    return None


@filter_for(bound_type=str)
def page_id(value: str | None):
    """Filter by page ID (exact match)"""
    if value is not None:
        return KnowledgeBasePage.page_id == value
    return None


@filter_for(bound_type=int)
def page_number(value: int | None):
    """Filter by page number (exact match)"""
    if value is not None:
        return KnowledgeBasePage.page_number == value
    return None


knowledge_base_pages_filters_dependency = create_combined_filter_dependency(
    document_id,
    page_id,
    page_number,
)


# Ordering definition
@order_by_for(alias="page_number")
def page_number_order(desc: bool):
    """Sort by page number"""
    return KnowledgeBasePage.page_number.desc() if desc else KnowledgeBasePage.page_number.asc()


@order_by_for()
def created_at(desc: bool):
    """Sort by creation time"""
    return KnowledgeBasePage.created_at.desc() if desc else KnowledgeBasePage.created_at.asc()


@order_by_for()
def updated_at(desc: bool):
    """Sort by update time"""
    return KnowledgeBasePage.updated_at.desc() if desc else KnowledgeBasePage.updated_at.asc()


knowledge_base_pages_order_by_dependency = create_order_by_dependency(
    page_number_order,
    created_at,
    updated_at,
    default_order="page_number",
)

# Combined Query Options dependency
get_knowledge_base_pages_query_options = create_list_query_options_dependency(
    filters_dependency=knowledge_base_pages_filters_dependency,
    order_by_dependency=knowledge_base_pages_order_by_dependency,
)
