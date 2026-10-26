<div align="center">

<img src=".github/assets/enterprise-rag-platform-banner.svg" alt="Enterprise RAG Platform" width="100%">

# Enterprise RAG Platform

Retrieval augmented generation on Azure that answers only from what each employee may read, proves it with numbers, and shows its work in every trace.

<a href="infra/terraform/foundry.tf"><img src="https://img.shields.io/badge/Azure%20AI%20Foundry-keyless-0b1f4d?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik02LjUgMTlhNC41IDQuNSAwIDAgMS0uOS04LjkxQTYgNiAwIDAgMSAxNy4yIDguNiA1IDUgMCAwIDEgMTggMTl6Ii8%2BPC9zdmc%2B" alt="Azure AI Foundry"></a>
<a href="src/rag/azure/openai.py"><img src="https://img.shields.io/badge/Azure%20OpenAI-chat%20%2B%20embeddings-12306e?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAybDIuNCA3LjZMMjIgMTJsLTcuNiAyLjRMMTIgMjJsLTIuNC03LjZMMiAxMmw3LjYtMi40eiIvPjwvc3ZnPg%3D%3D" alt="Azure OpenAI"></a>
<a href="src/rag/ingestion/index_schema.py"><img src="https://img.shields.io/badge/AI%20Search-hybrid%20%2B%20semantic-16367f?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgZD0iTTEwLjUgNGE2LjUgNi41IDAgMSAwIDAgMTMgNi41IDYuNSAwIDAgMCAwLTEzek0xNS41IDE1LjVMMjEgMjEiLz48L3N2Zz4%3D" alt="Azure AI Search"></a>
<a href="docs/security-model.md"><img src="https://img.shields.io/badge/Security%20trimming-by%20Entra%20group-1a3a8a?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAybDggM3Y2YzAgNS0zLjQgOS4zLTggMTEtNC42LTEuNy04LTYtOC0xMVY1eiIvPjwvc3ZnPg%3D%3D" alt="Security trimming"></a>
<br>
<a href="infra/terraform/versions.tf"><img src="https://img.shields.io/badge/Terraform-azurerm%204%20%2B%20azapi%202-1a3a8a?style=for-the-badge&logo=terraform&logoColor=white" alt="Terraform"></a>
<a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.11%20to%203.13-2456c8?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
<a href="src/rag/api/app.py"><img src="https://img.shields.io/badge/FastAPI-SSE%20streaming-2456c8?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"></a>
<a href="src/rag/api/telemetry.py"><img src="https://img.shields.io/badge/OpenTelemetry-traces-16367f?style=for-the-badge&logo=opentelemetry&logoColor=white" alt="OpenTelemetry"></a>
<a href=".github/workflows/ci.yml"><img src="https://img.shields.io/badge/Eval%20gate-in%20CI-12306e?style=for-the-badge&logo=githubactions&logoColor=white" alt="Evaluation gate"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-0b1f4d?style=for-the-badge" alt="MIT License"></a>

</div>

<br>

## In numbers

| | |
| --- | --- |
| 0 | API keys. Local auth is off on Foundry, AI Search, Storage and Application Insights |
| 0 | Access violations across 36 evaluation cases, gated in CI |
| 1.000 | Recall@5 on the synthetic handbook, offline run [^offline] |
| 0.917 | Refusal accuracy. The service answers if and only if it should [^offline] |
| 4 | Data planes behind private endpoints, with 6 private DNS zones |
| 9 | Role assignments, split between a read only API identity and a write only ingestion identity |
| 24 | Terraform resource blocks over 19 resource types, with 14 validation rules on 15 variables |
| 7 | Offline `terraform test` runs with mocked providers |
| 125 | Python tests, 96 percent branch coverage, no network |
| 15 | STRIDE threats, each mapped to a control and a file |

[^offline]: Offline backend, measured with `rag-eval`. Hashing embedder, in-memory hybrid index and an extractive generator. The numbers measure the pipeline logic on the synthetic set, not the quality of Azure OpenAI or Azure AI Search. Full table in [docs/evaluation.md](docs/evaluation.md).

## What it is

A reference implementation of RAG the way an enterprise needs it. Employees ask questions about internal documents and get short answers where every sentence cites its source. A restricted HR page never reaches someone outside HR, because the search index filters by Entra ID group before ranking and the application checks every hit again. Every change runs an evaluation set in CI, and a drop in retrieval quality or a single access violation blocks the merge.

Everything runs on a laptop with fakes behind the same interfaces, so the logic that matters most is tested without a cloud account.

