"""Offline providers: deterministic, dependency free, good enough to test the pipeline.

``HashingEmbedder`` and ``InMemorySearchIndex`` reproduce the shape of Azure AI Search hybrid
retrieval (BM25 plus vectors, fused with reciprocal rank fusion, then a reranking pass) so the
security trimming, fusion and evaluation code paths are exercised for real. The numbers they
produce describe this offline stack, not the quality of the Azure models.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from itertools import pairwise

from rag.generation.prompts import REFUSAL_TEXT
from rag.models import Chunk, SearchHit, SearchRequest
from rag.providers import ChatMessage
from rag.retrieval.fusion import reciprocal_rank_fusion
from rag.retrieval.security import is_visible
from rag.text import split_sentences, tokenize

_CONTEXT_BLOCK = re.compile(r'<source id="(?P<id>\d+)"[^>]*>\n(?P<body>.*?)\n</source>', re.DOTALL)
_QUESTION = re.compile(r"<question>\n(?P<q>.*?)\n</question>", re.DOTALL)


@dataclass(frozen=True)
class HashingEmbedder:
    """Feature hashing of unigrams and bigrams into a fixed size, L2 normalised vector."""

    size: int = 256

    @property
    def dimensions(self) -> int:
        return self.size

    def _embed_one(self, text: str) -> tuple[float, ...]:
        tokens = tokenize(text)
        features = tokens + [f"{a}_{b}" for a, b in pairwise(tokens)]
        vector = [0.0] * self.size
        for feature in features:
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.size
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return tuple(v / norm for v in vector)

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return [self._embed_one(t) for t in texts]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


@dataclass
class InMemorySearchIndex:
    """Hybrid search over a dict, with the same security contract as the Azure index."""

    k1: float = 1.2
    b: float = 0.75
    fusion_depth: int = 50
    _chunks: dict[str, Chunk] = field(default_factory=dict)
    _terms: dict[str, Counter[str]] = field(default_factory=dict)

    def upsert(self, chunks: Sequence[Chunk]) -> int:
        for chunk in chunks:
            self._chunks[chunk.id] = chunk
            self._terms[chunk.id] = Counter(tokenize(f"{chunk.section} {chunk.text}"))
        return len(chunks)

    def __len__(self) -> int:
        return len(self._chunks)

    def _idf(self, term: str) -> float:
        n = len(self._chunks)
        df = sum(1 for terms in self._terms.values() if term in terms)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _bm25(self, query_terms: list[str], ids: list[str]) -> list[str]:
        if not self._terms:
            return []
        avgdl = sum(sum(t.values()) for t in self._terms.values()) / len(self._terms)
        idf = {t: self._idf(t) for t in set(query_terms)}
        scores: dict[str, float] = {}
        for cid in ids:
            terms = self._terms[cid]
            length = sum(terms.values())
            score = 0.0
            for term in query_terms:
                tf = terms.get(term, 0)
                if tf:
                    denom = tf + self.k1 * (1 - self.b + self.b * length / avgdl)
                    score += idf[term] * tf * (self.k1 + 1) / denom
            if score > 0:
                scores[cid] = score
        return sorted(scores, key=lambda c: (-scores[c], c))

    def _vector(self, vector: Sequence[float], ids: list[str]) -> list[str]:
        if not vector:
            return []
        scored = [(cid, _cosine(vector, self._chunks[cid].vector)) for cid in ids]
        scored = [(cid, s) for cid, s in scored if s > 0]
        return [cid for cid, _ in sorted(scored, key=lambda x: (-x[1], x[0]))]

    def _rerank_score(self, query_terms: list[str], cid: str) -> float:
        """Stand-in for the semantic ranker: IDF weighted query coverage on a 0 to 4 scale."""
        unique = set(query_terms)
        total = sum(self._idf(t) for t in unique)
        if total == 0:
            return 0.0
        covered = sum(self._idf(t) for t in unique if t in self._terms[cid])
        return round(4.0 * covered / total, 4)

    def search(self, request: SearchRequest) -> list[SearchHit]:
        # Security trimming happens before ranking, as a pre-filter does in Azure AI Search.
        allowed = [cid for cid, c in self._chunks.items() if is_visible(c, request.groups)]
        query_terms = tokenize(request.text)
        lexical = self._bm25(query_terms, allowed)[: self.fusion_depth]
        semantic = self._vector(request.vector, allowed)[: self.fusion_depth]
        fused = reciprocal_rank_fusion([lexical, semantic])
        hits = [SearchHit(self._chunks[cid], score) for cid, score in fused]
        if request.use_semantic_ranker:
            hits = [
                SearchHit(h.chunk, h.score, self._rerank_score(query_terms, h.chunk.id))
                for h in hits
            ]
            hits.sort(key=lambda h: (-(h.reranker_score or 0.0), -h.score))
        return hits[: request.top_k]


class ExtractiveChatModel:
    """A deterministic stand-in for the chat model.

    It reads the grounded prompt, picks the source sentences that overlap most with the
    question and returns them with their citation markers, or the refusal text when nothing
    overlaps. It lets the evaluation harness measure citation and grounding logic offline.
    """

    def __init__(self, max_sentences: int = 2, min_overlap: int = 1) -> None:
        self.max_sentences = max_sentences
        self.min_overlap = min_overlap

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        prompt = messages[-1].content
        question_match = _QUESTION.search(prompt)
        question = set(tokenize(question_match.group("q") if question_match else ""))
        candidates: list[tuple[int, int, int, str]] = []
        for order, block in enumerate(_CONTEXT_BLOCK.finditer(prompt)):
            marker = int(block.group("id"))
            for position, sentence in enumerate(split_sentences(block.group("body"))):
                overlap = len(question & set(tokenize(sentence)))
                if overlap >= self.min_overlap:
                    candidates.append((-overlap, order * 1000 + position, marker, sentence))
        if not candidates:
            return REFUSAL_TEXT
        best = sorted(candidates)[: self.max_sentences]
        best.sort(key=lambda c: c[1])
        return " ".join(
            f"{sentence.rstrip().rstrip('.!?')} [{marker}]." for _, _, marker, sentence in best
        )

    def stream(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        text = self.complete(messages)
        for index, word in enumerate(text.split(" ")):
            yield word if index == 0 else f" {word}"
