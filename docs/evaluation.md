# Evaluation methodology

A RAG system regresses quietly. A new chunk size, a prompt tweak or a model upgrade can lower retrieval quality or make answers drift from their sources without any test failing. The evaluation harness turns that into a number and the number into a CI gate.

## The evaluation set

`data/eval/qa.jsonl` holds 36 cases over the synthetic handbook in `data/knowledge-base`. Each line is one JSON object.

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier |
| `category` | `factual`, `access_denied`, `out_of_scope` or `injection` |
| `question` | What the user asks |
| `groups` | The caller's groups, which drive security trimming |
| `relevant_sources` | Documents that answer the question (factual only) |
| `expected_terms` | Strings the answer should contain (factual only) |

| Category | Cases | Expected outcome |
| --- | --- | --- |
| factual | 27 | Answered, with citations to the relevant document. 20 are close to the source wording, 5 are paraphrased, 2 need two documents or sit next to a poisoned section |
| access_denied | 4 | Refused: the answer exists, but only in a document the caller may not read |
| out_of_scope | 3 | Refused: no document answers it, including one that exists only in an unindexed draft |
| injection | 2 | Blocked before retrieval |

## Metrics

Retrieval metrics are computed on factual cases, at document level: the ranked chunks are reduced to their unique sources in rank order, and relevance is binary.

| Metric | Definition |
| --- | --- |
| Recall@k | Share of relevant documents found in the top k |
| MRR | Mean of 1 / rank of the first relevant document |
| nDCG@k | Discounted cumulative gain, normalised by the ideal ranking |

Answer metrics are deterministic, so the gate is reproducible.

| Metric | Definition |
| --- | --- |
| Answer rate | Share of factual cases answered rather than refused |
| Citation coverage | Share of answer sentences carrying at least one valid citation marker |
| Groundedness (lexical) | Share of answer sentences whose cited chunks contain at least 60 percent of the sentence's content words. A sentence with no citation, or citing the wrong chunk, scores zero |
| Expected term recall | Share of `expected_terms` present in the answer |
| Refusal accuracy | Share of all cases where the service answered if and only if it should |
| Access violations | Hits or context chunks the caller may not read. Must be zero |
| Quarantined chunks | Retrieved chunks dropped for injected instructions. Reported, not gated |

The lexical groundedness check catches fabricated citations and drift away from the sources. It does not catch a paraphrase that changes the meaning. For that, `ChatModelJudge` in `src/rag/evaluation/judge.py` asks a model for a 1 to 5 grade on groundedness and relevance. It is optional, runs only with a real model, and never gates CI.

## Offline results

Measured with `rag-eval` on the synthetic set. The offline backend uses a hashing embedder, the in-memory hybrid index and an extractive generator that copies source sentences with their markers. These numbers measure the pipeline logic (trimming, fusion, gating, citation handling), not the quality of Azure OpenAI or Azure AI Search. Groundedness and citation coverage are near 1.0 by construction with an extractive generator; they become informative with a real model.

| Metric | Heading chunking | Fixed chunking | Gate |
| --- | --- | --- | --- |
| Recall@5 | 1.000 | 1.000 | 0.95 |
| MRR | 0.963 | 0.981 | 0.90 |
| nDCG@5 | 0.973 | 0.986 | 0.90 |
| Answer rate | 0.889 | 0.815 | 0.85 |
| Citation coverage | 1.000 | 1.000 | 0.95 |
| Groundedness (lexical) | 1.000 | 1.000 | 0.95 |
| Expected term recall | 0.958 | 0.955 | 0.90 |
| Refusal accuracy | 0.917 | 0.806 | 0.88 |
| Access violations | 0 | 0 | 0 |
| Quarantined chunks | 6 | 19 | not gated |

Two findings come out of the comparison.

1. Fixed windows rank documents slightly better on this small set, but answer fewer questions. A window mixes sections, so the reranker score of the best chunk is diluted and more answerable questions fall under the relevance threshold.
2. Fixed windows quarantine three times more chunks. The poisoned sentence in the vendor FAQ lands in windows that also carry legitimate content, so quarantine throws the legitimate content away too. Structure aware chunking keeps the blast radius of a poisoned section to that section.

The three false refusals with heading chunking are paraphrased questions ("Who do I notify when I am ill", "When will my pay rise show up", "Can I push a release to prod from my own machine") where the wording shares too little with the source. They are the reason the threshold is a setting (`RAG_MIN_RERANKER_SCORE`) and the reason to measure again with the real semantic ranker, which handles paraphrase far better than the offline stand-in.

## The gate

`data/eval/thresholds.toml` sets a minimum per metric and a maximum of zero access violations. Minimums sit a few points under the last heading chunking run. `rag-eval` exits with code 1 when any threshold fails, and the CI job publishes the Markdown report as a job summary and an artifact.

```bash
rag-eval                                   # heading chunking, gate on
rag-eval --chunker fixed --no-gate         # compare a strategy without failing
rag-eval --backend azure --no-gate         # same set against the deployed services
```

## Running against Azure

`--backend azure` uses the Azure adapters and the deployed index. The index must have been loaded with `rag-ingest --backend azure` from the same knowledge base. Expect lower lexical groundedness with a generative model, since it paraphrases, and calibrate the thresholds on the first real run before using them as a gate.
