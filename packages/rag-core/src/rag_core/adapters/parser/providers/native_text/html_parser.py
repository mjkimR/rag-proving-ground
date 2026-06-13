"""HTML document tag-to-elements parsing utilities."""

import html.parser
from html import escape
from typing import ClassVar

from rag_core.parsers.schemas import ContentFormat, ElementType, ParsedElement


class HTMLToElementsParser(html.parser.HTMLParser):
    """HTML parser to convert HTML tags into ParsedElements."""

    BLOCK_TAGS: ClassVar[set[str]] = {
        "p",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ul",
        "ol",
        "section",
        "blockquote",
        "pre",
        "code",
        "article",
        "aside",
        "footer",
        "header",
        "nav",
    }

    VOID_TAGS: ClassVar[set[str]] = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self, doc_id: str) -> None:
        super().__init__(convert_charrefs=True)
        self.doc_id = doc_id
        self.elements: list[ParsedElement] = []
        self.text_accumulator: list[str] = []
        self.current_tag_stack: list[str] = []

        # Ignore/blacklist tag state
        self.ignored_depth = 0
        self.ignored_tags = {"script", "style", "nav", "footer", "aside", "meta", "head"}

        # Table capture state
        self.in_table = False
        self.table_depth = 0
        self.table_html_accumulator: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()

        # Update ignored depth (only if not a void/self-closing tag)
        if tag_lower in self.ignored_tags and tag_lower not in self.VOID_TAGS:
            self.ignored_depth += 1

        # Reconstruct attributes string
        attr_str = ""
        if attrs:
            parts = []
            for name, val in attrs:
                if val is not None:
                    parts.append(f'{name}="{escape(val, quote=True)}"')
                else:
                    parts.append(name)
            attr_str = " " + " ".join(parts)

        # If inside a table, accumulate all tags directly
        if self.in_table:
            # We only track ignored tags inside tables in current_tag_stack
            if tag_lower in self.ignored_tags and tag_lower not in self.VOID_TAGS:
                self.current_tag_stack.append(tag_lower)
            self.table_html_accumulator.append(f"<{tag_lower}{attr_str}>")
            if tag_lower == "table":
                self.table_depth += 1
            return

        # Start of a table
        if tag_lower == "table":
            self._flush_text()
            if tag_lower not in self.VOID_TAGS:
                self.current_tag_stack.append(tag_lower)
            self.in_table = True
            self.table_depth = 1
            self.table_html_accumulator = [f"<table{attr_str}>"]
            return

        # Only push to stack if it's not a self-closing void tag
        if tag_lower not in self.VOID_TAGS:
            self.current_tag_stack.append(tag_lower)

        # Flush text when encountering block-level tags
        if tag_lower in self.BLOCK_TAGS:
            self._flush_text()

    def handle_data(self, data: str) -> None:
        if self.in_table:
            self.table_html_accumulator.append(escape(data))
        else:
            self.text_accumulator.append(data)

    def handle_comment(self, data: str) -> None:
        # HTML comments are explicitly ignored
        pass

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if self.in_table:
            self.table_html_accumulator.append(f"</{tag_lower}>")
            if tag_lower == "table":
                self.table_depth -= 1
                if self.table_depth == 0:
                    table_html = "".join(self.table_html_accumulator)
                    ignored = self.ignored_depth > 0
                    self.elements.append(
                        ParsedElement(
                            element_id=f"{self.doc_id}_el_{len(self.elements)}",
                            type=ElementType.TABLE,
                            format=ContentFormat.HTML,
                            content=table_html,
                            order=len(self.elements),
                            ignored=ignored,
                        )
                    )
                    self.in_table = False
                    self.table_html_accumulator = []

        # Flush block tag close
        if not self.in_table and tag_lower in self.BLOCK_TAGS:
            self._flush_text()

        # Pop matching tag and any unclosed children from stack
        if tag_lower in self.current_tag_stack:
            while self.current_tag_stack:
                popped = self.current_tag_stack.pop()
                if popped in self.ignored_tags and popped not in self.VOID_TAGS:
                    self.ignored_depth = max(0, self.ignored_depth - 1)
                if popped == tag_lower:
                    break

    def _flush_text(self) -> None:
        text = "".join(self.text_accumulator).strip()
        self.text_accumulator = []
        if not text:
            return

        el_type = ElementType.PARAGRAPH
        level = None

        # Find the nearest active block tag
        nearest_block = None
        for tag in reversed(self.current_tag_stack):
            if tag in self.BLOCK_TAGS:
                nearest_block = tag
                break

        if nearest_block:
            if nearest_block in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                el_type = ElementType.HEADING
                level = int(nearest_block[1])
            elif nearest_block == "li":
                el_type = ElementType.LIST_ITEM
            elif nearest_block in {"ul", "ol"}:
                el_type = ElementType.LIST

        ignored = self.ignored_depth > 0

        self.elements.append(
            ParsedElement(
                element_id=f"{self.doc_id}_el_{len(self.elements)}",
                type=el_type,
                format=ContentFormat.TEXT,
                content=text,
                level=level,
                order=len(self.elements),
                ignored=ignored,
            )
        )

    def finish(self) -> list[ParsedElement]:
        self._flush_text()
        return self.elements
