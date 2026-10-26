---
title: Deployment Standards
acl_groups: [engineering]
owner: Platform Engineering
last_reviewed: 2026-05-19
---

# Deployment Standards

## Code review

Every change reaches main through a pull request. Application changes need 1 approval. Changes to production infrastructure code need 2 approvals, one of them from the platform team.

## Release

Deployments to production run from the pipeline only, never from a laptop. Every release must be reversible: a rollback must complete within 15 minutes. Risky features ship behind a feature flag, disabled by default.

## Change freeze

A change freeze applies during the last two weeks of December. Only fixes for SEV1 and SEV2 incidents are deployed during the freeze, with approval from the head of engineering.
