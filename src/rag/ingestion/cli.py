"""``rag-ingest``: load a folder, chunk it and push it to the index of the chosen backend."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from rag.config import Settings
from rag.ingestion.chunking import Chunker, FixedSizeChunker, HeadingChunker
from rag.ingestion.loaders import load_directory
from rag.ingestion.pipeline import IngestionPipeline


def _chunker(name: str, max_words: int, overlap: int) -> Chunker:
    if name == "fixed":
        return FixedSizeChunker(max_words, overlap)
    return HeadingChunker(max_words, overlap)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb", type=Path, default=Path("data/knowledge-base"))
    parser.add_argument("--chunker", choices=["heading", "fixed"], default="heading")
    parser.add_argument("--max-words", type=int, default=180)
    parser.add_argument("--overlap", type=int, default=30)
    parser.add_argument("--backend", choices=["offline", "azure"], default="offline")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = Settings(backend=args.backend)
    if args.backend == "azure":
        from rag.azure.openai import AzureOpenAIEmbedder, make_client
        from rag.azure.search import AzureSearchIndex, ensure_index, make_clients

        search_client, index_client = make_clients(settings)
        ensure_index(index_client, settings.search_index, settings.embedding_dimensions)
        pipeline = IngestionPipeline(
            _chunker(args.chunker, args.max_words, args.overlap),
            AzureOpenAIEmbedder(
                make_client(settings),
                settings.embedding_deployment,
                settings.embedding_dimensions,
            ),
            AzureSearchIndex(search_client, settings.semantic_configuration),
        )
    else:
        from rag.fakes import HashingEmbedder, InMemorySearchIndex

        pipeline = IngestionPipeline(
            _chunker(args.chunker, args.max_words, args.overlap),
            HashingEmbedder(),
            InMemorySearchIndex(),
        )

    report = pipeline.run(load_directory(args.kb))
    for source, count in sorted(report.per_source.items()):
        print(f"{count:4d}  {source}")
    print(f"{report.documents} documents, {report.chunks} chunks, {len(report.skipped)} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
