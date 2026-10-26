from __future__ import annotations

import pytest

from rag.factory import Components
from rag.fakes import HashingEmbedder
from rag.models import Principal
from rag.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_scores_match_the_formula() -> None:
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["b", "c"]], k=60))
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert fused["a"] == pytest.approx(1 / 61)
    assert fused["c"] == pytest.approx(1 / 62)


def test_rrf_rewards_agreement_between_rankers() -> None:
    # Second in both lists beats first in only one of them.
    fused = reciprocal_rank_fusion([["a", "b"], ["c", "b"]])
    assert [item for item, _ in fused] == ["b", "a", "c"]


def test_rrf_ties_break_by_id_for_determinism() -> None:
    assert reciprocal_rank_fusion([["z"], ["a"]]) == [("a", 1 / 61), ("z", 1 / 61)]


def test_rrf_rejects_invalid_k() -> None:
    with pytest.raises(ValueError, match="positive"):
        reciprocal_rank_fusion([["a"]], k=0)


def test_rrf_empty() -> None:
    assert reciprocal_rank_fusion([[], []]) == []


def test_hashing_embedder_is_normalised_and_deterministic() -> None:
    embedder = HashingEmbedder(size=64)
    first, second = embedder.embed(["annual leave days", "annual leave days"])
    assert first == second
    assert sum(v * v for v in first) == pytest.approx(1.0)
    assert embedder.dimensions == 64


def test_hybrid_retrieval_ranks_the_right_document_first(
    components: Components, employee: Principal
) -> None:
    hits = components.retriever.retrieve("hotel cap per night in capital cities", employee)
    assert hits[0].chunk.source == "handbook/travel-and-expenses.md"
    assert hits[0].reranker_score is not None
    scores = [h.reranker_score or 0.0 for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_semantic_ranker_can_be_disabled(components: Components, employee: Principal) -> None:
    components.retriever.use_semantic_ranker = False
    try:
        hits = components.retriever.retrieve("hotel cap", employee)
    finally:
        components.retriever.use_semantic_ranker = True
    assert all(h.reranker_score is None for h in hits)
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
