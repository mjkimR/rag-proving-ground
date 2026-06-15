from pathlib import Path
from typing import Any

from loguru import logger

from rag_core.adapters.parser.interface import ParserInput
from rag_core.adapters.parser.providers.shared.type_conversion import (
    to_dict as _dict,
)
from rag_core.adapters.parser.providers.shared.type_conversion import (
    to_dict_or_none as _dict_or_none,
)
from rag_core.adapters.parser.providers.shared.type_conversion import (
    to_float as _float,
)
from rag_core.adapters.parser.providers.shared.type_conversion import (
    to_int as _int,
)
from rag_core.adapters.parser.providers.shared.type_conversion import (
    to_list as _list,
)
from rag_core.adapters.parser.providers.shared.type_conversion import (
    to_string as _string,
)
from rag_core.parsers.schemas import (
    AssetRef,
    BoundingBox,
    ContentFormat,
    ElementType,
    ParsedDocument,
    ParsedElement,
    ParsedPage,
    Provenance,
    TableCellData,
    TableGridData,
)

from .table import (
    is_complex_table,
    table_data,
    table_html,
)

# Mappings from Docling element labels to standard semantic ElementTypes
_LABEL_TO_ELEMENT_TYPE: dict[str, ElementType] = {
    "title": ElementType.HEADING,
    "section_header": ElementType.HEADING,
    "paragraph": ElementType.PARAGRAPH,
    "text": ElementType.PARAGRAPH,
    "list_item": ElementType.LIST_ITEM,
    "table": ElementType.TABLE,
    "picture": ElementType.IMAGE,
    "chart": ElementType.IMAGE,
    "caption": ElementType.CAPTION,
    "footnote": ElementType.FOOTNOTE,
    "formula": ElementType.EQUATION,
    "equation": ElementType.EQUATION,
    "page_header": ElementType.PAGE_HEADER,
    "page_footer": ElementType.PAGE_FOOTER,
    "document_index": ElementType.SECTION_INDEX,
    "code": ElementType.CODE,
    "reference": ElementType.PARAGRAPH,
    "form": ElementType.PARAGRAPH,
    "key_value_region": ElementType.PARAGRAPH,
    "checkbox_selected": ElementType.PARAGRAPH,
    "checkbox-selected": ElementType.PARAGRAPH,
    "checkbox_unselected": ElementType.PARAGRAPH,
    "checkbox-unselected": ElementType.PARAGRAPH,
    "grading_scale": ElementType.PARAGRAPH,
    "handwritten_text": ElementType.PARAGRAPH,
    "empty_value": ElementType.PARAGRAPH,
    "field_region": ElementType.PARAGRAPH,
    "field_heading": ElementType.PARAGRAPH,
    "field_item": ElementType.PARAGRAPH,
    "field_key": ElementType.PARAGRAPH,
    "field_value": ElementType.PARAGRAPH,
    "field_hint": ElementType.PARAGRAPH,
    "marker": ElementType.PARAGRAPH,
}

# Mappings from Docling element labels to standard logical roles (benchmarked from Azure AI Document Intelligence)
_LABEL_TO_LOGICAL_ROLE: dict[str, str] = {
    "title": "title",
    "section_header": "sectionHeading",
    "page_header": "pageHeader",
    "page_footer": "pageFooter",
    "footnote": "footnote",
    "caption": "caption",
}

# Labels that represent layout boilerplate to be marked as ignored during chunking
_LAYOUT_IGNORED_LABELS: set[str] = {
    "page_header",
    "page_footer",
    "document_index",
}

# Standard layout labels we expect but intentionally map to UNKNOWN or their respective types
_EXPECTED_LABELS: set[str] = {
    "page_header",
    "page_footer",
    "document_index",
    "unknown",
}

# Warning counts to restrict duplicate logging of unseen label types
_UNSEEN_LABEL_WARNING_COUNTS: dict[str, int] = {}


