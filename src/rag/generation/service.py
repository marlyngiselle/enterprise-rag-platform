"""The answer service: guard, retrieve, gate, generate, verify.

1. The question is screened for prompt injection and its PII is masked.
2. Retrieval runs with the caller's groups, so only documents they may read are candidates.
3. Retrieved chunks that carry injected instructions are quarantined.
4. If nothing relevant is left, the service refuses before calling the model.
5. The answer is checked: unknown citation markers are removed, PII is masked, and an answer
   that cites nothing is replaced by a refusal.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

from opentelemetry import trace
from opentelemetry.trace import Span

from rag.generation.guards import PiiRedactor, PromptInjectionGuard, Redactor
from rag.generation.prompts import REFUSAL_TEXT, build_messages
from rag.models import Answer, Citation, Principal, SearchHit
from rag.providers import ChatMessage, ChatModel
from rag.retrieval.citations import build_citations, unknown_markers, used_citations
from rag.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

BLOCKED_TEXT = "I can't help with that request."
RefusalReason = Literal["blocked_input", "insufficient_context", "model_refusal", "ungrounded"]
_SENTENCE_END = re.compile(r"[.!?](?:\s|$)")


@dataclass(frozen=True)
class StreamEvent:
    event: Literal["sources", "token", "done"]
    data: dict[str, object]


@dataclass(frozen=True)
class _Prepared:
    hits: tuple[SearchHit, ...]
    citations: tuple[Citation, ...]
    messages: tuple[ChatMessage, ...]
    quarantined: int = 0


def _refusal(
    reason: RefusalReason, hits: tuple[SearchHit, ...] = (), quarantined: int = 0
) -> Answer:
    text = BLOCKED_TEXT if reason == "blocked_input" else REFUSAL_TEXT
    return Answer(
        text=text,
        citations=(),
        refused=True,
        refusal_reason=reason,
        context=hits,
        quarantined=quarantined,
    )


def citation_payload(citations: tuple[Citation, ...] | list[Citation]) -> list[dict[str, object]]:
    return [
        {"marker": c.marker, "source": c.source, "title": c.title, "section": c.section}
        for c in citations
    ]


@dataclass
class AnswerService:
    retriever: Retriever
    chat: ChatModel
    guard: PromptInjectionGuard = field(default_factory=PromptInjectionGuard)
    redactor: Redactor = field(default_factory=PiiRedactor)
    min_reranker_score: float = 1.2

    def _prepare(self, question: str, principal: Principal, span: Span) -> _Prepared | Answer:
        verdict = self.guard.check(question)
        if not verdict.allowed:
            span.set_attribute("rag.guard.input", verdict.reason or "blocked")
            return _refusal("blocked_input")
        redaction = self.redactor.redact(question)
        span.set_attribute("rag.pii.question_redactions", redaction.total)

        hits = self.retriever.retrieve(redaction.text, principal)
        clean, quarantined = self.guard.filter_context(hits)
        span.set_attribute("rag.guard.quarantined_chunks", len(quarantined))
        if quarantined:
            logger.warning(
                "quarantined %d chunk(s) with injected instructions: %s",
                len(quarantined),
                sorted({h.chunk.source for h in quarantined}),
            )
        relevant = tuple(
            h
            for h in clean
            if h.reranker_score is None or h.reranker_score >= self.min_reranker_score
        )
        if not relevant:
            return _refusal("insufficient_context", tuple(clean), len(quarantined))
        return _Prepared(
            hits=relevant,
            citations=tuple(build_citations(relevant)),
            messages=tuple(build_messages(redaction.text, relevant)),
            quarantined=len(quarantined),
        )

    def _finalize(self, raw: str, prepared: _Prepared) -> Answer:
        if REFUSAL_TEXT.rstrip(".") in raw:
            return _refusal("model_refusal", prepared.hits, prepared.quarantined)
        text = self.redactor.redact(raw).text
        for marker in unknown_markers(text, prepared.citations):
            logger.warning("removed citation [%d] that points at no source", marker)
            text = text.replace(f"[{marker}]", "")
        used = used_citations(text, prepared.citations)
        if not used:
            return _refusal("ungrounded", prepared.hits, prepared.quarantined)
        return Answer(
            text=text.strip(),
            citations=tuple(used),
            refused=False,
            context=prepared.hits,
            quarantined=prepared.quarantined,
        )

    def answer(self, question: str, principal: Principal) -> Answer:
        with tracer.start_as_current_span("rag.answer") as span:
            prepared = self._prepare(question, principal, span)
            if isinstance(prepared, Answer):
                result = prepared
            else:
                with tracer.start_as_current_span("rag.generate"):
                    raw = self.chat.complete(prepared.messages)
                result = self._finalize(raw, prepared)
            span.set_attribute("rag.refused", result.refused)
            span.set_attribute("rag.refusal_reason", result.refusal_reason or "")
            span.set_attribute("rag.citations", len(result.citations))
            return result

    def stream(self, question: str, principal: Principal) -> Iterator[StreamEvent]:
        """Stream sentence by sentence, so PII redaction always sees whole sentences.

        The final ``done`` event carries the verdict of the same checks ``answer`` runs. A
        client must render the refusal if ``done`` says the streamed text was not grounded.
        """
        # A generator may resume in another thread or context, so the span is never made
        # current across a yield. It is activated only around the synchronous preparation.
        span = tracer.start_span("rag.answer.stream")
        try:
            with trace.use_span(span, end_on_exit=False):
                prepared = self._prepare(question, principal, span)
            if isinstance(prepared, Answer):
                span.set_attribute("rag.refused", True)
                yield StreamEvent("token", {"text": prepared.text})
                yield StreamEvent(
                    "done",
                    {"refused": True, "refusal_reason": prepared.refusal_reason, "citations": []},
                )
                return
            yield StreamEvent("sources", {"citations": citation_payload(prepared.citations)})
            buffer = ""
            full = ""
            for token in self.chat.stream(prepared.messages):
                buffer += token
                full += token
                cut = max((m.end() for m in _SENTENCE_END.finditer(buffer)), default=0)
                if cut:
                    yield StreamEvent("token", {"text": self.redactor.redact(buffer[:cut]).text})
                    buffer = buffer[cut:]
            if buffer:
                yield StreamEvent("token", {"text": self.redactor.redact(buffer).text})
            result = self._finalize(full, prepared)
            span.set_attribute("rag.refused", result.refused)
            span.set_attribute("rag.refusal_reason", result.refusal_reason or "")
            yield StreamEvent(
                "done",
                {
                    "refused": result.refused,
                    "refusal_reason": result.refusal_reason,
                    "citations": citation_payload(result.citations),
                },
            )
        finally:
            span.end()
