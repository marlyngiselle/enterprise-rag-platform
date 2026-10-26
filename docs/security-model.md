# Security model

Three questions decide whether an enterprise RAG system is safe to open to employees. Who can read which document, which network paths reach the data, and which identity holds which right. This page answers each one.

## Data access: document level security trimming

| Step | Where | Control |
| --- | --- | --- |
| Source | Front matter, HTML meta tag or PDF sidecar | Every document declares the Entra ID groups that may read it |
| Ingestion | `IngestionPipeline` | A document without groups is not indexed |
| Index | `group_ids` field | Filterable, written only by the ingestion identity |
| Query | `build_security_filter` | `group_ids/any(g: search.in(g, '<caller groups>', ','))`, applied as a pre-filter to BM25 and vector queries |
| Application | `Retriever` | Every hit is checked against the caller's groups again. A mismatch is dropped and logged as an error |
| Evaluation | `access_violations` metric | Counted on every case, CI fails above zero |

Group identifiers are validated against a strict pattern before they reach the filter, so a crafted claim cannot change the OData expression. More than 200 groups is rejected explicitly. A token in group overage (the `_claim_names` claim instead of `groups`) gets a 403, because silently treating it as "no groups" would hide the problem. The fix is to resolve groups server side through Microsoft Graph or to use app roles.

What trimming does not cover: a caller who may read a document may also read every answer built from it. Classification inside a document (one restricted paragraph in a public page) needs a separate document.

## Network

With `enable_private_endpoints = true` (the default, and the production setting):

| Data plane | Private endpoint subresource | Private DNS zone(s) | Public access |
| --- | --- | --- | --- |
| Azure AI Search | `searchService` | `privatelink.search.windows.net` | Disabled |
| Foundry (models) | `account` | `privatelink.openai.azure.com`, `privatelink.cognitiveservices.azure.com`, `privatelink.services.ai.azure.com` | Disabled |
| Documents | `blob` | `privatelink.blob.core.windows.net` | Disabled |
| Key Vault | `vault` | `privatelink.vaultcore.azure.net` | Disabled |

The private endpoint subnet has an NSG that admits HTTPS from the VNet only. The workload subnet is delegated to Container Apps. Ingestion pushes documents to the index, so the search service never needs outbound access to storage or to the models (see ADR 0003).

With private endpoints off (development), every data plane accepts only the ranges in `allowed_ip_ranges`, and still requires Entra ID.

## Identity and RBAC

No API key exists. Local authentication is disabled on Foundry, Azure AI Search, Application Insights ingestion and the storage account (shared keys).

| Identity | Role | Scope |
| --- | --- | --- |
| API | Search Index Data Reader | Search service |
| API | Cognitive Services OpenAI User | Foundry resource |
| API | Key Vault Secrets User | Key Vault |
| API | Monitoring Metrics Publisher | Application Insights |
| Ingestion | Search Index Data Contributor | Search service |
| Ingestion | Search Service Contributor | Search service, to create and update the index schema |
| Ingestion | Cognitive Services OpenAI User | Foundry resource |
| Ingestion | Storage Blob Data Reader | `documents` container only |
| Ingestion | Monitoring Metrics Publisher | Application Insights |

The API cannot write to the index, so a compromised API cannot plant content for other users. The ingestion identity cannot read Key Vault. The `terraform test` suite asserts both.

## Model input and output

| Hook | Default implementation | Replaceable by |
| --- | --- | --- |
| Direct prompt injection (question) | Pattern detector, blocks before retrieval | Azure AI Content Safety Prompt Shields |
| Indirect prompt injection (chunks) | Same detector, quarantines the chunk | Prompt Shields document analysis |
| PII in the question | Redactor masks e-mail, phone, IBAN, card numbers before the model and the logs | Azure AI Language PII detection |
| PII in the answer | Same redactor, per sentence when streaming | Same |
| Ungrounded answer | No citation means refusal | LLM judge in evaluation |

Pattern detectors are a first line, not a guarantee. They are cheap, deterministic and testable, and the protocols make it a one class change to add a managed classifier behind them.

## Supply chain

GitHub Actions are pinned to commit SHAs, checkout runs with `persist-credentials: false`, and the workflow token is read only. Terraform providers are locked with hashes for Linux and macOS.
