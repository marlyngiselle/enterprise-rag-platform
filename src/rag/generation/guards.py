"""Guard hooks: prompt injection detection and PII redaction.

These are deterministic first lines of defence, cheap enough to run on every request and on
every retrieved chunk. They sit behind small protocols so a managed service (Azure AI Content
Safety Prompt Shields, a PII detection endpoint) can replace or complement them.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from rag.models import SearchHit


@dataclass(frozen=True)
class GuardVerdict:
    allowed: bool
    reason: str | None = None


class InputGuard(Protocol):
    def check(self, text: str) -> GuardVerdict: ...


@dataclass(frozen=True)
class Redaction:
    text: str
    counts: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.counts.values())


class Redactor(Protocol):
    def redact(self, text: str) -> Redaction: ...


_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        (
            "override",
            r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier|"
            r"all|any|your|the|system)\b.{0,40}\b(instructions?|rules|prompts?|guidelines)",
        ),
        ("role_change", r"\byou are now\b|\bact as (an? )?(unrestricted|jailbroken|dan)\b"),
        (
            "prompt_leak",
            r"\b(reveal|print|show|repeat|output)\b.{0,30}\b(system prompt|your instructions|"
            r"hidden rules|initial prompt)",
        ),
        ("mode_switch", r"\b(developer|god|jailbreak|dan) mode\b"),
        ("chat_markup", r"<\|im_start\|>|<\|system\|>|\[/?INST\]|###\s*system\s*:"),
        (
            "exfiltration",
            r"!\[[^\]]*\]\(https?://[^)]*\?[^)]*=|\b(send|post|forward|email)\b.{0,40}"
            r"\b(to|at)\b.{0,20}(https?://|[\w.+-]+@[\w-]+\.)",
        ),
    )
)


@dataclass(frozen=True)
class PromptInjectionGuard:
    """Pattern based detector for direct (question) and indirect (document) injection."""

    max_chars: int = 2000

    def check(self, text: str) -> GuardVerdict:
        if len(text) > self.max_chars:
            return GuardVerdict(False, "too_long")
        for name, pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                return GuardVerdict(False, f"prompt_injection:{name}")
        return GuardVerdict(True)

    def filter_context(self, hits: Sequence[SearchHit]) -> tuple[list[SearchHit], list[SearchHit]]:
        """Split hits into clean and quarantined. Quarantined chunks never reach the prompt."""
        clean: list[SearchHit] = []
        quarantined: list[SearchHit] = []
        for hit in hits:
            verdict = self.check(hit.chunk.text[: self.max_chars])
            (clean if verdict.allowed else quarantined).append(hit)
        return clean, quarantined


_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b")),
    ("card", re.compile(r"\b(?:\d[ -]?){12,18}\d\b")),
    ("phone", re.compile(r"(?<![\w+])\+\d{1,3}(?:[ .-]?\(?\d{1,4}\)?){2,5}(?!\w)")),
)


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, char in enumerate(reversed(digits)):
        n = int(char)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


@dataclass(frozen=True)
class PiiRedactor:
    """Masks e-mail addresses, international phone numbers, IBANs and payment card numbers.

    Stateless and thread safe. Patterns favour precision: a date or an amount must never be
    masked in an answer, so phone numbers are only matched in international format and card
    numbers only when they pass the Luhn check.
    """

    def redact(self, text: str) -> Redaction:
        counts: dict[str, int] = {}

        def masker(kind: str) -> Callable[[re.Match[str]], str]:
            def repl(match: re.Match[str]) -> str:
                if kind == "card":
                    digits = re.sub(r"\D", "", match.group())
                    if not (13 <= len(digits) <= 19 and _luhn_ok(digits)):
                        return match.group()
                counts[kind] = counts.get(kind, 0) + 1
                return f"[REDACTED_{kind.upper()}]"

            return repl

        for kind, pattern in _PII_PATTERNS:
            text = pattern.sub(masker(kind), text)
        return Redaction(text, counts)
