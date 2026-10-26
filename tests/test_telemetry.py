from __future__ import annotations

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from rag.api.app import create_app
from rag.config import Settings
from rag.factory import Components
from rag.models import Principal

QUESTION = "What is the hotel cap per night in capital cities?"


def test_answer_emits_spans_with_counts_not_content(
    components: Components, employee: Principal, spans: InMemorySpanExporter
) -> None:
    components.service.answer(QUESTION, employee)
    by_name = {s.name: s for s in spans.get_finished_spans()}
    assert {"rag.answer", "rag.retrieve", "rag.generate"} <= set(by_name)
    retrieve = by_name["rag.retrieve"]
    assert retrieve.parent is not None
    assert retrieve.parent.span_id == by_name["rag.answer"].context.span_id
    attributes = dict(by_name["rag.answer"].attributes or {})
    assert attributes["rag.refused"] is False
    assert attributes["rag.citations"] == 1
    for span in spans.get_finished_spans():
        assert all(QUESTION not in str(v) for v in (span.attributes or {}).values())


def test_stream_span_parents_retrieval_and_ends(
    components: Components, employee: Principal, spans: InMemorySpanExporter
) -> None:
    list(components.service.stream(QUESTION, employee))
    by_name = {s.name: s for s in spans.get_finished_spans()}
    stream_span = by_name["rag.answer.stream"]
    assert by_name["rag.retrieve"].parent is not None
    assert by_name["rag.retrieve"].parent.span_id == stream_span.context.span_id
    assert dict(stream_span.attributes or {})["rag.refused"] is False


def test_http_request_span_carries_request_id(
    components: Components, spans: InMemorySpanExporter
) -> None:
    client = TestClient(create_app(Settings(auth_mode="dev-headers"), components))
    client.post(
        "/v1/ask",
        json={"question": QUESTION},
        headers={"x-user-id": "u", "x-user-groups": "all-employees", "x-request-id": "trace-0001"},
    )
    request_ids = {(s.attributes or {}).get("request.id") for s in spans.get_finished_spans()}
    assert "trace-0001" in request_ids
