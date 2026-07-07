from uuid import UUID

from app_layer_base.base.deps.filters.combine import create_combined_filter_dependency
from app_layer_base.base.deps.filters.decorators import filter_for
from app_layer_base.base.deps.ordering.base import order_by_for
from app_layer_base.base.deps.ordering.combine import create_order_by_dependency
from app_layer_base.base.deps.query_options import create_list_query_options_dependency

from app.features.history.job_process_histories.models import JobProcessHistory


# Filters definition
@filter_for(bound_type=str)
def resource_type(value: str | None):
    """Filter by resource type"""
    if value is not None:
        return JobProcessHistory.resource_type == value
    return None


@filter_for(bound_type=UUID)
def resource_id(value: UUID | None):
    """Filter by resource ID"""
    if value is not None:
        return JobProcessHistory.resource_id == value
    return None


@filter_for(bound_type=str)
def stage(value: str | None):
    """Filter by stage"""
    if value is not None:
        return JobProcessHistory.stage == value
    return None


@filter_for(bound_type=str)
def outcome(value: str | None):
    """Filter by outcome"""
    if value is not None:
        return JobProcessHistory.outcome == value
    return None


@filter_for(bound_type=str)
def provider(value: str | None):
    """Filter by provider"""
    if value is not None:
        return JobProcessHistory.provider == value
    return None


@filter_for(bound_type=str)
def model_name(value: str | None):
    """Filter by model name"""
    if value is not None:
        return JobProcessHistory.model_name == value
    return None


@filter_for(bound_type=UUID)
def group_id(value: UUID | None):
    """Filter by group ID"""
    if value is not None:
        return JobProcessHistory.group_id == value
    return None


history_filters_dependency = create_combined_filter_dependency(
    resource_type,
    resource_id,
    group_id,
    stage,
    outcome,
    provider,
    model_name,
)


# Ordering definition
@order_by_for()
def created_at(desc: bool):
    """Sort by creation time"""
    return JobProcessHistory.created_at.desc() if desc else JobProcessHistory.created_at.asc()


@order_by_for()
def updated_at(desc: bool):
    """Sort by update time"""
    return JobProcessHistory.updated_at.desc() if desc else JobProcessHistory.updated_at.asc()


@order_by_for()
def duration_seconds(desc: bool):
    """Sort by duration in seconds"""
    return JobProcessHistory.duration_seconds.desc() if desc else JobProcessHistory.duration_seconds.asc()


history_order_by_dependency = create_order_by_dependency(
    created_at,
    updated_at,
    duration_seconds,
    default_order="-created_at",
)

# Combined Query Options dependency
get_job_process_histories_query_options = create_list_query_options_dependency(
    filters_dependency=history_filters_dependency,
    order_by_dependency=history_order_by_dependency,
)