## Architecture

```mermaid
flowchart LR
  subgraph users["Employees"]
    u["fa:fa-user Entra ID user<br/>groups claim"]
  end

  subgraph app["Workload (Container Apps)"]
    direction TB
    auth["fa:fa-id-badge Built-in auth<br/>validates the token"]
    api["fa:fa-bolt RAG API<br/>FastAPI, SSE"]
    guard["fa:fa-shield-halved Guards<br/>injection, PII"]
    job["fa:fa-gears Ingestion job<br/>load, chunk, embed"]
    auth --> api
    api --- guard
  end

  subgraph ai["Azure AI Foundry"]
    direction TB
    chat["fa:fa-comments Chat deployment"]
    emb["fa:fa-vector-square Embedding deployment"]
  end

  subgraph retrieval["Azure AI Search"]
    idx["fa:fa-magnifying-glass Hybrid index<br/>BM25, HNSW, semantic ranker<br/>group_ids filter"]
  end

  subgraph data["Data"]
    blob["fa:fa-folder-open Documents<br/>Storage, no shared keys"]
    kv["fa:fa-key Key Vault<br/>RBAC only"]
  end

  subgraph obs["Observability"]
    appi["fa:fa-wave-square Application Insights"]
    law["fa:fa-database Log Analytics"]
  end

  u -- "HTTPS + token" --> auth
  api -- "read, trimmed by group" --> idx
  api --> chat
  api --> emb
  job -- "read" --> blob
  job --> emb
  job -- "push chunks + ACL" --> idx
  api -. "OpenTelemetry" .-> appi
  appi --> law
  idx -. "diagnostics" .-> law
  chat -. "diagnostics" .-> law
  api -. "secrets if any" .- kv

  classDef user fill:#0b1f4d,stroke:#8fb3ff,stroke-width:2px,color:#ffffff
  classDef wl fill:#1a3a8a,stroke:#c7d7ff,stroke-width:2px,color:#ffffff
  classDef model fill:#2456c8,stroke:#ffffff,stroke-width:2px,color:#ffffff
  classDef search fill:#16367f,stroke:#c7d7ff,stroke-width:2px,color:#ffffff
  classDef store fill:#12306e,stroke:#8fb3ff,stroke-width:2px,color:#ffffff
  classDef observe fill:#16367f,stroke:#8fb3ff,stroke-width:2px,color:#ffffff
  class u user
  class auth,api,guard,job wl
  class chat,emb model
  class idx search
  class blob,kv store
  class appi,law observe
  style users fill:#eef3ff,stroke:#2456c8,stroke-width:1px,color:#0b1f4d
  style app fill:#eef3ff,stroke:#2456c8,stroke-width:1px,color:#0b1f4d
  style ai fill:#eef3ff,stroke:#2456c8,stroke-width:1px,color:#0b1f4d
  style retrieval fill:#eef3ff,stroke:#2456c8,stroke-width:1px,color:#0b1f4d
  style data fill:#eef3ff,stroke:#2456c8,stroke-width:1px,color:#0b1f4d
  style obs fill:#eef3ff,stroke:#2456c8,stroke-width:1px,color:#0b1f4d
```

All data planes sit behind private endpoints in production. The index schema, the chunking and the ACL extraction are code in this repository, explained in [docs/architecture.md](docs/architecture.md).

## How a question is answered

```mermaid
sequenceDiagram
  autonumber
  participant U as Employee
  participant A as RAG API
  participant G as Guards
  participant E as Embedding model
  participant S as AI Search
  participant C as Chat model
  participant T as App Insights
  U->>A: POST /v1/ask/stream (token, x-request-id)
  A->>G: Screen question for injection, mask PII
  G-->>A: Clean question
  A->>E: Embed question (managed identity)
  A->>S: BM25 + vector + semantic, filter group_ids by caller groups
  S-->>A: Top chunks with reranker scores
  A->>A: Re-check groups, quarantine poisoned chunks, drop weak hits
  alt Nothing relevant left
    A-->>U: Refusal, model never called
  else Grounded context
    A->>C: Numbered sources + rules (cite every sentence)
    C-->>A: Token stream
    A-->>U: SSE sources, tokens per sentence (PII masked), done with verdict
  end
  A-->>T: Spans with counts and verdicts, never the text
```

## Evaluation

The gate in CI runs 36 cases through retrieval and generation and fails the build when a metric drops under its threshold. The cases cover answerable questions, questions whose answer exists only in a document the caller may not read, questions nothing answers, and direct injection attempts.

