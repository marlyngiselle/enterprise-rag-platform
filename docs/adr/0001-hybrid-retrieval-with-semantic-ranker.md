# ADR 0001: Hybrid retrieval with semantic reranking

Status: accepted

## Context

Employee questions mix exact identifiers (SEV1, a form name, an amount) with paraphrase ("when will my pay rise show up"). Pure vector search misses exact tokens and acronyms. Pure keyword search misses paraphrase. Both return a long tail that wastes prompt tokens.

## Decision

Every query runs BM25 and a vector query in one request to Azure AI Search, fused with reciprocal rank fusion, then reranked by the semantic ranker. Only chunks above a reranker score threshold reach the prompt. If none does, the service refuses before calling the model.

## Consequences

1. Better recall on mixed queries, and a calibrated relevance score (0 to 4) to decide when to refuse.
2. The semantic ranker needs the basic tier or higher, and the standard plan for production volume.
3. Latency rises by the reranking step, typically tens of milliseconds for 50 candidates.
4. The refusal threshold becomes a tuning parameter. The evaluation set measures its effect on answer rate and refusal accuracy.
