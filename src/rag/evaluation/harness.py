"""Run an evaluation set through retrieval and generation, then score and gate the results."""

from __future__ import annotations

import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from rag.evaluation import metrics as m
from rag.evaluation.dataset import EvalCase
from rag.evaluation.judge import AnswerJudge, JudgeVerdict
from rag.generation.service import AnswerService
from rag.models import Principal
from rag.retrieval.retriever import Retriever


@dataclass(frozen=True)
class CaseResult:
    case: EvalCase
    retrieved_sources: tuple[str, ...]
    recall: float
    reciprocal_rank: float
    ndcg: float
    refused: bool
    refusal_reason: str | None
    answer: str
    citation_coverage: float
    groundedness: float
    term_recall: float
    access_violations: int
    quarantined: int = 0
    judge: JudgeVerdict | None = None

    @property
    def refusal_correct(self) -> bool:
        return self.refused != self.case.answerable


@dataclass(frozen=True)
class Summary:
    cases: int
    answerable: int
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    answer_rate: float
    citation_coverage: float
    groundedness: float
    term_recall: float
    refusal_accuracy: float
    access_violations: int
    quarantined_chunks: int

    def as_dict(self) -> dict[str, float]:
        return {
            "recall_at_k": self.recall_at_k,
            "mrr": self.mrr,
            "ndcg_at_k": self.ndcg_at_k,
            "answer_rate": self.answer_rate,
            "citation_coverage": self.citation_coverage,
            "groundedness": self.groundedness,
            "term_recall": self.term_recall,
            "refusal_accuracy": self.refusal_accuracy,
            "access_violations": float(self.access_violations),
            "quarantined_chunks": float(self.quarantined_chunks),
        }


@dataclass
class EvalReport:
    results: list[CaseResult]
    k: int
    label: str
    notes: list[str] = field(default_factory=list)

    @property
    def summary(self) -> Summary:
        answerable = [r for r in self.results if r.case.answerable]
        answered = [r for r in answerable if not r.refused]
        return Summary(
            cases=len(self.results),
            answerable=len(answerable),
            recall_at_k=m.mean([r.recall for r in answerable]),
            mrr=m.mean([r.reciprocal_rank for r in answerable]),
            ndcg_at_k=m.mean([r.ndcg for r in answerable]),
            answer_rate=len(answered) / len(answerable) if answerable else 0.0,
            citation_coverage=m.mean([r.citation_coverage for r in answered]),
            groundedness=m.mean([r.groundedness for r in answered]),
            term_recall=m.mean([r.term_recall for r in answered]),
            refusal_accuracy=m.mean([1.0 if r.refusal_correct else 0.0 for r in self.results]),
            access_violations=sum(r.access_violations for r in self.results),
            quarantined_chunks=sum(r.quarantined for r in self.results),
        )


def evaluate_case(
    case: EvalCase,
    retriever: Retriever,
    service: AnswerService,
    judge: AnswerJudge | None = None,
) -> CaseResult:
    principal = Principal(user_id=f"eval:{case.id}", groups=case.groups)
    hits = retriever.retrieve(case.question, principal)
    ranked = m.unique_sources(hits)
    k = retriever.top_k
    answer = service.answer(case.question, principal)
    answered = not answer.refused
    verdict = None
    if judge is not None and answered:
        verdict = judge.judge(case.question, answer.text, [h.chunk.text for h in answer.context])
    return CaseResult(
        case=case,
        retrieved_sources=tuple(ranked),
        recall=m.recall_at_k(ranked, case.relevant_sources, k),
        reciprocal_rank=m.reciprocal_rank(ranked, case.relevant_sources),
        ndcg=m.ndcg_at_k(ranked, case.relevant_sources, k),
        refused=answer.refused,
        refusal_reason=answer.refusal_reason,
        answer=answer.text,
        citation_coverage=m.citation_coverage(answer.text) if answered else 0.0,
        groundedness=(
            m.groundedness(answer.text, answer.citations, answer.context) if answered else 0.0
        ),
        term_recall=m.term_recall(answer.text, case.expected_terms) if answered else 0.0,
        access_violations=m.access_violations(hits, case.groups)
        + m.access_violations(answer.context, case.groups),
        quarantined=answer.quarantined,
        judge=verdict,
    )


def run_evaluation(
    cases: Sequence[EvalCase],
    retriever: Retriever,
    service: AnswerService,
    label: str = "offline",
    judge: AnswerJudge | None = None,
) -> EvalReport:
    results = [evaluate_case(c, retriever, service, judge) for c in cases]
    return EvalReport(results=results, k=retriever.top_k, label=label)


@dataclass(frozen=True)
class Thresholds:
    minimums: dict[str, float]
    max_access_violations: int = 0

    @classmethod
    def load(cls, path: Path) -> Thresholds:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        gate = data.get("gate", {})
        maximum = int(gate.pop("max_access_violations", 0))
        return cls(minimums={k: float(v) for k, v in gate.items()}, max_access_violations=maximum)


def check_gate(summary: Summary, thresholds: Thresholds) -> list[str]:
    """Return one message per failed threshold. An empty list means the gate passes."""
    values = summary.as_dict()
    failures = []
    for name, minimum in sorted(thresholds.minimums.items()):
        if name not in values:
            failures.append(f"unknown metric in thresholds: {name}")
        elif values[name] < minimum:
            failures.append(f"{name} = {values[name]:.3f} is below {minimum:.3f}")
    if summary.access_violations > thresholds.max_access_violations:
        failures.append(
            f"access_violations = {summary.access_violations} exceeds "
            f"{thresholds.max_access_violations}"
        )
    return failures