| Metric | Offline result [^offline] | Gate |
| --- | --- | --- |
| Recall@5 | 1.000 | 0.95 |
| MRR | 0.963 | 0.90 |
| nDCG@5 | 0.973 | 0.90 |
| Answer rate (answerable cases) | 0.889 | 0.85 |
| Citation coverage | 1.000 | 0.95 |
| Groundedness, lexical | 1.000 | 0.95 |
| Expected term recall | 0.958 | 0.90 |
| Refusal accuracy | 0.917 | 0.88 |
| Access violations | 0 | 0 |

Citation coverage and groundedness are 1.0 by construction with an extractive generator. They become informative against a real model, where the optional LLM judge also applies.

> [!TIP]
> The same harness compares strategies. Fixed size chunking ranks slightly better on this set but answers fewer questions (0.815) and quarantines 19 chunks instead of 6, because a poisoned sentence contaminates every window around it. It fails the gate. Details in [docs/evaluation.md](docs/evaluation.md).

## Quick start

Everything below runs offline, with no Azure subscription.

```bash
git clone https://github.com/marlyngiselle/enterprise-rag-platform.git
cd enterprise-rag-platform
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Quality checks and the evaluation gate
.venv/bin/ruff check . && .venv/bin/mypy && .venv/bin/pytest
.venv/bin/rag-eval && cat reports/eval-report.md

# Run the API on the synthetic handbook
RAG_AUTH_MODE=dev-headers .venv/bin/uvicorn --factory rag.api.app:app_factory --port 8080
```

In a second terminal, ask the same question as two different employees.

```bash
curl -s localhost:8080/v1/ask -H 'content-type: application/json' \
  -H 'x-user-id: alex' -H 'x-user-groups: all-employees,hr-compensation' \
  -d '{"question": "What is the merit increase budget for 2026?"}'

curl -s localhost:8080/v1/ask -H 'content-type: application/json' \
  -H 'x-user-id: sam' -H 'x-user-groups: all-employees' \
  -d '{"question": "What is the merit increase budget for 2026?"}'
```

The first gets the answer with a citation to the compensation review. The second gets a refusal, and the model is never called.

Infrastructure checks, also offline.

```bash
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform test
tflint --chdir=infra/terraform --config="$PWD/.tflint.hcl" --init
tflint --chdir=infra/terraform --config="$PWD/.tflint.hcl"
```

To deploy, copy `infra/terraform/backend.hcl.example` to `backend.hcl` with your state storage account, then run from a machine with access to Azure.

```bash
az login
export TF_VAR_subscription_id="$(az account show --query id -o tsv)"
terraform -chdir=infra/terraform init -backend-config=backend.hcl
terraform -chdir=infra/terraform plan -var-file=env/dev.tfvars -out=tfplan
terraform -chdir=infra/terraform apply tfplan

export RAG_BACKEND=azure
export RAG_OPENAI_ENDPOINT="$(terraform -chdir=infra/terraform output -raw openai_endpoint)"
export RAG_SEARCH_ENDPOINT="$(terraform -chdir=infra/terraform output -raw search_endpoint)"
.venv/bin/rag-ingest --backend azure
.venv/bin/rag-eval --backend azure --no-gate
```

## Environments

| Setting | dev | prd |
| --- | --- | --- |
| Network | Public endpoints, IP allowlist, Entra ID still required | Private endpoints and private DNS, public access disabled |
| AI Search | `basic`, 1 replica, semantic ranker free plan | `standard`, 3 replicas (read and write SLA), semantic ranker standard |
| Model deployments | `GlobalStandard`, 30k tokens per minute | `DataZoneStandard`, 150k tokens per minute |
| Document storage | LRS | ZRS |
| Log retention | 30 days | 90 days |

## Access model

| Identity | AI Search | Foundry models | Documents | Key Vault | App Insights |
| --- | --- | --- | --- | --- | --- |
| API | Index Data Reader | OpenAI User | none | Secrets User | Metrics Publisher |
| Ingestion job | Index Data Contributor, Service Contributor | OpenAI User | Blob Data Reader on `documents` | none | Metrics Publisher |
| Employee | through the API only, trimmed by group | none | none | none | none |

The API cannot write to the index, so a compromised API cannot plant content for other users. The `terraform test` suite asserts it. The full model, with network and guard hooks, is in [docs/security-model.md](docs/security-model.md).

## Delivery

