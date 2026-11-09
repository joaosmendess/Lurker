"""Common contract and helpers shared by every job source."""

from collections.abc import Callable
from html.parser import HTMLParser

import httpx

from app.models import Job

REQUEST_TIMEOUT_SECONDS: float = 30.0

# The contract: a source is any function that receives an HTTP client and
# returns normalized jobs. Errors (network, HTTP status, format change) are
# raised; collect.py catches them so one source never breaks the whole run.
type JobSource = Callable[[httpx.Client], list[Job]]


class _TextExtractor(HTMLParser):
    """Collects the text of an HTML document, turning block tags into line breaks."""

    _BLOCK_TAGS = frozenset({"p", "div", "br", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6"})
    _SKIPPED_TAGS = frozenset({"script", "style"})

    def __init__(self) -> None:
        # convert_charrefs=True (the default) already turns "&amp;" into "&"
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth: int = 0
        # The "- " bullet is written before the first real text of an <li>,
        # not at the tag itself: Remotive nests <p> inside <li>, which would
        # otherwise leave the bullet alone on its own line.
        self._pending_bullet: bool = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIPPED_TAGS:
            self._skip_depth += 1
        elif tag == "li":
            self._parts.append("\n")
            self._pending_bullet = True
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIPPED_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._pending_bullet and data.strip():
            self._parts.append("- ")
            self._pending_bullet = False
        self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def html_to_text(html: str) -> str:
    """Convert an HTML fragment to plain text, keeping paragraphs and list items."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()

    clean_lines: list[str] = []
    for line in parser.text().splitlines():
        # split() with no args splits on any whitespace run, so this collapses
        # tabs, non-breaking spaces and repeated spaces into single spaces
        normalized = " ".join(line.split())
        if normalized:
            clean_lines.append(normalized)
    return "\n".join(clean_lines)
