from app.features.knowledge.synonyms.models import SynonymMap
from app_layer_base.base.deps.filters.combine import create_combined_filter_dependency
from app_layer_base.base.deps.filters.decorators import filter_for
from app_layer_base.base.deps.ordering.base import order_by_for
from app_layer_base.base.deps.ordering.combine import create_order_by_dependency
from app_layer_base.base.deps.query_options import create_list_query_options_dependency
from sqlalchemy import Boolean, bindparam, or_
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import ColumnElement


class JsonStringArrayElementPhraseMatch(ColumnElement[bool]):
    """Case-insensitive phrase match against individual JSON string array elements."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, json_column, value: str) -> None:
        self.json_column = json_column
        normalized = value.strip()
        self.exact = bindparam(None, normalized)
        self.prefix = bindparam(None, f"{normalized} %")
        self.infix = bindparam(None, f"% {normalized} %")
        self.suffix = bindparam(None, f"% {normalized}")


@compiles(JsonStringArrayElementPhraseMatch, "postgresql")
def _compile_json_array_element_phrase_match_postgresql(element, compiler, **kw):
    json_column = compiler.process(element.json_column, **kw)
    exact = compiler.process(element.exact, **kw)
    prefix = compiler.process(element.prefix, **kw)
    infix = compiler.process(element.infix, **kw)
    suffix = compiler.process(element.suffix, **kw)
    return (
        "EXISTS ("
        f"SELECT 1 FROM jsonb_array_elements_text({json_column}) AS synonym_value(value) "
        "WHERE "
        f"lower(synonym_value.value) = lower({exact}) OR "
        f"lower(synonym_value.value) LIKE lower({prefix}) OR "
        f"lower(synonym_value.value) LIKE lower({infix}) OR "
        f"lower(synonym_value.value) LIKE lower({suffix})"
        ")"
    )


@compiles(JsonStringArrayElementPhraseMatch, "sqlite")
@compiles(JsonStringArrayElementPhraseMatch)
def _compile_json_array_element_phrase_match_default(element, compiler, **kw):
    json_column = compiler.process(element.json_column, **kw)
    exact = compiler.process(element.exact, **kw)
    prefix = compiler.process(element.prefix, **kw)
    infix = compiler.process(element.infix, **kw)
    suffix = compiler.process(element.suffix, **kw)
    return (
        "EXISTS ("
        f"SELECT 1 FROM json_each({json_column}) AS synonym_value "
        "WHERE "
        f"lower(CAST(synonym_value.value AS TEXT)) = lower({exact}) OR "
        f"lower(CAST(synonym_value.value AS TEXT)) LIKE lower({prefix}) OR "
        f"lower(CAST(synonym_value.value AS TEXT)) LIKE lower({infix}) OR "
        f"lower(CAST(synonym_value.value AS TEXT)) LIKE lower({suffix})"
        ")"
    )


@filter_for(bound_type=str)
def search(value: str | None):
    """Filter by keyword, description, or synonyms containing the search string (case-insensitive)"""
    if value is not None:
        term = f"%{value}%"
        return or_(
            SynonymMap.keyword.ilike(term),
            SynonymMap.description.ilike(term),
            JsonStringArrayElementPhraseMatch(SynonymMap.synonyms, value),
        )
    return None


synonyms_filters_dependency = create_combined_filter_dependency(
    search,
)


# Ordering definition
@order_by_for()
def created_at(desc: bool):
    """Sort by creation time"""
    return SynonymMap.created_at.desc() if desc else SynonymMap.created_at.asc()


@order_by_for()
def updated_at(desc: bool):
    """Sort by update time"""
    return SynonymMap.updated_at.desc() if desc else SynonymMap.updated_at.asc()


@order_by_for()
def keyword_order(desc: bool, alias="keyword"):
    """Sort by keyword"""
    return SynonymMap.keyword.desc() if desc else SynonymMap.keyword.asc()


synonyms_order_by_dependency = create_order_by_dependency(
    created_at,
    updated_at,
    keyword_order,
    default_order="-created_at",
)

get_synonyms_query_options = create_list_query_options_dependency(
    filters_dependency=synonyms_filters_dependency,
    order_by_dependency=synonyms_order_by_dependency,
)
