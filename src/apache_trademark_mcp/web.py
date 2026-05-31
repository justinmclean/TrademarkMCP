"""Stdlib-only HTML fetching and parsing helpers for compliance checks."""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser

DEFAULT_TIMEOUT_SECONDS = 15.0
USER_AGENT = "apache-trademark-mcp/0.1"
MAX_BYTES = 2_000_000  # 2 MB safety cap


@dataclass
class Link:
    href: str
    text: str


@dataclass
class Image:
    src: str
    alt: str


@dataclass
class FetchedPage:
    url: str
    final_url: str
    status: int
    html: str
    text: str
    title: str
    headings: list[str]  # h1/h2 text, in document order
    links: list[Link]
    images: list[Image]
    error: str | None = None

    @property
    def text_lower(self) -> str:
        return self.text.lower()

    @property
    def host(self) -> str:
        try:
            return urllib.parse.urlparse(self.final_url).netloc.lower()
        except ValueError:
            return ""


@dataclass
class _PageBuilder(HTMLParser):
    """Collect title, headings, links, images, and visible text from HTML."""

    title: str = ""
    headings: list[str] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    images: list[Image] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)

    _in_title: bool = False
    _heading_tag: str | None = None
    _heading_buf: list[str] = field(default_factory=list)
    _link_href: str | None = None
    _link_text_buf: list[str] = field(default_factory=list)
    _skip_depth: int = 0  # script/style nesting

    def __post_init__(self) -> None:
        # dataclasses don't call HTMLParser.__init__ — do it manually
        HTMLParser.__init__(self, convert_charrefs=True)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return

        if tag == "title":
            self._in_title = True

        if tag in {"h1", "h2", "h3"}:
            self._heading_tag = tag
            self._heading_buf = []

        if tag == "a":
            self._link_href = attrs_dict.get("href", "")
            self._link_text_buf = []

        if tag == "img":
            self.images.append(
                Image(
                    src=attrs_dict.get("src", ""),
                    alt=attrs_dict.get("alt", ""),
                )
            )

        if tag == "br":
            self.text_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return

        if tag == "title":
            self._in_title = False

        if tag in {"h1", "h2", "h3"} and self._heading_tag == tag:
            heading = " ".join("".join(self._heading_buf).split())
            if heading:
                self.headings.append(heading)
            self._heading_tag = None
            self._heading_buf = []
            self.text_parts.append(" ")

        if tag == "a" and self._link_href is not None:
            text = " ".join("".join(self._link_text_buf).split())
            self.links.append(Link(href=self._link_href, text=text))
            self._link_href = None
            self._link_text_buf = []

        if tag in {"p", "div", "section", "header", "footer", "li", "br"}:
            self.text_parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return

        if self._in_title:
            self.title += data

        if self._heading_tag is not None:
            self._heading_buf.append(data)

        if self._link_href is not None:
            self._link_text_buf.append(data)

        self.text_parts.append(data)

    def visible_text(self) -> str:
        return " ".join("".join(self.text_parts).split())

    def collected_title(self) -> str:
        return " ".join(self.title.split())


def parse_html(html: str) -> tuple[str, list[str], list[Link], list[Image], str]:
    """Return ``(title, headings, links, images, visible_text)`` from HTML."""
    builder = _PageBuilder()
    try:
        builder.feed(html)
        builder.close()
    except Exception:
        # html.parser is tolerant but recover if anything raises.
        pass
    return (
        builder.collected_title(),
        builder.headings,
        builder.links,
        builder.images,
        builder.visible_text(),
    )


def fetch_page(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> FetchedPage:
    """Fetch ``url`` and return a parsed :class:`FetchedPage`.

    Errors are captured in the ``error`` field rather than raised so callers
    can present a structured result.
    """
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        return FetchedPage(
            url=url,
            final_url=url,
            status=0,
            html="",
            text="",
            title="",
            headings=[],
            links=[],
            images=[],
            error="URL must start with http:// or https://",
        )

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            status = resp.status
            final_url = resp.geturl() or url
            charset = resp.headers.get_content_charset() or "utf-8"
            raw = resp.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raw = raw[:MAX_BYTES]
            try:
                html = raw.decode(charset, errors="replace")
            except LookupError:
                html = raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return FetchedPage(
            url=url,
            final_url=url,
            status=exc.code,
            html="",
            text="",
            title="",
            headings=[],
            links=[],
            images=[],
            error=f"HTTP {exc.code} fetching {url}",
        )
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
        return FetchedPage(
            url=url,
            final_url=url,
            status=0,
            html="",
            text="",
            title="",
            headings=[],
            links=[],
            images=[],
            error=f"Could not fetch {url}: {exc}",
        )

    title, headings, links, images, text = parse_html(html)
    return FetchedPage(
        url=url,
        final_url=final_url,
        status=status,
        html=html,
        text=text,
        title=title,
        headings=headings,
        links=links,
        images=images,
    )


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def is_apache_host(host: str) -> bool:
    """Return True if ``host`` is on the apache.org domain."""
    host = (host or "").lower().lstrip(".")
    return host == "apache.org" or host.endswith(".apache.org")


def host_of(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except ValueError:
        return ""


def absolutise(base: str, href: str) -> str:
    if not href:
        return ""
    try:
        return urllib.parse.urljoin(base, href)
    except ValueError:
        return href


def second_level_domain(host: str) -> str:
    """Return the bare second-level domain of ``host``.

    For ``foo.bar.example.com`` -> ``example``.
    """
    host = (host or "").lower().lstrip(".")
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) < 2:
        return ""
    return parts[-2]
