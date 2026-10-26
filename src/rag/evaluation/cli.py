"""``rag-eval``: offline evaluation with a regression gate for CI."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from rag.config import Settings
from rag.evaluation.dataset import load_eval_set
from rag.evaluation.harness import Thresholds, check_gate, run_evaluation
from rag.evaluation.report import render_markdown
from rag.factory import build_azure, build_offline
from rag.ingestion.chunking import FixedSizeChunker, HeadingChunker

OFFLINE_NOTE = (
    "Offline run: hashing embedder, in-memory hybrid index (BM25 + vectors + RRF + rerank "
    "stand-in) and an extractive generator. The numbers measure the pipeline logic on the "
    "synthetic set, not the quality of Azure OpenAI or Azure AI Search."
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb", type=Path, default=Path("data/knowledge-base"))
    parser.add_argument("--eval-set", type=Path, default=Path("data/eval/qa.jsonl"))
    parser.add_argument("--thresholds", type=Path, default=Path("data/eval/thresholds.toml"))
    parser.add_argument("--report", type=Path, default=Path("reports/eval-report.md"))
    parser.add_argument("--chunker", choices=["heading", "fixed"], default="heading")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--backend", choices=["offline", "azure"], default="offline")
    parser.add_argument("--no-gate", action="store_true", help="report only, never fail")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.ERROR)

    settings = Settings(backend=args.backend, knowledge_base_path=str(args.kb), top_k=args.top_k)
    if args.backend == "azure":
        components = build_azure(settings)
        label, notes = "azure", []
    else:
        chunker = FixedSizeChunker() if args.chunker == "fixed" else HeadingChunker()
        components = build_offline(settings, chunker)
        label, notes = f"offline, {args.chunker} chunking", [OFFLINE_NOTE]
        if components.ingestion:
            ing = components.ingestion
            notes.append(
                f"Knowledge base: {ing.documents} documents indexed, {ing.chunks} chunks, "
                f"{len(ing.skipped)} skipped for missing ACL."
            )

    cases = load_eval_set(args.eval_set)
    report = run_evaluation(cases, components.retriever, components.service, label=label)
    report.notes.extend(notes)
    thresholds = Thresholds.load(args.thresholds) if args.thresholds.exists() else None

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_markdown(report, thresholds), encoding="utf-8")

    summary = report.summary
    for key, value in summary.as_dict().items():
        print(f"{key:20s} {value:.3f}")
    print(f"report: {args.report}")
    failures = check_gate(summary, thresholds) if thresholds else []
    for failure in failures:
        print(f"GATE FAIL: {failure}", file=sys.stderr)
    return 1 if failures and not args.no_gate else 0


if __name__ == "__main__":
    sys.exit(main())
