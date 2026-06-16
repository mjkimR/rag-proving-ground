from rag_core.adapters.parser.providers.shared.type_conversion import (
    normalize_and_sort_pages,
)


def test_normalize_and_sort_pages_valid_sequence() -> None:
    # 1. Valid, ordered 1-indexed sequence
    pages = [{"page_no": 1, "text": "A"}, {"page_no": 2, "text": "B"}, {"page_no": 3, "text": "C"}]
    expected = [{"page_no": 1, "text": "A"}, {"page_no": 2, "text": "B"}, {"page_no": 3, "text": "C"}]
    assert normalize_and_sort_pages(pages) == expected


def test_normalize_and_sort_pages_unordered_sequence() -> None:
    # 2. Out-of-order sequence should be sorted by page_no to keep correct logical flow
    pages = [{"page_no": 3, "text": "C"}, {"page_no": 1, "text": "A"}, {"page_no": 2, "text": "B"}]
    expected = [{"page_no": 1, "text": "A"}, {"page_no": 2, "text": "B"}, {"page_no": 3, "text": "C"}]
    assert normalize_and_sort_pages(pages) == expected


def test_normalize_and_sort_pages_non_integer() -> None:
    # 3. Non-integer page numbers or missing values should fallback to 1..N order matching list order
    pages = [{"page_no": 1, "text": "A"}, {"page_no": "invalid", "text": "B"}, {"page_no": None, "text": "C"}]
    expected = [{"page_no": 1, "text": "A"}, {"page_no": 2, "text": "B"}, {"page_no": 3, "text": "C"}]
    assert normalize_and_sort_pages(pages) == expected


def test_normalize_and_sort_pages_empty() -> None:
    # 4. Empty input list
    assert normalize_and_sort_pages([]) == []


def test_normalize_and_sort_pages_non_one_indexed() -> None:
    # 5. Non 1-indexed sequence should fallback to 1..N order matching list order
    pages = [{"page_no": 2, "text": "A"}, {"page_no": 3, "text": "B"}]
    expected = [{"page_no": 1, "text": "A"}, {"page_no": 2, "text": "B"}]
    assert normalize_and_sort_pages(pages) == expected


def test_normalize_and_sort_pages_duplicates() -> None:
    # 6. Duplicated page numbers should fallback to 1..N order matching list order
    pages = [{"page_no": 1, "text": "A"}, {"page_no": 2, "text": "B"}, {"page_no": 2, "text": "C"}]
    expected = [{"page_no": 1, "text": "A"}, {"page_no": 2, "text": "B"}, {"page_no": 3, "text": "C"}]
    assert normalize_and_sort_pages(pages) == expected
