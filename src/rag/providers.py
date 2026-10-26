"""Provider interfaces.

Every external dependency (embeddings, chat model, search index) sits behind a protocol, so
the whole pipeline runs offline with the fakes in ``rag.fakes`` and against Azure with the
adapters in ``rag.azure``.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from rag.models import Chunk, SearchHit, SearchRequest

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str


class Embedder(Protocol):
    @property
    def dimensions(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]: ...


class ChatModel(Protocol):
    def complete(self, messages: Sequence[ChatMessage]) -> str: ...

    def stream(self, messages: Sequence[ChatMessage]) -> Iterator[str]: ...


class SearchIndex(Protocol):
    def upsert(self, chunks: Sequence[Chunk]) -> int: ...

    def search(self, request: SearchRequest) -> list[SearchHit]: ...
