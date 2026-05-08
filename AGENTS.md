# AGENTS

Quick start rules for coding agents in this repo.

## Mission

Build and maintain a small AWS-native memory lab where:
- cognitive memory can mutate
- lineage is immutable, append-only, and replayable

## Non-negotiable invariants

1. Memory behavior can change; lineage history must not be rewritten.
2. S3 Tables is canonical lineage (`memory_lab.memory_events_v4`).
3. S3 Vectors is a rebuildable recall index, not source of truth.
4. Do not auto-resolve contradictions.

## Current data flow

1. Engine/experiments write JSON lineage events to S3 ingress.
2. Athena ingestion validates into:
   - `lineage_events_raw` (validatable intake)
   - `lineage_events_quarantine` (invalid records)
3. Valid rows are inserted into canonical S3 Tables (`AWS_ATHENA_TARGET_TABLE_FQN`, default `memory_lab.memory_events_v4`).

## Required event envelope

Every new event must include:
- `event_id`, `event_type`, `agent_id`, `stream_id`, `memory_id`
- `event_time`, `schema_version`, `payload`
- `actor_class`, `source_class`
- `parent_event_id` (nullable)

## Safety + policy

- Apply eligibility gating before influence:
  - relevance * trust * recency * reinforcement * consistency * safety
- Quarantine suspicious/poisoned memory before promotion.
- Keep rejection/quarantine reasons machine-readable and deterministic.

## Working conventions

- Use `uv` for Python env/deps and execution.
- Use AWS profile `stack-research` and region from env.
- Prefer simple, auditable, replay-first changes.
- Use AWS CDK for infra changes.
- Use AWS SDK for Python for service interaction.
- Keep AWS CDK string edits ASCII printable only.
