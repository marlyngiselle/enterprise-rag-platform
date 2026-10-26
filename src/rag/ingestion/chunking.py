"""Chunking strategies.

Sizes are counted in words, a stable proxy for tokens that needs no tokenizer download. At the
defaults (180 words, 30 overlap) a chunk stays well under the 8k input limit of the embedding
models and leaves room for several chunks in the generation prompt.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

from rag.models import Chunk, Document

_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
_SEPARATORS = ("\n\n", "\n", ". ")


def chunk_id(source: str, position: int) -> str:
    """Deterministic key, valid for Azure AI Search (letters, digits, dash, underscore)."""
    return hashlib.sha256(f"{source}#{position}".encode()).hexdigest()[:32]


def word_count(text: str) -> int:
    return len(text.split())


class Chunker(Protocol):
    def split(self, document: Document) -> list[Chunk]: ...


def _validate(max_words: int, overlap_words: int) -> None:
    if max_words < 10:
        msg = "max_words must be at least 10"
        raise ValueError(msg)
    if not 0 <= overlap_words < max_words // 2:
        msg = "overlap_words must be between 0 and half of max_words"
        raise ValueError(msg)


def fixed_windows(text: str, max_words: int, overlap_words: int) -> list[str]:
    """Sliding windows of ``max_words`` that share ``overlap_words`` with the previous one."""
    words = text.split()
    if not words:
        return []
    step = max_words - overlap_words
    windows = []
    for start in range(0, len(words), step):
        windows.append(" ".join(words[start : start + max_words]))
        if start + max_words >= len(words):
            break
    return windows


def recursive_split(
    text: str, max_words: int, overlap_words: int, separators: tuple[str, ...] = _SEPARATORS
) -> list[str]:
    """Split on the coarsest separator that keeps pieces under ``max_words``.

    Paragraphs first, then lines, then sentences, then fixed windows as the last resort.
    Pieces are packed greedily, and each new chunk starts with the tail of the previous one.
    """
    if word_count(text) <= max_words:
        return [text.strip()] if text.strip() else []
    if not separators:
        return fixed_windows(text, max_words, overlap_words)

    sep, rest = separators[0], separators[1:]
    pieces: list[str] = []
    for raw in text.split(sep):
        piece = raw.strip()
        if not piece:
            continue
        if word_count(piece) > max_words:
            pieces.extend(recursive_split(piece, max_words, overlap_words, rest))
        else:
            pieces.append(piece if sep != ". " or piece.endswith(".") else piece + ".")

    chunks: list[str] = []
    current: list[str] = []
    for piece in pieces:
        candidate = [*current, piece]
        if current and word_count(" ".join(candidate)) > max_words:
            chunks.append(" ".join(current) if sep == ". " else sep.join(current))
            tail = " ".join(" ".join(current).split()[-overlap_words:]) if overlap_words else ""
            current = [tail, piece] if tail else [piece]
            if word_count(" ".join(current)) > max_words:
                current = [piece]
        else:
            current = candidate
    if current:
        chunks.append(" ".join(current) if sep == ". " else sep.join(current))
    return chunks


@dataclass(frozen=True)
class FixedSizeChunker:
    """Baseline: fixed word windows with overlap, blind to document structure."""

    max_words: int = 180
    overlap_words: int = 30

    def __post_init__(self) -> None:
        _validate(self.max_words, self.overlap_words)

    def split(self, document: Document) -> list[Chunk]:
        windows = fixed_windows(document.text, self.max_words, self.overlap_words)
        return [
            Chunk(
                id=chunk_id(document.source, i),
                source=document.source,
                title=document.title,
                section=document.title,
                text=window,
                acl_groups=document.acl_groups,
                position=i,
            )
            for i, window in enumerate(windows)
        ]


@dataclass(frozen=True)
class Section:
    path: tuple[str, ...]
    text: str

    @property
    def breadcrumb(self) -> str:
        return " > ".join(self.path)


def split_sections(markdown: str) -> list[Section]:
    """Split Markdown by headings and keep the heading path of every section."""
    sections: list[Section] = []
    path: list[tuple[int, str]] = []
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append(Section(tuple(title for _, title in path), body))
        buffer.clear()

    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else _HEADING.match(line)
        if match:
            flush()
            level = len(match.group("hashes"))
            path = [(lvl, title) for lvl, title in path if lvl < level]
            path.append((level, match.group("title").strip()))
        else:
            buffer.append(line)
    flush()
    return sections


@dataclass(frozen=True)
class HeadingChunker:
    """Structure aware: one chunk per heading section, split recursively when too long.

    The heading path travels with the chunk as ``section``, which is what citations show and
    what the semantic ranker uses as the title field.
    """

    max_words: int = 180
    overlap_words: int = 30

    def __post_init__(self) -> None:
        _validate(self.max_words, self.overlap_words)

    def split(self, document: Document) -> list[Chunk]:
        chunks: list[Chunk] = []
        for section in split_sections(document.text):
            name = section.breadcrumb or document.title
            for piece in recursive_split(section.text, self.max_words, self.overlap_words):
                position = len(chunks)
                chunks.append(
                    Chunk(
                        id=chunk_id(document.source, position),
                        source=document.source,
                        title=document.title,
                        section=name,
                        text=piece,
                        acl_groups=document.acl_groups,
                        position=position,
                    )
                )
        return chunks
