"""Small, dependency free text utilities shared by the fakes and the evaluation metrics."""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\[(\"])")
_MARKER = re.compile(r"\[(\d{1,3})\]")

_STOPWORD_TEXT = """
    a about above after again all am an and any are as at be because been before being
    below between both but by can could did do does doing down during each few for from
    further had has have having he her here hers him his how i if in into is it its itself
    just me more most my no nor not now of off on once only or other our ours out over own
    same she should so some such than that the their theirs them then there these they this
    those through to too under until up very was we were what when where which while who
    whom why will with would you your yours yourself i'm can't don't i'd"""
STOPWORDS = frozenset(_STOPWORD_TEXT.split())


def stem(word: str) -> str:
    """Very light stemming, enough to match plural and gerund forms in a handbook."""
    for suffix, min_len in (("ies", 5), ("ing", 6), ("ed", 5), ("es", 5), ("s", 4)):
        if word.endswith(suffix) and len(word) >= min_len:
            if suffix == "ies":
                return word[:-3] + "y"
            if suffix == "s" and word.endswith("ss"):
                return word
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    """Lowercase content words, stopwords removed, lightly stemmed."""
    return [stem(w) for w in _WORD.findall(text.lower()) if w not in STOPWORDS]


def split_sentences(text: str) -> list[str]:
    flat = " ".join(line.strip("-* ").strip() for line in text.splitlines() if line.strip())
    return [s.strip() for s in _SENTENCE.split(flat) if s.strip()]


def citation_markers(text: str) -> list[int]:
    return [int(m) for m in _MARKER.findall(text)]


def strip_markers(text: str) -> str:
    return _MARKER.sub("", text).strip()
