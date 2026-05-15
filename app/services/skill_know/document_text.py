from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser


HTML_TAG_PATTERN = re.compile(r"</?(?:p|div|br|h[1-6]|ul|ol|li|table|thead|tbody|tr|th|td|blockquote|pre|img)\b", re.I)


def looks_like_html(content: str) -> bool:
    return bool(HTML_TAG_PATTERN.search(str(content or "")))


class _DocumentHtmlParser(HTMLParser):
    HEADING_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
    BLOCK_TAGS = {"p", "div", "blockquote", "pre", "ul", "ol", "table", "thead", "tbody"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.current: list[str] = []
        self.heading_level: int | None = None
        self.in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.HEADING_LEVELS:
            self._flush()
            self.heading_level = self.HEADING_LEVELS[tag]
            return
        if tag in self.BLOCK_TAGS or tag == "tr":
            self._flush()
            return
        if tag == "li":
            self._flush()
            self.current.append("- ")
            return
        if tag in {"th", "td"}:
            if self.current:
                self.current.append(" | ")
            self.in_cell = True
            return
        if tag == "br":
            self._flush()
            return
        if tag == "img":
            attr_map = {name.lower(): value or "" for name, value in attrs}
            alt = attr_map.get("alt") or attr_map.get("title") or "image"
            src = attr_map.get("src") or ""
            self.current.append(f"[图片: {alt}]")
            if src.startswith("/skill-know/documents/assets/"):
                self.current.append(f" {src}")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.HEADING_LEVELS:
            self._flush(heading_level=self.heading_level)
            self.heading_level = None
            return
        if tag in self.BLOCK_TAGS or tag in {"li", "tr"}:
            self._flush()
            return
        if tag in {"th", "td"}:
            self.in_cell = False

    def handle_data(self, data: str) -> None:
        text = unescape(data or "")
        text = re.sub(r"\s+", " ", text)
        if text.strip():
            self.current.append(text)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self, heading_level: int | None = None) -> None:
        text = re.sub(r"\s+", " ", "".join(self.current)).strip()
        self.current = []
        if not text:
            return
        if heading_level:
            text = f"{'#' * heading_level} {text}"
        self.lines.append(text)


def html_to_markdownish_text(content: str) -> str:
    parser = _DocumentHtmlParser()
    parser.feed(str(content or ""))
    parser.close()
    return "\n\n".join(line for line in parser.lines if line.strip()).strip()


def normalize_document_text(content: str) -> str:
    value = str(content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not value:
        return ""
    if looks_like_html(value):
        return html_to_markdownish_text(value)
    return value
