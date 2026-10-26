"""Azure AI Search adapter: hybrid query, semantic ranker, security filter as a pre-filter."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery

from rag.ingestion.index_schema import (
    SELECT_FIELDS,
    VECTOR_FIELD,
    build_index,
    from_search_document,
    to_search_document,
)
from rag.models import Chunk, SearchHit, SearchRequest
from rag.retrieval.security import build_security_filter

if TYPE_CHECKING:
    from rag.config import Settings

UPLOAD_BATCH = 500


def make_clients(settings: Settings) -> tuple[SearchClient, SearchIndexClient]:
    if not settings.search_endpoint:
        msg = "RAG_SEARCH_ENDPOINT is required for the azure backend"
        raise ValueError(msg)
    credential = DefaultAzureCredential()
    return (
        SearchClient(settings.search_endpoint, settings.search_index, credential),
        SearchIndexClient(settings.search_endpoint, credential),
    )


def ensure_index(index_client: SearchIndexClient, name: str, dimensions: int) -> None:
    """Create or update the index from the schema in code. Needs Search Service Contributor."""
    index_client.create_or_update_index(build_index(name, dimensions))


@dataclass
class AzureSearchIndex:
    client: SearchClient
    semantic_configuration: str = "default"
    knn: int = 50

    def upsert(self, chunks: Sequence[Chunk]) -> int:
        uploaded = 0
        for start in range(0, len(chunks), UPLOAD_BATCH):
            batch = [to_search_document(c) for c in chunks[start : start + UPLOAD_BATCH]]
            results = self.client.merge_or_upload_documents(documents=batch)
            failed = [r.key for r in results if not r.succeeded]
            if failed:
                msg = f"{len(failed)} documents failed to index, first: {failed[0]}"
                raise RuntimeError(msg)
            uploaded += len(batch)
        return uploaded

    def search(self, request: SearchRequest) -> list[SearchHit]:
        options: dict[str, Any] = {
            "search_text": request.text,
            "vector_queries": [
                VectorizedQuery(
                    vector=list(request.vector), k_nearest_neighbors=self.knn, fields=VECTOR_FIELD
                )
            ],
            "filter": build_security_filter(request.groups),
            "vector_filter_mode": "preFilter",
            "select": SELECT_FIELDS,
            "top": request.top_k,
        }
        if request.use_semantic_ranker:
            options["query_type"] = "semantic"
            options["semantic_configuration_name"] = self.semantic_configuration
        hits = []
        for result in self.client.search(**options):
            hits.append(
                SearchHit(
                    chunk=from_search_document(dict(result)),
                    score=float(result.get("@search.score") or 0.0),
                    reranker_score=result.get("@search.reranker_score"),
                )
            )
        return hits