```mermaid
flowchart LR
  pr["fa:fa-code-pull-request Pull request"] --> py["fa:fa-flask python<br/>ruff, mypy, pytest"]
  pr --> tf["fa:fa-cubes terraform<br/>fmt, validate, test, tflint"]
  py --> ev{"fa:fa-scale-balanced Evaluation gate<br/>36 cases, thresholds"}
  ev -- "pass" --> merge["fa:fa-code-merge Merge"]
  ev -- "fail" --> block["fa:fa-ban Blocked<br/>report in job summary"]
  tf --> merge
  classDef auto fill:#1a3a8a,stroke:#c7d7ff,stroke-width:2px,color:#ffffff
  classDef gate fill:#0b1f4d,stroke:#8fb3ff,stroke-width:2px,color:#ffffff
  classDef ok fill:#2456c8,stroke:#ffffff,stroke-width:2px,color:#ffffff
  classDef stop fill:#12306e,stroke:#8fb3ff,stroke-width:2px,color:#ffffff,stroke-dasharray:5 5
  class pr,py,tf auto
  class ev gate
  class merge ok
  class block stop
```

Every action is pinned to a commit SHA, checkout keeps no credentials, and the workflow token is read only. The evaluation report is published as a job summary and kept as an artifact for 30 days.

## Before you deploy

> [!IMPORTANT]
> Group based trimming needs the `groups` claim in the token. Users in more than about 200 groups receive an overage pointer instead, and the API answers 403 rather than guessing. Resolve groups server side through Microsoft Graph, or switch to app roles.

> [!WARNING]
> `RAG_AUTH_MODE=dev-headers` trusts the `x-user-groups` header. It exists for local runs. In Azure, keep the default `easy-auth` and restrict ingress to the built-in authentication front door.

> [!WARNING]
> Model deployments consume regional quota. If the region has no capacity left for a model, the apply fails with `InsufficientQuota`. Check quota before changing `chat_model` or `embedding_model`.

> [!CAUTION]
> Key Vault, the storage account and the documents container carry `prevent_destroy`. Key Vault and Foundry are soft deleted, and the random suffix in their names lets a rebuild proceed while the deleted copy still holds the old name.

## Repository map

| Path | What it holds |
| --- | --- |
| [`src/rag/ingestion/`](src/rag/ingestion) | Loaders (Markdown, HTML, PDF), heading and fixed chunkers, pipeline, index schema as code |
| [`src/rag/retrieval/`](src/rag/retrieval) | Security filter, reciprocal rank fusion, retriever with the second group check, citations |
| [`src/rag/generation/`](src/rag/generation) | Grounded prompt, injection and PII guards, answer service with streaming |
| [`src/rag/evaluation/`](src/rag/evaluation) | Metrics, harness, Markdown report, CI gate, optional LLM judge |
| [`src/rag/api/`](src/rag/api) | FastAPI app, Entra ID principal parsing, OpenTelemetry |
| [`src/rag/azure/`](src/rag/azure) | Keyless Azure OpenAI and AI Search adapters |
| [`src/rag/fakes.py`](src/rag/fakes.py) | Offline embedder, in-memory hybrid index, extractive generator |
| [`data/knowledge-base/`](data/knowledge-base) | Synthetic handbook, 11 documents, one restricted, one poisoned, one without ACL |
| [`data/eval/`](data/eval) | Evaluation set and gate thresholds |
| [`infra/terraform/`](infra/terraform) | Foundry, models, AI Search, storage, Key Vault, identities, RBAC, network, diagnostics |
| [`tests/`](tests) | Unit and API tests, all offline |
| [`docs/`](docs) | Architecture, security model, evaluation, threat model, ADRs |

## Documentation

| Document | What it answers |
| --- | --- |
| [Architecture](docs/architecture.md) | Components, ingestion, index schema, query path, streaming, offline mode |
| [Security model](docs/security-model.md) | Document level trimming, network, identities and roles, guard hooks |
| [Evaluation](docs/evaluation.md) | The set, the metrics, the offline results and how the gate works |
| [Threat model](docs/threat-model.md) | STRIDE for RAG, including prompt injection and data exfiltration |
| [ADR 0001](docs/adr/0001-hybrid-retrieval-with-semantic-ranker.md) | Why hybrid retrieval with semantic reranking |
| [ADR 0002](docs/adr/0002-security-trimming-in-the-index.md) | Why trimming in the index and again in the app |
| [ADR 0003](docs/adr/0003-push-ingestion-from-a-pipeline.md) | Why push ingestion instead of indexers |

<br>

<div align="center">

Designed and built by Giselle Da Costa. Released under the [MIT License](LICENSE).

</div>
