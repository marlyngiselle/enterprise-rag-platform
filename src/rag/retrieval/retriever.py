"""Hybrid retrieval with security trimming enforced twice: in the index and in the app."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from opentelemetry import trace

from rag.models import Principal, SearchHit, SearchRequest
from rag.providers import Embedder, SearchIndex
from rag.retrieval.security import is_visible, normalize_groups

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@dataclass
class Retriever:
    embedder: Embedder
    index: SearchIndex
    top_k: int = 5
    use_semantic_ranker: bool = True

    def retrieve(self, question: str, principal: Principal) -> list[SearchHit]:
        with tracer.start_as_current_span("rag.retrieve") as span:
            groups = normalize_groups(principal.groups)
            span.set_attribute("rag.groups.count", len(groups))
            if not groups:
                span.set_attribute("rag.hits", 0)
                return []
            vector = self.embedder.embed([question])[0]
            request = SearchRequest(
                text=question,
                vector=vector,
                groups=groups,
                top_k=self.top_k,
                use_semantic_ranker=self.use_semantic_ranker,
            )
            hits = self.index.search(request)
            visible = [h for h in hits if is_visible(h.chunk, groups)]
            dropped = len(hits) - len(visible)
            if dropped:
                # The index filter should make this impossible. If it happens, fail closed
                # and make it loud: it means the filter or the index schema is wrong.
                logger.error("security trimming dropped %d hits the index returned", dropped)
            span.set_attribute("rag.hits", len(visible))
            span.set_attribute("rag.security.dropped", dropped)
            return visible
