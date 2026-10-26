"""Ingestion pipeline: chunk, embed in batches, push to the index. Fails closed on ACLs."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

from rag.ingestion.chunking import Chunker
from rag.models import Chunk, Document
from rag.providers import Embedder, SearchIndex

logger = logging.getLogger(__name__)


def embedding_input(chunk: Chunk) -> str:
    """Text sent to the embedding model: the heading path gives a short chunk its context."""
    return f"{chunk.title} | {chunk.section}\n{chunk.text}"


@dataclass
class IngestionReport:
    documents: int = 0
    chunks: int = 0
    skipped: list[str] = field(default_factory=list)
    per_source: dict[str, int] = field(default_factory=dict)


@dataclass
class IngestionPipeline:
    chunker: Chunker
    embedder: Embedder
    index: SearchIndex
    batch_size: int = 16

    def run(self, documents: Sequence[Document]) -> IngestionReport:
        report = IngestionReport()
        pending: list[Chunk] = []
        for document in documents:
            if not document.acl_groups:
                logger.warning(
                    "skipped %s: no acl_groups, access control fails closed", document.source
                )
                report.skipped.append(document.source)
                continue
            chunks = self.chunker.split(document)
            report.documents += 1
            report.per_source[document.source] = len(chunks)
            pending.extend(chunks)

        for start in range(0, len(pending), self.batch_size):
            batch = pending[start : start + self.batch_size]
            vectors = self.embedder.embed([embedding_input(c) for c in batch])
            if len(vectors) != len(batch):
                msg = f"embedder returned {len(vectors)} vectors for {len(batch)} inputs"
                raise RuntimeError(msg)
            report.chunks += self.index.upsert(
                [c.with_vector(v) for c, v in zip(batch, vectors, strict=True)]
            )
        return report
