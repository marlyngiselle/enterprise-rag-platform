from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import pytest

from rag.factory import Components
from rag.fakes import HashingEmbedder, InMemorySearchIndex
from rag.ingestion.chunking import HeadingChunker
from rag.ingestion.pipeline import IngestionPipeline
from rag.models import Chunk, Principal, SearchHit, SearchRequest
from rag.retrieval.retriever import Retriever
from rag.retrieval.security import (
    InvalidGroupError,
    build_security_filter,
    is_visible,
    normalize_groups,
)
from tests.conftest import make_chunk, make_document


def test_filter_uses_search_in_with_sorted_unique_groups() -> None:
    assert build_security_filter(["finance", "all-employees", "finance"]) == (
        "group_ids/any(g: search.in(g, 'all-employees,finance', ','))"
    )


def test_filter_without_groups_matches_nothing() -> None:
    assert build_security_filter([]) == "group_ids/any(g: false)"


@pytest.mark.parametrize(
    "group",
    ["x') or true or ('", "a,b", "a b", "-leading", "x" * 129, "grp'"],
)
def test_group_ids_that_could_alter_the_filter_are_rejected(group: str) -> None:
    with pytest.raises(InvalidGroupError):
        build_security_filter([group])


def test_entra_object_ids_are_accepted() -> None:
    oid = "6f1c2a3b-0d4e-4f5a-9b8c-7d6e5f4a3b2c"
    assert normalize_groups([oid, f" {oid} ", ""]) == (oid,)


def test_too_many_groups_is_an_explicit_error() -> None:
    with pytest.raises(InvalidGroupError, match="overage"):
        normalize_groups([f"g{i}" for i in range(201)])


def test_chunk_without_groups_is_visible_to_nobody() -> None:
    assert not is_visible(make_chunk("1", "x", groups=()), ["all-employees"])
    assert is_visible(make_chunk("1", "x", groups=("a", "b")), ["b"])


def test_in_memory_index_trims_before_ranking() -> None:
    embedder = HashingEmbedder()
    index = InMemorySearchIndex()
    chunks = [
        make_chunk("pub", "salary review timeline", ("all-employees",)),
        make_chunk("hr", "salary bands and merit budget salary", ("hr-compensation",)),
    ]
    index.upsert(
        [
            c.with_vector(v)
            for c, v in zip(chunks, embedder.embed([c.text for c in chunks]), strict=True)
        ]
    )
    vector = embedder.embed(["salary bands"])[0]
    hits = index.search(SearchRequest("salary bands", vector, ("all-employees",)))
    assert [h.chunk.id for h in hits] == ["pub"]
    hr_hits = index.search(SearchRequest("salary bands", vector, ("hr-compensation",)))
    assert [h.chunk.id for h in hr_hits] == ["hr"]
    assert index.search(SearchRequest("salary bands", vector, ())) == []


@dataclass
class LeakyIndex:
    """Simulates a broken filter: returns everything, whatever the groups."""

    chunks: list[Chunk] = field(default_factory=list)

    def upsert(self, chunks: Sequence[Chunk]) -> int:
        self.chunks.extend(chunks)
        return len(chunks)

    def search(self, request: SearchRequest) -> list[SearchHit]:
        return [SearchHit(c, 1.0, 4.0) for c in self.chunks]


def test_retriever_drops_hits_the_index_should_not_have_returned(
    caplog: pytest.LogCaptureFixture,
) -> None:
    index = LeakyIndex([make_chunk("a", "ok"), make_chunk("b", "secret", ("hr-compensation",))])
    retriever = Retriever(HashingEmbedder(), index)
    hits = retriever.retrieve("anything", Principal("u", ("all-employees",)))
    assert [h.chunk.id for h in hits] == ["a"]
    assert "security trimming dropped 1" in caplog.text


def test_retriever_with_no_groups_does_not_query() -> None:
    index = LeakyIndex([make_chunk("a", "ok")])
    assert Retriever(HashingEmbedder(), index).retrieve("q", Principal("u", ())) == []


def test_pipeline_skips_documents_without_acl() -> None:
    index = InMemorySearchIndex()
    report = IngestionPipeline(HeadingChunker(), HashingEmbedder(), index).run(
        [make_document("# A\ntext"), make_document("# B\ntext", groups=())]
    )
    assert report.documents == 1
    assert report.skipped == ["doc.md"]
    assert len(index) == 1


def test_restricted_document_never_reaches_an_employee(
    components: Components, employee: Principal
) -> None:
    hits = components.retriever.retrieve("merit increase budget salary bands", employee)
    assert hits, "public documents should still match"
    assert all(h.chunk.source != "hr/compensation-review-2026.md" for h in hits)
    answer = components.service.answer("What is the merit increase budget for 2026?", employee)
    assert answer.refused
    assert "3.5" not in answer.text


def test_restricted_document_reaches_its_group(components: Components) -> None:
    hr = Principal("u-hr", ("all-employees", "hr-compensation"))
    answer = components.service.answer("What is the merit increase budget for 2026?", hr)
    assert not answer.refused
    assert "3.5 percent" in answer.text
    assert answer.citations[0].source == "hr/compensation-review-2026.md"
