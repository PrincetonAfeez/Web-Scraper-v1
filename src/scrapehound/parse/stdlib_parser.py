"""HTML extraction using only Python's standard library."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin

from scrapehound.exceptions import ParseError
from scrapehound.http.encoding import decode_html
from scrapehound.models import ParsedPage

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.base_href: str | None = None
        self.title_parts: list[str] = []
        self.description: str | None = None
        self.og_description: str | None = None
        self.headings: list[str] = []
        self._capture_title = False
        self._title_closed = False
        self._capture_heading: str | None = None
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr_map = {name.lower(): value for name, value in attrs if value is not None}
        if tag in {"a", "area"} and attr_map.get("href"):
            self.links.append(attr_map["href"])
        elif tag in {"iframe", "frame"} and attr_map.get("src"):
            self.links.append(attr_map["src"])
        elif tag == "base" and attr_map.get("href") and self.base_href is None:
            self.base_href = attr_map["href"]
        elif tag == "title":
            self._capture_title = True
            self.title_parts = []
        elif tag in _HEADING_TAGS and self._capture_heading is None:
            self._capture_heading = tag
            self._heading_parts = []
        elif tag == "meta":
            name = (attr_map.get("name") or attr_map.get("property") or "").lower()
            content = attr_map.get("content")
            if content:
                if name == "description":
                    self.description = content.strip()
                elif name == "og:description":
                    self.og_description = content.strip()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._capture_title = False
            self._title_closed = True
        elif tag == self._capture_heading:
            heading = " ".join("".join(self._heading_parts).split())
            if heading:
                self.headings.append(heading)
            self._capture_heading = None
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self.title_parts.append(data)
        if self._capture_heading:
            self._heading_parts.append(data)


class StdlibHTMLParser:
    def parse(self, body: bytes, final_url: str, content_type: str) -> ParsedPage:
        text, encoding = decode_html(body, content_type)
        extractor = _Extractor()
        try:
            extractor.feed(text)
            extractor.close()
        except Exception as exc:
            raise ParseError(f"HTML parse failed: {exc}") from exc
        base = urljoin(final_url, extractor.base_href) if extractor.base_href else final_url
        links: list[str] = []
        seen: set[str] = set()
        for href in extractor.links:
            href = href.strip()
            if not href or href.startswith("#"):
                continue
            resolved, _fragment = urldefrag(urljoin(base, href))
            if resolved.startswith(("http://", "https://")) and resolved not in seen:
                seen.add(resolved)
                links.append(resolved)
        # HTMLParser buffers an unterminated <title> as raw text (RCDATA), so
        # markup can leak in. Only truncate at "<" when </title> was missing,
        # so a properly closed title keeping a decoded "<" (from &lt;) survives.
        raw_title = "".join(extractor.title_parts)
        if not extractor._title_closed:
            raw_title = raw_title.split("<", 1)[0]
        title = " ".join(raw_title.split()) or None
        return ParsedPage(
            final_url=final_url,
            title=title,
            description=extractor.description or extractor.og_description,
            headings=extractor.headings,
            links=links,
            text_encoding=encoding,
        )
