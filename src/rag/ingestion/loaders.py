"""Document loaders for Markdown, HTML and PDF.

Every loader returns a ``Document`` whose ``acl_groups`` comes from the source itself (front
matter, a meta tag or a sidecar file). A document without groups is still returned, and the
pipeline refuses to index it: access control fails closed.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader

from rag.models import Document

_FRONT_MATTER = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
)
_SKIP_TAGS = frozenset({"script", "style", "noscript", "template", "head"})
_BLOCK_TAGS = frozenset({"p", "div", "section", "article", "li", "tr", "br", "table", "ul", "ol"})


def parse_groups(raw: str) -> tuple[str, ...]:
    """Parse ``[a, b]`` or ``a, b`` into a sorted, de-duplicated tuple."""
    cleaned = raw.strip().strip("[]")
    groups = {part.strip().strip("'\"") for part in cleaned.split(",")}
    return tuple(sorted(g for g in groups if g))


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split simple ``key: value`` front matter from a Markdown body."""
    match = _FRONT_MATTER.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group("body").splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip():
            meta[key.strip()] = value.strip()
    return meta, text[match.end() :]


def _first_heading(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def load_markdown(path: Path, source: str) -> Document:
    meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
    title = meta.get("title") or _first_heading(body) or path.stem
    groups = parse_groups(meta.get("acl_groups", ""))
    extra = {k: v for k, v in meta.items() if k not in {"title", "acl_groups"}}
    return Document(
        source=source,
        title=title,
        text=body.strip(),
        acl_groups=groups,
        content_type="text/markdown",
        metadata=extra,
    )


class _HtmlToMarkdown(HTMLParser):
    """Turns HTML into heading-structured text and drops what a reader cannot see.

    Scripts, styles, comments and elements marked ``hidden`` or ``display:none`` are removed,
    because hidden text is the classic carrier for indirect prompt injection.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self.acl_groups: tuple[str, ...] = ()
        self._stack: list[tuple[str, bool]] = []
        self._in_title = False

    @property
    def _suppressed(self) -> bool:
        return any(hidden for _, hidden in self._stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: (v or "") for k, v in attrs}
        if tag == "meta" and attr.get("name") == "acl-groups":
            self.acl_groups = parse_groups(attr.get("content", ""))
        if tag == "title":
            self._in_title = True
        if tag in _VOID_TAGS:
            if tag == "br" and not self._suppressed:
                self.parts.append("\n")
            return
        style = attr.get("style", "").replace(" ", "").lower()
        hidden = (
            tag in _SKIP_TAGS
            or "hidden" in attr
            or attr.get("aria-hidden") == "true"
            or "display:none" in style
            or "visibility:hidden" in style
        )
        self._stack.append((tag, hidden))
        if self._suppressed:
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n" if tag in {"p", "div", "section", "article"} else "\n")
            if tag == "li":
                self.parts.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                break
        if re.fullmatch(r"h[1-6]", tag) and not self._suppressed:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data.strip()
            return
        if not self._suppressed:
            self.parts.append(re.sub(r"\s+", " ", data))

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [line.strip() for line in raw.splitlines()]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def load_html(path: Path, source: str) -> Document:
    parser = _HtmlToMarkdown()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    body = parser.text()
    return Document(
        source=source,
        title=parser.title or _first_heading(body) or path.stem,
        text=body,
        acl_groups=parser.acl_groups,
        content_type="text/html",
    )


def load_pdf(path: Path, source: str) -> Document:
    """Extract text per page with pypdf; title and groups come from ``<file>.meta.json``."""
    sidecar = path.with_name(path.name + ".meta.json")
    meta: dict[str, object] = {}
    if sidecar.exists():
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
    reader = PdfReader(path)
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"## Page {number}\n\n{text}")
    raw_groups = meta.get("acl_groups", [])
    groups = tuple(sorted({str(g) for g in raw_groups})) if isinstance(raw_groups, list) else ()
    return Document(
        source=source,
        title=str(meta.get("title") or path.stem),
        text="\n\n".join(pages),
        acl_groups=groups,
        content_type="application/pdf",
    )


_LOADERS = {
    ".md": load_markdown,
    ".markdown": load_markdown,
    ".html": load_html,
    ".htm": load_html,
    ".pdf": load_pdf,
}


def supported(path: Path) -> bool:
    return path.suffix.lower() in _LOADERS


def load_path(path: Path, root: Path | None = None) -> Document:
    loader = _LOADERS.get(path.suffix.lower())
    if loader is None:
        msg = f"unsupported file type: {path.suffix}"
        raise ValueError(msg)
    source = path.relative_to(root).as_posix() if root else path.name
    return loader(path, source)


def load_directory(root: Path) -> list[Document]:
    """Load every supported file under ``root`` in a stable order."""
    files = sorted(p for p in root.rglob("*") if p.is_file() and supported(p))
    return [load_path(p, root) for p in files]
