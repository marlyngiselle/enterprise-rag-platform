"""Azure adapters, tested against stand-in SDK clients: no network, no credentials."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from rag.azure.openai import AzureOpenAIChat, AzureOpenAIEmbedder, make_client
from rag.azure.search import AzureSearchIndex, ensure_index, make_clients
from rag.config import Settings
from rag.ingestion.index_schema import (
    VECTOR_FIELD,
    build_index,
    from_search_document,
    to_search_document,
)
from rag.models import SearchRequest
from rag.providers import ChatMessage
from tests.conftest import make_chunk


def test_index_schema_has_hybrid_semantic_and_security_fields() -> None:
    index = build_index("handbook", 1536)
    fields = {f.name: f for f in index.fields}
    assert fields["id"].key
    assert fields["group_ids"].filterable
    assert not fields["group_ids"].searchable
    assert fields[VECTOR_FIELD].vector_search_dimensions == 1536
    assert fields[VECTOR_FIELD].hidden
    assert fields["content"].analyzer_name == "en.microsoft"
    assert index.vector_search is not None
    assert index.vector_search.profiles is not None
    assert index.vector_search.profiles[0].algorithm_configuration_name == "hnsw"
    assert index.semantic_search is not None
    assert index.semantic_search.configurations is not None
    semantic = index.semantic_search.configurations[0].prioritized_fields
    assert semantic.title_field is not None
    assert semantic.title_field.field_name == "section"


def test_search_document_round_trip() -> None:
    chunk = make_chunk("k1", "text", groups=("a", "b")).with_vector((0.1, 0.2))
    document = to_search_document(chunk)
    assert document["group_ids"] == ["a", "b"]
    back = from_search_document({k: v for k, v in document.items() if k != VECTOR_FIELD})
    assert back.acl_groups == ("a", "b")
    assert back.text == "text"
    with pytest.raises(ValueError, match="no vector"):
        to_search_document(make_chunk("k2", "t"))


class FakeSearchClient:
    def __init__(self, results: list[dict[str, Any]], fail: bool = False) -> None:
        self.results = results
        self.fail = fail
        self.calls: list[dict[str, Any]] = []
        self.uploaded: list[list[dict[str, object]]] = []

    def search(self, **options: Any) -> list[dict[str, Any]]:
        self.calls.append(options)
        return self.results

    def merge_or_upload_documents(self, documents: list[dict[str, object]]) -> list[Any]:
        self.uploaded.append(documents)
        return [SimpleNamespace(key=d["id"], succeeded=not self.fail) for d in documents]


def test_hybrid_query_uses_prefilter_and_semantic_ranker() -> None:
    client = FakeSearchClient(
        [
            {
                "id": "1",
                "source": "a.md",
                "title": "A",
                "section": "S",
                "content": "c",
                "position": 0,
                "group_ids": ["all-employees"],
                "@search.score": 0.03,
                "@search.reranker_score": 2.5,
            },
        ]
    )
    index = AzureSearchIndex(client)  # type: ignore[arg-type]
    hits = index.search(SearchRequest("leave", (0.1, 0.2), ("all-employees",), top_k=3))
    options = client.calls[0]
    assert options["filter"] == "group_ids/any(g: search.in(g, 'all-employees', ','))"
    assert options["vector_filter_mode"] == "preFilter"
    assert options["query_type"] == "semantic"
    assert options["top"] == 3
    assert options["vector_queries"][0].fields == VECTOR_FIELD
    assert hits[0].reranker_score == 2.5
    assert hits[0].chunk.acl_groups == ("all-employees",)


def test_semantic_ranker_off_sends_a_simple_query() -> None:
    client = FakeSearchClient([])
    AzureSearchIndex(client).search(  # type: ignore[arg-type]
        SearchRequest("q", (0.1,), ("g",), use_semantic_ranker=False)
    )
    assert "query_type" not in client.calls[0]


def test_upload_raises_on_failed_documents() -> None:
    chunk = make_chunk("k", "t").with_vector((0.1,))
    assert AzureSearchIndex(FakeSearchClient([])).upsert([chunk]) == 1  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="failed to index"):
        AzureSearchIndex(FakeSearchClient([], fail=True)).upsert([chunk])  # type: ignore[arg-type]


def test_ensure_index_sends_the_schema() -> None:
    sent: list[Any] = []
    ensure_index(SimpleNamespace(create_or_update_index=sent.append), "idx", 8)  # type: ignore[arg-type]
    assert sent[0].name == "idx"


@dataclass
class FakeEmbeddings:
    calls: list[dict[str, Any]]

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        items = [
            SimpleNamespace(index=i, embedding=[float(i)]) for i in range(len(kwargs["input"]))
        ]
        return SimpleNamespace(data=list(reversed(items)))


def test_embedder_batches_and_restores_order() -> None:
    calls: list[dict[str, Any]] = []
    client = SimpleNamespace(embeddings=FakeEmbeddings(calls))
    embedder = AzureOpenAIEmbedder(client, "embedding", 256, batch_size=2)  # type: ignore[arg-type]
    vectors = embedder.embed(["a", "b", "c"])
    assert vectors == [(0.0,), (1.0,), (0.0,)]
    assert [len(c["input"]) for c in calls] == [2, 1]
    assert calls[0]["dimensions"] == 256
    assert embedder.dimensions == 256


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return iter(
                [
                    SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hi"))]),
                    SimpleNamespace(choices=[]),
                    SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content=" [1]."))]
                    ),
                ]
            )
        message = SimpleNamespace(content="Answer [1].")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_chat_complete_and_stream() -> None:
    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    chat = AzureOpenAIChat(client, "chat")  # type: ignore[arg-type]
    messages = [ChatMessage("system", "s"), ChatMessage("user", "u"), ChatMessage("assistant", "a")]
    assert chat.complete(messages) == "Answer [1]."
    assert "".join(chat.stream(messages)) == "Hi [1]."
    assert completions.calls[0]["temperature"] == 0.0
    assert [m["role"] for m in completions.calls[0]["messages"]] == ["system", "user", "assistant"]


def test_azure_backend_requires_endpoints() -> None:
    with pytest.raises(ValueError, match="RAG_OPENAI_ENDPOINT"):
        make_client(Settings(backend="azure"))
    with pytest.raises(ValueError, match="RAG_SEARCH_ENDPOINT"):
        make_clients(Settings(backend="azure"))
