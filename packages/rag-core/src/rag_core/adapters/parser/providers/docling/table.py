from html import escape
from typing import Any

from rag_core.adapters.parser.providers.shared.type_conversion import to_int, to_list, to_string


def table_data(item: dict[str, Any]) -> dict[str, Any]:
    """Extract table data dictionary from a Docling table item.

    Args:
        item: The dictionary representing the table element in the raw Docling JSON.

    Returns:
        A dictionary containing the table's structural data (cells, row/column counts, etc.).
    """
    data = item.get("data")
    if isinstance(data, dict):
        return data
    return {}


def is_complex_table(item: dict[str, Any]) -> bool:
    """Determine if a table is complex based on cell row/column spans.

    A table is considered complex if any cell spans across multiple rows
    or columns (i.e., row_span > 1 or col_span > 1).

    Args:
        item: The dictionary representing the table element.

    Returns:
        True if the table has row/column spans greater than 1, False otherwise.
    """
    cells = table_data(item).get("table_cells")
    if not isinstance(cells, list):
        return False
    return any(
        isinstance(cell, dict) and ((to_int(cell.get("row_span")) or 1) > 1 or (to_int(cell.get("col_span")) or 1) > 1)
        for cell in cells
    )


def table_html(item: dict[str, Any]) -> str:
    """Generate an HTML representation of a Docling table element.

    Constructs a standard HTML <table> with proper <tr>, <th>, and <td> elements.
    It handles cell spans (rowspan and colspan) by grid mapping and skipping covered cells.

    Args:
        item: The dictionary representing the table element.

    Returns:
        A formatted HTML table string.
    """
    data = table_data(item)
    rows = to_int(data.get("num_rows")) or 0
    cols = to_int(data.get("num_cols")) or 0
    cells = to_list(data.get("table_cells"))
    grid: list[list[str | None]] = [["" for _ in range(cols)] for _ in range(rows)]

    for cell in cells:
        if not isinstance(cell, dict):
            continue
        row = to_int(cell.get("start_row_offset_idx"))
        col = to_int(cell.get("start_col_offset_idx"))
        if row is None or col is None or row < 0 or col < 0 or row >= rows or col >= cols:
            continue
        tag = "th" if cell.get("column_header") or cell.get("row_header") else "td"
        attrs = []
        row_span = to_int(cell.get("row_span")) or 1
        col_span = to_int(cell.get("col_span")) or 1
        if row_span > 1:
            attrs.append(f' rowspan="{row_span}"')
        if col_span > 1:
            attrs.append(f' colspan="{col_span}"')
        grid[row][col] = f"<{tag}{''.join(attrs)}>{escape(to_string(cell.get('text')) or '')}</{tag}>"
        for covered_row in range(row, min(row + row_span, rows)):
            for covered_col in range(col, min(col + col_span, cols)):
                if covered_row != row or covered_col != col:
                    grid[covered_row][covered_col] = None

    body = "\n".join(f"  <tr>{''.join((cell or '<td></td>') for cell in row if cell is not None)}</tr>" for row in grid)
    return f"<table>\n{body}\n</table>"
