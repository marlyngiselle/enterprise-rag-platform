"""Deterministic metrics. Retrieval relevance is judged at document level.

Ranked chunk lists are reduced to their unique sources in rank order before scoring, so two
chunks of the same relevant document count once. Relevance is binary.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from rag.models import Citation, SearchHit
from rag.retrieval.security import is_visible
from rag.text import citation_markers, split_sentences, strip_markers, tokenize

GROUNDED_SUPPORT = 0.6


def unique_sources(hits: Sequence[SearchHit]) -> list[str]:
    seen: list[str] = []
    for hit in hits:
        if hit.chunk.source not in seen:
            seen.append(hit.chunk.source)
    return seen


def recall_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    return len(relevant_set & set(ranked[:k])) / len(relevant_set)


def reciprocal_rank(ranked: Sequence[str], relevant: Iterable[str]) -> float:
    relevant_set = set(relevant)
    for rank, item in enumerate(ranked, start=1):
        if item in relevant_set:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    relevant_set = set(relevant)
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item in enumerate(ranked[:k], start=1)
        if item in relevant_set
    )
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant_set), k) + 1))
    return dcg / ideal if ideal else 0.0


def citation_coverage(answer: str) -> float:
    """Share of answer sentences that carry at least one citation marker."""
    sentences = split_sentences(answer)
    if not sentences:
        return 0.0
    return sum(1 for s in sentences if citation_markers(s)) / len(sentences)


def sentence_support(sentence: str, sources: Sequence[str]) -> float:
    """Share of the sentence's content words found in the text of the sources it cites."""
    words = set(tokenize(strip_markers(sentence)))
    if not words:
        return 1.0
    available: set[str] = set()
    for text in sources:
        available.update(tokenize(text))
    return len(words & available) / len(words)


def groundedness(answer: str, citations: Sequence[Citation], hits: Sequence[SearchHit]) -> float:
    """Share of sentences whose cited sources contain at least 60 percent of their words.

    A lexical proxy, deliberately strict: a sentence with no marker scores zero. It catches
    fabricated citations and drift from the sources, not subtle paraphrase errors, which is
    what the optional LLM judge is for.
    """
    sentences = split_sentences(answer)
    if not sentences:
        return 0.0
    text_by_chunk = {h.chunk.id: h.chunk.text for h in hits}
    chunk_by_marker = {c.marker: c.chunk_id for c in citations}
    grounded = 0
    for sentence in sentences:
        cited = [
            text_by_chunk[chunk_by_marker[m]]
            for m in citation_markers(sentence)
            if m in chunk_by_marker and chunk_by_marker[m] in text_by_chunk
        ]
        if cited and sentence_support(sentence, cited) >= GROUNDED_SUPPORT:
            grounded += 1
    return grounded / len(sentences)


def term_recall(answer: str, expected_terms: Sequence[str]) -> float:
    if not expected_terms:
        return 1.0
    lowered = answer.lower()
    return sum(1 for t in expected_terms if t.lower() in lowered) / len(expected_terms)


def access_violations(hits: Sequence[SearchHit], groups: Sequence[str]) -> int:
    """Hits the caller is not entitled to see. Anything above zero is a security defect."""
    return sum(1 for h in hits if not is_visible(h.chunk, groups))


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
