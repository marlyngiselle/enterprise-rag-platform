"""Azure AI Search index definition, as code.

Hybrid ready: full text fields with the Microsoft English analyzer, an HNSW vector field and
a semantic configuration. ``group_ids`` is the security field used for trimming: filterable,
never searchable, and populated only by the ingestion identity.
"""

from __future__ import annotations

from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
)

from rag.models import Chunk
from rag.retrieval.security import GROUP_FIELD

VECTOR_FIELD = "content_vector"
VECTOR_PROFILE = "hnsw-cosine"
SEMANTIC_CONFIG = "default"
SELECT_FIELDS = ["id", "source", "title", "section", "content", "position", GROUP_FIELD]


def build_index(name: str, dimensions: int) -> SearchIndex:
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SimpleField(
            name="source", type=SearchFieldDataType.String, filterable=True, facetable=True
        ),
        SearchableField(
            name="title", type=SearchFieldDataType.String, analyzer_name="en.microsoft"
        ),
        SearchableField(
            name="section", type=SearchFieldDataType.String, analyzer_name="en.microsoft"
        ),
        SearchableField(
            name="content", type=SearchFieldDataType.String, analyzer_name="en.microsoft"
        ),
        SimpleField(name="position", type=SearchFieldDataType.Int32, sortable=True),
        SimpleField(
            name=GROUP_FIELD,
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
        ),
        SearchField(
            name=VECTOR_FIELD,
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            hidden=True,
            vector_search_dimensions=dimensions,
            vector_search_profile_name=VECTOR_PROFILE,
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw",
                parameters=HnswParameters(
                    m=4,
                    ef_construction=400,
                    ef_search=500,
                    metric=VectorSearchAlgorithmMetric.COSINE,
                ),
            )
        ],
        profiles=[VectorSearchProfile(name=VECTOR_PROFILE, algorithm_configuration_name="hnsw")],
    )
    semantic = SemanticSearch(
        default_configuration_name=SEMANTIC_CONFIG,
        configurations=[
            SemanticConfiguration(
                name=SEMANTIC_CONFIG,
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="section"),
                    content_fields=[SemanticField(field_name="content")],
                    keywords_fields=[SemanticField(field_name="title")],
                ),
            )
        ],
    )
    return SearchIndex(
        name=name, fields=fields, vector_search=vector_search, semantic_search=semantic
    )


def to_search_document(chunk: Chunk) -> dict[str, object]:
    if not chunk.vector:
        msg = f"chunk {chunk.id} has no vector"
        raise ValueError(msg)
    return {
        "id": chunk.id,
        "source": chunk.source,
        "title": chunk.title,
        "section": chunk.section,
        "content": chunk.text,
        "position": chunk.position,
        GROUP_FIELD: list(chunk.acl_groups),
        VECTOR_FIELD: list(chunk.vector),
    }


def from_search_document(document: dict[str, object]) -> Chunk:
    groups = document.get(GROUP_FIELD) or []
    position = document.get("position")
    return Chunk(
        id=str(document["id"]),
        source=str(document.get("source", "")),
        title=str(document.get("title", "")),
        section=str(document.get("section", "")),
        text=str(document.get("content", "")),
        acl_groups=tuple(str(g) for g in groups) if isinstance(groups, list) else (),
        position=position if isinstance(position, int) else 0,
    )
