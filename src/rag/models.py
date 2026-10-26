"""Domain types shared by ingestion, retrieval, generation and evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Document:
    """A source document after loading, before chunking."""

    source: str
    title: str
    text: str
    acl_groups: tuple[str, ...]
    content_type: str = "text/markdown"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrievable unit of text with the metadata the index needs."""

    id: str
    source: str
    title: str
    section: str
    text: str
    acl_groups: tuple[str, ...]
    position: int
    vector: tuple[float, ...] = ()

    def with_vector(self, vector: tuple[float, ...]) -> Chunk:
        return Chunk(
            id=self.id,
            source=self.source,
            title=self.title,
            section=self.section,
            text=self.text,
            acl_groups=self.acl_groups,
            position=self.position,
            vector=vector,
        )


@dataclass(frozen=True, slots=True)
class Principal:
    """The caller, as far as retrieval is concerned: an id and the groups it belongs to."""

    user_id: str
    groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SearchRequest:
    text: str
    vector: tuple[float, ...]
    groups: tuple[str, ...]
    top_k: int = 5
    use_semantic_ranker: bool = True


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk: Chunk
    score: float
    reranker_score: float | None = None


@dataclass(frozen=True, slots=True)
class Citation:
    marker: int
    source: str
    title: str
    section: str
    chunk_id: str


@dataclass(frozen=True, slots=True)
class Answer:
    text: str
    citations: tuple[Citation, ...]
    refused: bool
    refusal_reason: str | None = None
    context: tuple[SearchHit, ...] = ()
    quarantined: int = 0
