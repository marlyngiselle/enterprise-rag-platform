"""Optional LLM-as-judge interface.

The deterministic metrics gate CI. A judge adds a graded opinion on groundedness and
relevance when a model is available, and is never required for the gate to run.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from rag.providers import ChatMessage, ChatModel

JUDGE_PROMPT = """You grade an answer produced by a retrieval augmented assistant.
Score from 1 (worst) to 5 (best):
- groundedness: every claim in the answer is supported by the context.
- relevance: the answer addresses the question.
Return only JSON: {"groundedness": <int>, "relevance": <int>, "rationale": "<one sentence>"}"""


@dataclass(frozen=True)
class JudgeVerdict:
    groundedness: int
    relevance: int
    rationale: str


class AnswerJudge(Protocol):
    def judge(self, question: str, answer: str, contexts: Sequence[str]) -> JudgeVerdict: ...


def _score(value: object) -> int:
    if not isinstance(value, int | float | str):
        msg = f"score is not numeric: {value!r}"
        raise TypeError(msg)
    return max(1, min(5, round(float(value))))


@dataclass
class ChatModelJudge:
    """Any ``ChatModel`` can judge, typically a stronger deployment than the one answering."""

    model: ChatModel

    def judge(self, question: str, answer: str, contexts: Sequence[str]) -> JudgeVerdict:
        context = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(contexts, start=1))
        raw = self.model.complete(
            [
                ChatMessage("system", JUDGE_PROMPT),
                ChatMessage(
                    "user",
                    f"<question>{question}</question>\n<context>{context}</context>\n"
                    f"<answer>{answer}</answer>",
                ),
            ]
        )
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end < start:
            msg = "judge did not return JSON"
            raise ValueError(msg)
        data = json.loads(raw[start : end + 1])
        return JudgeVerdict(
            groundedness=_score(data.get("groundedness")),
            relevance=_score(data.get("relevance")),
            rationale=str(data.get("rationale", ""))[:300],
        )
