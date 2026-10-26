# ADR 0003: Push ingestion from a pipeline instead of built-in indexers

Status: accepted

## Context

Azure AI Search can pull documents itself with indexers and skillsets, including integrated vectorization. That needs the search service to reach storage and the models, which with private networking means shared private links approved on each target, and puts chunking logic in skillset JSON.

## Decision

A Python ingestion job loads, chunks, embeds and pushes documents to the index. The same chunking and ACL code runs in tests, in the evaluation harness and in production.

## Consequences

1. Chunking strategy, ACL extraction and injection hygiene are ordinary code, unit tested and evaluated offline.
2. The search service needs no outbound access: no shared private links to approve.
3. The ingestion job must be scheduled and monitored, and handles retries and deletions itself.
4. Switching to indexers later remains possible, since the index schema is defined independently in code.
