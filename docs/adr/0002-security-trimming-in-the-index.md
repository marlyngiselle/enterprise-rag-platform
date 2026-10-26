# ADR 0002: Document level security trimming in the index, checked again in the app

Status: accepted

## Context

The knowledge base mixes public handbook pages with restricted HR and finance documents. Alternatives considered:

| Option | Problem |
| --- | --- |
| One index per audience | Duplicates content, explodes with group combinations |
| Filter results in the app after search | Top k fills with documents the user cannot see; recall collapses and timing leaks existence |
| Index level filter only | One bug in the filter and restricted content reaches the prompt |

## Decision

Each chunk stores the Entra ID group ids allowed to read its document in a filterable `group_ids` field. Each query carries a `search.in` filter built from the caller's validated groups, applied as a pre-filter to both keyword and vector queries. The application then re-checks every hit and drops anything that does not match, logging it as an error. Documents without groups are never indexed.

## Consequences

1. Authorised users get full recall, unauthorised content never enters ranking.
2. A filter defect fails closed and loudly instead of leaking.
3. Group overage must be handled: tokens with more than about 200 groups carry no groups claim. The API returns 403 in that case instead of guessing.
4. Permission changes on a document require re-ingesting its chunks.
