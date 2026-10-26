"""Wire the providers for a backend: ``offline`` (fakes, in memory) or ``azure``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rag.config import Settings
from rag.generation.service import AnswerService
from rag.ingestion.chunking import Chunker, HeadingChunker
from rag.ingestion.loaders import load_directory
from rag.ingestion.pipeline import IngestionPipeline, IngestionReport
from rag.providers import ChatModel, Embedder, SearchIndex
from rag.retrieval.retriever import Retriever


@dataclass
class Components:
    embedder: Embedder
    index: SearchIndex
    chat: ChatModel
    retriever: Retriever
    service: AnswerService
    ingestion: IngestionReport | None = None


def _assemble(
    settings: Settings, embedder: Embedder, index: SearchIndex, chat: ChatModel
) -> Components:
    retriever = Retriever(embedder=embedder, index=index, top_k=settings.top_k)
    service = AnswerService(
        retriever=retriever, chat=chat, min_reranker_score=settings.min_reranker_score
    )
    return Components(embedder, index, chat, retriever, service)


def build_offline(settings: Settings, chunker: Chunker | None = None) -> Components:
    """In-memory index loaded from the local knowledge base. No network, no credentials."""
    from rag.fakes import ExtractiveChatModel, HashingEmbedder, InMemorySearchIndex

    embedder = HashingEmbedder()
    index = InMemorySearchIndex()
    report = IngestionPipeline(chunker or HeadingChunker(), embedder, index).run(
        load_directory(Path(settings.knowledge_base_path))
    )
    components = _assemble(settings, embedder, index, ExtractiveChatModel())
    components.ingestion = report
    return components


def build_azure(settings: Settings) -> Components:
    from rag.azure.openai import AzureOpenAIChat, AzureOpenAIEmbedder, make_client
    from rag.azure.search import AzureSearchIndex, make_clients

    client = make_client(settings)
    search_client, _ = make_clients(settings)
    embedder = AzureOpenAIEmbedder(
        client, settings.embedding_deployment, settings.embedding_dimensions
    )
    index = AzureSearchIndex(search_client, settings.semantic_configuration)
    chat = AzureOpenAIChat(client, settings.chat_deployment)
    return _assemble(settings, embedder, index, chat)


def build_components(settings: Settings) -> Components:
    return build_azure(settings) if settings.backend == "azure" else build_offline(settings)
