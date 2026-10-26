from __future__ import annotations

from pathlib import Path

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from rag.config import Settings
from rag.factory import Components, build_offline
from rag.models import Chunk, Document, Principal

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data" / "knowledge-base"
EVAL_SET = ROOT / "data" / "eval" / "qa.jsonl"
THRESHOLDS = ROOT / "data" / "eval" / "thresholds.toml"

# One global tracer provider for the whole session, with an in-memory exporter so tests can
# assert on spans. configure_telemetry() keeps an SDK provider that is already installed.
SPANS = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(SPANS))
trace.set_tracer_provider(_provider)


@pytest.fixture(scope="session")
def components() -> Components:
    return build_offline(Settings(knowledge_base_path=str(KB)))


@pytest.fixture
def spans() -> InMemorySpanExporter:
    SPANS.clear()
    return SPANS


@pytest.fixture
def employee() -> Principal:
    return Principal(user_id="u-employee", groups=("all-employees",))


@pytest.fixture
def engineer() -> Principal:
    return Principal(user_id="u-engineer", groups=("all-employees", "engineering"))


def make_chunk(
    cid: str,
    text: str,
    groups: tuple[str, ...] = ("all-employees",),
    source: str = "doc.md",
    section: str = "Section",
) -> Chunk:
    return Chunk(
        id=cid,
        source=source,
        title="Doc",
        section=section,
        text=text,
        acl_groups=groups,
        position=0,
    )


def make_document(text: str, groups: tuple[str, ...] = ("all-employees",)) -> Document:
    return Document(source="doc.md", title="Doc", text=text, acl_groups=groups)