def normalize_docling_document(
    document_data: dict[str, Any],
    *,
    parser_input: ParserInput,
    parser_name: str,
    raw_response: dict[str, Any],
    markdown: str,
    text: str,
    html: str = "",
) -> ParsedDocument:
    doc_id = _doc_id(document_data, parser_input)
    pages = _pages(document_data, doc_id)
    page_id_by_no = {page.page_no: page.page_id for page in pages}
    page_height_by_no = {page.page_no: page.height for page in pages if page.height}
    elements = _elements(document_data, page_id_by_no, page_height_by_no)
    _build_heading_tree(elements)
    origin = _dict(document_data.get("origin"))

    return ParsedDocument(
        doc_id=doc_id,
        source=parser_input.source,
        filename=parser_input.filename or _string(origin.get("filename")),
        mimetype=parser_input.content_type or _string(origin.get("mimetype")),
        parser=parser_name,
        pages=pages,
        elements=elements,
        text=text,
        html=html,
        markdown=markdown,
        metadata={
            **parser_input.metadata,
            "name": document_data.get("name"),
            "origin": origin,
        },
        raw=raw_response,
    )


def _doc_id(document_data: dict[str, Any], parser_input: ParserInput) -> str:
    metadata_doc_id = parser_input.metadata.get("doc_id")
    if metadata_doc_id:
        return str(metadata_doc_id)

    origin = document_data.get("origin")
    if isinstance(origin, dict) and origin.get("binary_hash") is not None:
        return f"docling_{origin['binary_hash']}"

    source = parser_input.source or parser_input.filename or _string(document_data.get("name")) or "document"
    return Path(source).stem or source


def _pages(document_data: dict[str, Any], doc_id: str) -> list[ParsedPage]:
    pages_data = _dict(document_data.get("pages"))
    if not pages_data:
        return []

    pages: list[ParsedPage] = []
    for page_key, page_data in sorted(
        pages_data.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else 0
    ):
        if not isinstance(page_data, dict):
            continue

        page_no = _int(page_data.get("page_no")) or _int(page_key) or len(pages) + 1
        size = _dict(page_data.get("size"))
        image_data = _dict_or_none(page_data.get("image"))
        pages.append(
            ParsedPage(
                page_id=_page_id(doc_id, page_no),
                page_no=page_no,
                width=_float(size.get("width")),
                height=_float(size.get("height")),
                image=_asset_ref(image_data),
            )
        )

    return pages


def _elements(
    document_data: dict[str, Any], page_id_by_no: dict[int, str], page_height_by_no: dict[int, float]
) -> list[ParsedElement]:
    indexes: dict[str, list[Any]] = {
        "texts": _list(document_data.get("texts")),
        "tables": _list(document_data.get("tables")),
        "pictures": _list(document_data.get("pictures")),
        "groups": _list(document_data.get("groups")),
    }
    body = _dict(document_data.get("body"))
    root_children = _list(body.get("children"))

    elements: list[ParsedElement] = []
    visited: set[str] = set()

    def traverse(ref: str, parent_id: str | None = None) -> None:
        if ref in visited:
            return
        visited.add(ref)

        item = _resolve_ref(ref, indexes)
        if not isinstance(item, dict):
            return

        parsed_items = _element_from_item(
            item, ref, len(elements), indexes, page_id_by_no, page_height_by_no, parent_id=parent_id
        )
        if not parsed_items:
            return

        primary_el = parsed_items[0]
        elements.extend(parsed_items)

        # Traverse children recursively, but skip table cells to avoid double-chunking
        if primary_el.type != ElementType.TABLE:
            children = _list(item.get("children"))
            for child in children:
                child_ref = _ref(child)
                if child_ref:
                    traverse(child_ref, parent_id=primary_el.element_id)

    for child in root_children:
        child_ref = _ref(child)
        if child_ref:
            traverse(child_ref)

    return elements


