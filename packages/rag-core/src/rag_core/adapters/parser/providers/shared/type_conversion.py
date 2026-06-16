"""Type conversion and safety casting utilities for parser providers."""

import copy
from typing import Any, Literal, cast

from rag_core.adapters.parser.providers.native_text.parser import NativeTextParser
from rag_core.parsers.schemas import ParsedElement, ParsedPage


def to_string(value: Any) -> str | None:
    """Safely convert a value to a string, returning None if not a string.

    Args:
        value: Any input value.

    Returns:
        The string if the input is a string, otherwise None.
    """
    if isinstance(value, str):
        return value
    return None


def to_dict(value: Any) -> dict[str, Any]:
    """Safely convert a value to a dict, returning empty dict if not a dict.

    Args:
        value: Any input value.

    Returns:
        The dictionary if the input is a dict, otherwise an empty dict.
    """
    if isinstance(value, dict):
        return value
    return {}


def to_dict_or_none(value: Any) -> dict[str, Any] | None:
    """Safely convert a value to a dict or None if not a dict.

    Args:
        value: Any input value.

    Returns:
        The dictionary if the input is a dict, otherwise None.
    """
    if isinstance(value, dict):
        return value
    return None


def to_list(value: Any) -> list[Any]:
    """Safely convert a value to a list, returning empty list if not a list.

    Args:
        value: Any input value.

    Returns:
        The list if the input is a list, otherwise an empty list.
    """
    if isinstance(value, list):
        return value
    return []


def to_int(value: Any) -> int | None:
    """Safely convert a value to an integer, returning None on failure.

    Args:
        value: Any input value.

    Returns:
        The integer value if conversion succeeds, otherwise None.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    """Safely convert a value to a float, returning None on failure.

    Args:
        value: Any input value.

    Returns:
        The float value if conversion succeeds, otherwise None.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_and_sort_pages(pages_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize, validate and sort pages from a raw parser response.

    If the page numbers form a valid, unique sequence (1 to N) regardless of their order,
    we sort the pages by their page number to ensure correct logical flow.
    Otherwise (if there are duplicates, missing numbers, etc.), we assign them sequential
    1-indexed page numbers (1 to N) based on their original list order.
    """
    n = len(pages_list)
    if n == 0:
        return []

    raw_page_nos: list[int | None] = []
    for page_data in pages_list:
        p_no = page_data.get("page_no")
        if isinstance(p_no, int):
            raw_page_nos.append(p_no)
        else:
            raw_page_nos.append(None)

    expected_sequence = list(range(1, n + 1))
    is_valid_sequence = all(x is not None for x in raw_page_nos) and set(raw_page_nos) == set(expected_sequence)

    result_pages = []
    if is_valid_sequence:
        # Since it is a valid 1..N set of pages, sort the pages by their page_no
        # to ensure they are returned in ascending order.
        validated_page_nos = cast(list[int], raw_page_nos)
        sorted_indices = sorted(range(n), key=lambda i: validated_page_nos[i])
        for idx in sorted_indices:
            result_pages.append(copy.deepcopy(pages_list[idx]))
    else:
        # Overwrite/assign sequentially based on list order
        for idx, page_data in enumerate(pages_list):
            new_page = copy.deepcopy(page_data)
            new_page["page_no"] = idx + 1
            result_pages.append(new_page)

    return result_pages


def process_parser_pages(
    pages_list: list[dict[str, Any]],
    doc_id: str,
    parse_format: Literal["text", "markdown"] = "text",
) -> tuple[list[ParsedPage], list[ParsedElement], str]:
    """Normalize/sort page list, extract plain text or markdown elements for each page,
    and guarantee sequential ordering of both page IDs and element IDs.
    """
    sorted_pages = normalize_and_sort_pages(pages_list)

    pages: list[ParsedPage] = []
    elements: list[ParsedElement] = []
    native_text_parser = NativeTextParser()

    for page_data in sorted_pages:
        page_no = page_data["page_no"]
        page_text = page_data.get("text", "")
        page_id = f"{doc_id}_page_{page_no}"

        pages.append(ParsedPage(page_id=page_id, page_no=page_no))

        # Parse page content into elements dynamically
        actual_format = "plain_text" if parse_format == "text" else parse_format
        parser_method_name = f"_parse_{actual_format}"
        if hasattr(native_text_parser, parser_method_name):
            parse_fn = getattr(native_text_parser, parser_method_name)
            page_elements = parse_fn(page_text, doc_id)
        else:
            raise ValueError(f"Unsupported parse format: {parse_format}")

        for el in page_elements:
            el.page_id = page_id
            elements.append(el)

    # Re-index element order and assign unique element IDs
    for idx, el in enumerate(elements):
        el.order = idx
        el.element_id = f"{doc_id}_el_{idx}"

    full_text = "\n\n".join(p.get("text", "") for p in sorted_pages)

    return pages, elements, full_text
