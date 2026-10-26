# Threat model

STRIDE applied to the RAG request path and the ingestion path. Each threat maps to a control and to the place where it is implemented or tested.

## Assets and trust boundaries

| Asset | Why it matters |
| --- | --- |
| Restricted documents (compensation, finance) | Disclosure to the wrong employee is the main business risk |
| The index | Whoever writes to it decides what every user reads |
| Model deployments | Cost, quota and the content they return |
| Prompts and system rules | Leaking them helps an attacker craft injections |
| Logs and traces | Can become a second copy of sensitive content |

Boundaries: the user and the API (Entra ID), the API and the data planes (managed identity, private endpoints), document authors and the index (ingestion), retrieved content and the model (prompt).

## STRIDE

| # | Category | Threat | Control | Where |
| --- | --- | --- | --- | --- |
| S1 | Spoofing | Caller forges identity or groups in headers | Built-in authentication validates the token; ingress restricted to it; dev header mode is off by default | `api/auth.py`, `Settings.auth_mode` |
| S2 | Spoofing | Workload uses a leaked key to call models or search | Keys do not exist: local auth disabled everywhere | `foundry.tf`, `search.tf`, `storage.tf`, plan test `keyless_everywhere` |
| T1 | Tampering | Attacker plants a document to steer answers for everyone (index poisoning) | Only the ingestion identity writes; the API reads only; sources in a versioned container | `rbac.tf`, plan test `least_privilege_roles` |
| T2 | Tampering | Indirect prompt injection inside a document | Hidden HTML dropped at load; poisoned chunks quarantined before the prompt; sources declared as data in the system prompt | `loaders.py`, `guards.py`, `prompts.py`, `test_guards.py` |
| T3 | Tampering | Crafted group claim alters the OData filter | Strict group id pattern, explicit delimiter in `search.in` | `security.py`, `test_security.py` |
| R1 | Repudiation | Cannot tell who asked what and what they received | Request id on every response and span; Entra ID identities in data plane logs; diagnostic settings on every resource | `api/app.py`, `diagnostics.tf` |
| I1 | Information disclosure | Restricted document returned to an unauthorised user | Pre-filter in the index plus re-check in the app; documents without ACL never indexed; access violations gated at zero | `retriever.py`, `pipeline.py`, eval gate |
| I2 | Information disclosure | Data exfiltration through the answer (markdown image or link carrying data to an external URL) | Exfiltration patterns blocked in questions and quarantined in chunks; answers are plain text with citations, clients must not render remote images | `guards.py` |
| I3 | Information disclosure | System prompt leak | Prompt leak patterns blocked; the prompt holds no secret | `guards.py`, `prompts.py` |
| I4 | Information disclosure | PII copied into the model, logs or traces | Question redacted before retrieval and the model; answer redacted; spans hold counts only | `guards.py`, `service.py`, `test_telemetry.py` |
| I5 | Information disclosure | Data plane reachable from the internet | Private endpoints, public access disabled, NSG on the endpoint subnet | `network.tf`, plan test `private_by_default` |
| D1 | Denial of service | Long or many questions exhaust token quota | Length limit on input; capacity set per deployment; refusal before the model when context is weak | `AskRequest`, `foundry.tf`, `service.py` |
| D2 | Denial of service | Search overloaded | Replicas as a variable; three for a read and write SLA in production | `env/prd.tfvars` |
| E1 | Elevation of privilege | Model output treated as instructions by a downstream tool | The API returns text and citations only, no tool calls; answers without citations are refused | `service.py` |
| E2 | Elevation of privilege | API identity compromised and used to change infrastructure | API identity holds data plane reader roles only, no control plane role | `rbac.tf` |

## Residual risks

1. Pattern based injection detection can be bypassed by paraphrase or encoding. Add Prompt Shields behind the same protocol for production.
2. Group membership changes take effect at the next token, not instantly.
3. A user entitled to a document can still extract all of it through many questions. Rate limiting belongs in the gateway in front of the API.
4. The lexical groundedness check does not catch meaning changes. Use the LLM judge on a sample of production traffic.
