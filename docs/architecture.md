# Architecture

## Components

| Component | Azure service | Role |
| --- | --- | --- |
| Document landing zone | Storage account, container `documents` | Source files (Markdown, HTML, PDF) with their ACL metadata |
| Ingestion job | Container Apps job, identity `id-<workload>-<env>-ingestion` | Loads, chunks, embeds and pushes chunks to the index |
| Models | Azure AI Foundry resource (kind `AIServices`) with a project | Chat and embedding deployments, Entra ID only |
| Retrieval | Azure AI Search, semantic ranker enabled | Hybrid index: BM25, HNSW vectors, semantic reranking, security field |
| API | Container Apps app behind built-in authentication, identity `id-<workload>-<env>-api` | Guard, retrieve, generate, verify, stream |
| Secrets | Key Vault, RBAC mode | Only for credentials that cannot be replaced by a managed identity |
| Observability | Application Insights on a Log Analytics workspace | Traces from the API, diagnostic logs from every data plane |

The Terraform in `infra/terraform` creates everything except the Container Apps environment and the apps themselves, which belong to the hosting platform. The workload subnet is delegated to `Microsoft.App/environments` and ready for them.

## Ingestion

1. A loader turns each file into a `Document`. Markdown takes its title and `acl_groups` from front matter, HTML from `<title>` and `<meta name="acl-groups">`, PDF from a `<file>.pdf.meta.json` sidecar. HTML loading drops scripts, styles, comments and anything hidden, because hidden text is the usual carrier for indirect prompt injection.
2. A document without groups is skipped and logged. Access control fails closed.
3. The heading chunker splits on Markdown headings and keeps the heading path (`Leave and Time Off > Parental leave`) as the `section` of each chunk. Long sections are split recursively on paragraphs, then lines, then sentences, with a 30 word overlap. A fixed window chunker exists as a baseline.
4. Chunks are embedded in batches of 16. The embedding input is `title | section` plus the text, so a short chunk keeps its context.
5. Chunks are pushed with `merge_or_upload` in batches of 500. The chunk key is a hash of source and position, so a re-run updates in place.

## Index schema

Defined in code in `src/rag/ingestion/index_schema.py`.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | key | Hash of source and position |
| `source`, `title`, `section`, `content` | searchable, `en.microsoft` analyzer | BM25 and semantic ranker input |
| `position` | Int32, sortable | Order inside the document |
| `group_ids` | Collection(String), filterable | Security trimming |
| `content_vector` | Collection(Single), HNSW cosine, not retrievable | Vector search |

The semantic configuration uses `section` as title, `content` as content and `title` as keywords.

## Query path

1. Built-in authentication validates the Entra ID token and forwards the claims. The API reads the object id and the `groups` claims.
2. The question is checked for prompt injection and PII is masked before it goes anywhere else.
3. One hybrid query is sent: the text for BM25, the embedding for a k nearest neighbours vector query, the security filter as a pre-filter on both, and `query_type=semantic`. Azure AI Search fuses BM25 and vector results with reciprocal rank fusion, then reranks the top 50 with the semantic ranker.
4. The API checks every hit against the caller's groups again, and drops and logs anything that should not be there.
5. Chunks that contain injected instructions are quarantined. Hits under the reranker score threshold (1.2 on the 0 to 4 scale) are dropped. If nothing is left, the API refuses without calling the model.
6. The prompt wraps each chunk in a numbered `<source>` tag. The system prompt requires a citation per sentence and a fixed refusal sentence when the sources are not enough.
7. The answer is verified: unknown citation markers are removed, PII is masked, and an answer that cites nothing becomes a refusal.

## Streaming

`POST /v1/ask/stream` sends server sent events: `meta` (request id), `sources` (the candidate citations), `token` events and `done`. Tokens are released sentence by sentence, so the PII redactor always sees a complete sentence. The `done` event carries the same verdict as the non streaming path. A client must replace the streamed text with the refusal if `done` says the answer was not grounded.

## Observability

OpenTelemetry instruments FastAPI and adds spans `rag.answer`, `rag.retrieve` and `rag.generate`. Spans carry counts and verdicts (hits, quarantined chunks, PII redactions, refusal reason) and the request id. They never carry the question or the answer. With `APPLICATIONINSIGHTS_CONNECTION_STRING` set and the `monitor` extra installed, spans go to Application Insights, which accepts them only from an identity with `Monitoring Metrics Publisher`.

## Offline mode

Every external dependency sits behind a protocol in `src/rag/providers.py`. The offline backend replaces them with deterministic fakes: a hashing embedder, an in-memory index that implements BM25, cosine similarity, reciprocal rank fusion and a reranking stand-in, and an extractive generator. The tests, the evaluation gate and a local run of the API need no cloud access.
