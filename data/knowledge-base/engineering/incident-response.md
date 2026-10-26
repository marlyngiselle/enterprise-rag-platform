---
title: Incident Response Runbook
acl_groups: [engineering]
owner: Platform Engineering
last_reviewed: 2026-05-05
---

# Incident Response Runbook

This runbook defines how engineering responds to production incidents.

## Severity levels

SEV1 means a full outage or data loss for customers. SEV2 means a major feature is degraded for many customers. SEV3 means a minor feature is degraded or a workaround exists. SEV4 is a cosmetic issue with no customer impact.

## Paging and roles

For a SEV1 the on-call engineer is paged and must acknowledge within 5 minutes. The first responder becomes the incident commander until they hand over the role explicitly. The incident commander posts a status update every 30 minutes until the incident is resolved.

## On-call rotation

On-call rotations last one week, from Monday 09:00 to the next Monday 09:00. On-call engineers receive an allowance of 50 EUR per weekday and 100 EUR per weekend day on call.

## Postmortems

Every SEV1 and SEV2 incident gets a blameless postmortem, published within 5 business days of resolution. Action items from a postmortem are tracked in the backlog with an owner and a due date.
