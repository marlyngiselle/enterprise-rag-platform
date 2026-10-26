from __future__ import annotations

import math
from collections.abc import Iterator, Sequence

import pytest

from rag.evaluation import metrics as m
from rag.evaluation.judge import ChatModelJudge
from rag.models import Citation, SearchHit
from rag.providers import ChatMessage
from tests.conftest import make_chunk


def test_recall_at_k() -> None:
    assert m.recall_at_k(["a", "b", "c"], ["a", "c"], k=2) == 0.5
    assert m.recall_at_k(["a"], [], k=5) == 0.0


def test_reciprocal_rank() -> None:
    assert m.reciprocal_rank(["x", "y", "a"], ["a"]) == pytest.approx(1 / 3)
    assert m.reciprocal_rank(["x"], ["a"]) == 0.0


def test_ndcg_known_values() -> None:
    assert m.ndcg_at_k(["a", "b"], ["a"], k=5) == 1.0
    expected = (1 / math.log2(3)) / 1.0
    assert m.ndcg_at_k(["x", "a"], ["a"], k=5) == pytest.approx(expected)
    ideal = 1 + 1 / math.log2(3)
    assert m.ndcg_at_k(["a", "x", "b"], ["a", "b"], k=5) == pytest.approx(
        (1 + 1 / math.log2(4)) / ideal
    )


def test_unique_sources_dedupes_in_rank_order() -> None:
    hits = [
        SearchHit(make_chunk(str(i), "t", source=s), 1.0)
        for i, s in enumerate(["a", "b", "a", "c"])
    ]
    assert m.unique_sources(hits) == ["a", "b", "c"]


def test_citation_coverage() -> None:
    assert m.citation_coverage("One [1]. Two. Three [2].") == pytest.approx(2 / 3)
    assert m.citation_coverage("") == 0.0


def test_groundedness_requires_support_from_the_cited_chunk() -> None:
    hits = [
        SearchHit(make_chunk("c1", "Annual leave is 27 days per year."), 1.0),
        SearchHit(make_chunk("c2", "Hotels are capped at 180 EUR."), 1.0),
    ]
    citations = [Citation(1, "doc.md", "Doc", "S", "c1"), Citation(2, "doc.md", "Doc", "S", "c2")]
    assert m.groundedness("Annual leave is 27 days [1].", citations, hits) == 1.0
    # Right fact, wrong citation: not grounded.
    assert m.groundedness("Annual leave is 27 days [2].", citations, hits) == 0.0
    # Unsupported claim with a citation: not grounded.
    assert m.groundedness("Employees get unlimited paid sabbaticals [1].", citations, hits) == 0.0
    assert m.groundedness("", citations, hits) == 0.0


def test_term_recall_and_access_violations() -> None:
    assert m.term_recall("It is 27 Days.", ["27 days", "March"]) == 0.5
    assert m.term_recall("anything", []) == 1.0
    hits = [SearchHit(make_chunk("a", "t", groups=("hr",)), 1.0)]
    assert m.access_violations(hits, ["all-employees"]) == 1
    assert m.access_violations(hits, ["hr"]) == 0
    assert m.mean([]) == 0.0


class JsonChat:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        return self.reply

    def stream(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        yield self.reply


def test_llm_judge_parses_and_clamps_scores() -> None:
    judge = ChatModelJudge(
        JsonChat('Sure: {"groundedness": 7, "relevance": "4", "rationale": "fine"}')
    )
    verdict = judge.judge("q", "a [1].", ["ctx"])
    assert (verdict.groundedness, verdict.relevance, verdict.rationale) == (5, 4, "fine")


def test_llm_judge_rejects_non_json() -> None:
    with pytest.raises(ValueError, match="JSON"):
        ChatModelJudge(JsonChat("no idea")).judge("q", "a", [])
