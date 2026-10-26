"""Number retrieved chunks as sources and keep only the citations an answer really uses."""

from __future__ import annotations

from collections.abc import Sequence

from rag.models import Citation, SearchHit
from rag.text import citation_markers


def build_citations(hits: Sequence[SearchHit]) -> list[Citation]:
    """One citation per hit, numbered from 1 in prompt order."""
    return [
        Citation(
            marker=i,
            source=hit.chunk.source,
            title=hit.chunk.title,
            section=hit.chunk.section,
            chunk_id=hit.chunk.id,
        )
        for i, hit in enumerate(hits, start=1)
    ]


def used_citations(answer: str, citations: Sequence[Citation]) -> list[Citation]:
    """Citations referenced in the answer, in order of first use, unknown markers ignored."""
    by_marker = {c.marker: c for c in citations}
    seen: list[Citation] = []
    for marker in citation_markers(answer):
        citation = by_marker.get(marker)
        if citation and citation not in seen:
            seen.append(citation)
    return seen


def unknown_markers(answer: str, citations: Sequence[Citation]) -> set[int]:
    """Markers that point at no source, a sign of a fabricated citation."""
    known = {c.marker for c in citations}
    return {m for m in citation_markers(answer) if m not in known}