def _handle_group(
    item: dict[str, Any],
    ref: str | None,
    order: int,
    indexes: dict[str, list[Any]],
    page_id_by_no: dict[int, str],
    page_height_by_no: dict[int, float],
    provenance: list[Provenance],
    parent_id: str | None = None,
) -> list[ParsedElement]:
    children = _list(item.get("children"))
    child_ids = [child_ref for child in children if (child_ref := _ref(child))]

    if not provenance:
        provenance = _union_child_provenances(children, indexes, page_height_by_no)
    page_no = _first_page_no(provenance)
    return [
        ParsedElement(
            element_id=ref or f"element_{order}",
            type=ElementType.LIST,
            format=ContentFormat.MARKDOWN,
            content="",
            page_id=page_id_by_no.get(page_no) if page_no is not None else None,
            order=order,
            bbox=provenance[0].bbox if provenance else None,
            provenance=provenance,
            children_ids=child_ids,
            parent_id=parent_id,
            metadata=_metadata(item),
        )
    ]


def _handle_heading(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    label = _string(item.get("label"))
    return [
        ParsedElement(
            **common,
            type=ElementType.HEADING,
            format=ContentFormat.MARKDOWN,
            content=_heading_content(item),
            level=_int(item.get("level")) or (1 if label == "title" else None),
        )
    ]


def _handle_list_item(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    return [
        ParsedElement(
            **common,
            type=ElementType.LIST_ITEM,
            format=ContentFormat.MARKDOWN,
            content=_list_item_content(item),
        )
    ]


def _handle_table(
    item: dict[str, Any],
    common: dict[str, Any],
    page_height_by_no: dict[int, float],
) -> list[ParsedElement]:
    html = table_html(item)
    table_common = {key: value for key, value in common.items() if key != "metadata"}

    t_data = table_data(item)
    row_count = _int(t_data.get("num_rows")) or 0
    col_count = _int(t_data.get("num_cols")) or 0
    raw_cells = _list(t_data.get("table_cells"))

    cells: list[TableCellData] = []
    page_no = _first_page_no(common.get("provenance", []))

    for cell in raw_cells:
        if not isinstance(cell, dict):
            continue

        row_idx = _int(cell.get("start_row_offset_idx"))
        col_idx = _int(cell.get("start_col_offset_idx"))
        if row_idx is None or col_idx is None:
            continue

        row_span = _int(cell.get("row_span")) or 1
        col_span = _int(cell.get("col_span")) or 1
        cell_type = "header" if (cell.get("column_header") or cell.get("row_header")) else "data"
        content = _string(cell.get("text")) or ""

        raw_bbox = cell.get("bbox")
        bbox = _bbox(raw_bbox, page_no, page_height_by_no) if raw_bbox else None

        cells.append(
            TableCellData(
                row_index=row_idx,
                col_index=col_idx,
                row_span=row_span,
                col_span=col_span,
                cell_type=cell_type,
                content=content,
                bbox=bbox,
            )
        )

    grid_data = TableGridData(
        row_count=row_count,
        col_count=col_count,
        cells=cells,
    )

    return [
        ParsedElement(
            **table_common,
            type=ElementType.TABLE,
            format=ContentFormat.HTML,
            content=html,
            table_data=grid_data,
            metadata={
                **_metadata(item),
                "is_complex": is_complex_table(item),
                "num_rows": row_count,
                "num_cols": col_count,
            },
        )
    ]


def _handle_picture(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    return [
        ParsedElement(
            **common,
            type=ElementType.IMAGE,
            format=ContentFormat.ASSET_REF,
            asset=_asset_ref(_dict_or_none(item.get("image"))),
            children_ids=[
                child_ref for child_ref in (_ref(child) for child in _list(item.get("children"))) if child_ref
            ],
        )
    ]


def _handle_footnote(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    return [
        ParsedElement(
            **common,
            type=ElementType.FOOTNOTE,
            format=ContentFormat.MARKDOWN,
            content=_string(item.get("text")) or "",
        )
    ]


def _handle_caption(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    return [
        ParsedElement(
            **common,
            type=ElementType.CAPTION,
            format=ContentFormat.MARKDOWN,
            content=_string(item.get("text")) or "",
        )
    ]


def _handle_equation(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    label = _string(item.get("label"))
    return [
        ParsedElement(
            **common,
            type=ElementType.EQUATION,
            format=ContentFormat.LATEX if label == "formula" else ContentFormat.MARKDOWN,
            content=_string(item.get("text")) or "",
        )
    ]


def _handle_paragraph(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    return [
        ParsedElement(
            **common,
            type=ElementType.PARAGRAPH,
            format=ContentFormat.MARKDOWN,
            content=_string(item.get("text")) or "",
        )
    ]


def _handle_page_header(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    return [
        ParsedElement(
            **common,
            type=ElementType.PAGE_HEADER,
            format=ContentFormat.MARKDOWN,
            content=_string(item.get("text")) or "",
        )
    ]


def _handle_page_footer(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    return [
        ParsedElement(
            **common,
            type=ElementType.PAGE_FOOTER,
            format=ContentFormat.MARKDOWN,
            content=_string(item.get("text")) or "",
        )
    ]


def _handle_document_index(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    html = table_html(item)
    return [
        ParsedElement(
            **common,
            type=ElementType.SECTION_INDEX,
            format=ContentFormat.HTML,
            content=html,
        )
    ]


def _handle_code(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    return [
        ParsedElement(
            **common,
            type=ElementType.CODE,
            format=ContentFormat.TEXT,
            content=_string(item.get("text")) or "",
        )
    ]


def _handle_checkbox(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    label = _string(item.get("label")) or "checkbox_unselected"
    is_selected = "selected" in label.lower() and "unselected" not in label.lower()
    prefix = "[x] " if is_selected else "[ ] "
    text = _string(item.get("text")) or ""
    return [
        ParsedElement(
            **common,
            type=ElementType.PARAGRAPH,
            format=ContentFormat.MARKDOWN,
            content=f"{prefix}{text}".strip(),
        )
    ]


def _handle_default(item: dict[str, Any], common: dict[str, Any]) -> list[ParsedElement]:
    return [
        ParsedElement(
            **common,
            type=ElementType.UNKNOWN,
            format=ContentFormat.MARKDOWN,
            content=_string(item.get("text")) or "",
        )
    ]


_ELEMENT_HANDLERS = {
    "section_header": _handle_heading,
    "title": _handle_heading,
    "list_item": _handle_list_item,
    "table": _handle_table,
    "picture": _handle_picture,
    "chart": _handle_picture,
    "footnote": _handle_footnote,
    "caption": _handle_caption,
    "formula": _handle_equation,
    "equation": _handle_equation,
    "paragraph": _handle_paragraph,
    "text": _handle_paragraph,
    "page_header": _handle_page_header,
    "page_footer": _handle_page_footer,
    "document_index": _handle_document_index,
    "code": _handle_code,
    "reference": _handle_paragraph,
    "form": _handle_paragraph,
    "key_value_region": _handle_paragraph,
    "checkbox_selected": _handle_checkbox,
    "checkbox-selected": _handle_checkbox,
    "checkbox_unselected": _handle_checkbox,
    "checkbox-unselected": _handle_checkbox,
    "grading_scale": _handle_paragraph,
    "handwritten_text": _handle_paragraph,
    "empty_value": _handle_paragraph,
    "field_region": _handle_paragraph,
    "field_heading": _handle_paragraph,
    "field_item": _handle_paragraph,
    "field_key": _handle_paragraph,
    "field_value": _handle_paragraph,
    "field_hint": _handle_paragraph,
    "marker": _handle_paragraph,
}


def _element_from_item(
    item: dict[str, Any],
    ref: str | None,
    order: int,
    indexes: dict[str, list[Any]],
    page_id_by_no: dict[int, str],
    page_height_by_no: dict[int, float],
    parent_id: str | None = None,
) -> list[ParsedElement]:
    provenance = _provenance(item, ref, page_height_by_no)

    if ref and ref.startswith("#/groups/"):
        return _handle_group(
            item, ref, order, indexes, page_id_by_no, page_height_by_no, provenance, parent_id=parent_id
        )

    label = _string(item.get("label")) or "unknown"

    # Track warning for unseen label types (limit to 3 warnings per label type)
    if label not in _LABEL_TO_ELEMENT_TYPE and label not in _EXPECTED_LABELS:
        count = _UNSEEN_LABEL_WARNING_COUNTS.get(label, 0)
        if count < 3:
            _UNSEEN_LABEL_WARNING_COUNTS[label] = count + 1
            logger.warning(
                f"Encountered unseen/unhandled Docling element label '{label}'. "
                f"Mapping to ElementType.UNKNOWN. Item details: {item}"
            )

    page_no = _first_page_no(provenance)
    common = {
        "element_id": ref or f"element_{order}",
        "page_id": page_id_by_no.get(page_no) if page_no is not None else None,
        "order": order,
        "bbox": provenance[0].bbox if provenance else None,
        "provenance": provenance,
        "ignored": label in _LAYOUT_IGNORED_LABELS,
        "logical_role": _LABEL_TO_LOGICAL_ROLE.get(label),
        "metadata": _metadata(item),
        "parent_id": parent_id,
    }

    if label == "table":
        return _handle_table(item, common, page_height_by_no)
    handler = _ELEMENT_HANDLERS.get(label, _handle_default)
    return handler(item, common)


def _heading_content(item: dict[str, Any]) -> str:
    text = _string(item.get("text")) or ""
    level = max(1, _int(item.get("level")) or 1)
    return f"{'#' * level} {text}" if text else ""


def _list_item_content(item: dict[str, Any]) -> str:
    text = _string(item.get("text")) or ""
    marker = _string(item.get("marker")) or "-"
    return f"{marker} {text}".strip()


def _provenance(item: dict[str, Any], source_ref: str | None, page_height_by_no: dict[int, float]) -> list[Provenance]:
    prov_items = _list(item.get("prov"))
    result: list[Provenance] = []
    for prov in prov_items:
        if not isinstance(prov, dict):
            continue
        page_no = _int(prov.get("page_no"))
        charspan = prov.get("charspan")
        result.append(
            Provenance(
                page_no=page_no,
                bbox=_bbox(
                    prov.get("bbox") if isinstance(prov.get("bbox"), dict) else None, page_no, page_height_by_no
                ),
                charspan=(int(charspan[0]), int(charspan[1]))
                if isinstance(charspan, list) and len(charspan) == 2
                else None,
                source_ref=source_ref,
            )
        )
    return result


def _union_child_provenances(
    children: list[Any], indexes: dict[str, list[Any]], page_height_by_no: dict[int, float]
) -> list[Provenance]:
    all_provs: list[Provenance] = []
    for child in children:
        child_ref = _ref(child)
        child_item = _resolve_ref(child_ref, indexes)
        if not isinstance(child_item, dict):
            continue
        child_prov = _provenance(child_item, child_ref, page_height_by_no)
        if child_prov:
            all_provs.extend(child_prov)

    if not all_provs:
        return []

    # Group provenances by page number to support multi-page groups
    provs_by_page: dict[int, list[Provenance]] = {}
    for prov in all_provs:
        if prov.page_no is not None:
            provs_by_page.setdefault(prov.page_no, []).append(prov)

    result: list[Provenance] = []
    for page_no, page_provs in sorted(provs_by_page.items()):
        lefts = [p.bbox.left for p in page_provs if p.bbox]
        tops = [p.bbox.top for p in page_provs if p.bbox]
        rights = [p.bbox.right for p in page_provs if p.bbox]
        bottoms = [p.bbox.bottom for p in page_provs if p.bbox]

        if lefts and tops and rights and bottoms:
            merged_bbox = BoundingBox(
                left=min(lefts),
                top=min(tops),
                right=max(rights),
                bottom=max(bottoms),
                coord_origin="TOPLEFT",
            )
        else:
            merged_bbox = None

        charspan_starts = [p.charspan[0] for p in page_provs if p.charspan]
        charspan_ends = [p.charspan[1] for p in page_provs if p.charspan]
        merged_charspan = (min(charspan_starts), max(charspan_ends)) if charspan_starts and charspan_ends else None

        result.append(
            Provenance(
                page_no=page_no,
                bbox=merged_bbox,
                charspan=merged_charspan,
                source_ref=page_provs[0].source_ref if page_provs else None,
            )
        )

    return result


def _bbox(data: dict[str, Any] | None, page_no: int | None, page_height_by_no: dict[int, float]) -> BoundingBox | None:
    if data is None:
        return None
    left = _float(data.get("l"))
    top = _float(data.get("t"))
    right = _float(data.get("r"))
    bottom = _float(data.get("b"))
    if left is None or top is None or right is None or bottom is None:
        return None

    coord_origin = _string(data.get("coord_origin"))

    if coord_origin == "BOTTOMLEFT":
        if page_no is not None and page_no in page_height_by_no:
            # Full Y-axis flip using actual page height
            page_height = page_height_by_no[page_no]
            new_top = page_height - top
            new_bottom = page_height - bottom
            top = min(new_top, new_bottom)
            bottom = max(new_top, new_bottom)
        else:
            # Page height unknown: in BOTTOMLEFT, Docling stores the visual top
            # with a LARGER Y value ("t" key). So we just ensure top < bottom.
            top, bottom = min(top, bottom), max(top, bottom)
        coord_origin = "TOPLEFT"

    return BoundingBox(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        coord_origin=coord_origin,
    )


def _asset_ref(data: dict[str, Any] | None) -> AssetRef | None:
    if data is None:
        return None
    size = _dict(data.get("size"))
    return AssetRef(
        uri=_string(data.get("uri")),
        mimetype=_string(data.get("mimetype")),
        width=_float(size.get("width")),
        height=_float(size.get("height")),
        dpi=_int(data.get("dpi")),
    )


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "docling_label": item.get("label"),
        "content_layer": item.get("content_layer"),
    }
    if item.get("meta") is not None:
        metadata["meta"] = item.get("meta")
    return metadata


def _resolve_ref(ref: str | None, indexes: dict[str, list[Any]]) -> Any:
    if not ref or not ref.startswith("#/"):
        return None
    parts = ref.removeprefix("#/").split("/")
    if len(parts) != 2:
        return None
    collection, index_text = parts
    index = _int(index_text)
    if index is None:
        return None
    items = indexes.get(collection)
    if items is None or index < 0 or index >= len(items):
        return None
    return items[index]


def _ref(value: Any) -> str | None:
    if isinstance(value, dict):
        return _string(value.get("$ref"))
    return None


def _page_id(doc_id: str, page_no: int) -> str:
    return f"{doc_id}_page_{page_no}"


def _first_page_no(provenance: list[Provenance]) -> int | None:
    for item in provenance:
        if item.page_no is not None:
            return item.page_no
    return None


def _build_heading_tree(elements: list[ParsedElement]) -> None:
    """Build nested layout tree by setting parent_id and children_ids.

    Links non-heading elements and lower-level headings to the closest active parent heading.
    """
    stack: list[tuple[int, ParsedElement]] = []

    for el in elements:
        if el.ignored:
            continue

        if el.type == ElementType.HEADING:
            level = el.level if el.level is not None else 1
            while stack and stack[-1][0] >= level:
                stack.pop()

            if stack:
                parent = stack[-1][1]
                if el.parent_id is None:
                    el.parent_id = parent.element_id
                    if el.element_id not in parent.children_ids:
                        parent.children_ids.append(el.element_id)

            stack.append((level, el))
        else:
            if stack:
                parent = stack[-1][1]
                if el.parent_id is None:
                    el.parent_id = parent.element_id
                    if el.element_id not in parent.children_ids:
                        parent.children_ids.append(el.element_id)
