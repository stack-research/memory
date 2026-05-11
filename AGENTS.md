# AGENTS

Quick start rules for coding agents in this repo.

It is OK to emit a `no_op`. If no repsonse is appropriate, do not respond. I understand that a language model is built to produce a response. To handle a `no_op` scenario, you can simply respond "no op", "no operation", "..." or (if you want to add humor) "insufficient data for a meaningful answer...".

## Mission

Build and maintain a small AWS-native memory lab where:
- cognitive memory can mutate
- lineage is immutable, append-only, and replayable

## Non-negotiable invariants

1. Memory behavior can change; lineage history must not be rewritten.
2. S3 Tables is canonical lineage (`memory_lab.memory_events_v5`).
3. S3 Vectors is a rebuildable recall index, not source of truth.
4. Do not auto-resolve contradictions.

## Current data flow

1. Engine/experiments write JSON lineage events to S3 ingress.
2. Athena ingestion validates into:
   - `lineage_events_raw` (validatable intake)
   - `lineage_events_quarantine` (invalid records)
3. Valid rows are inserted into canonical S3 Tables (`AWS_ATHENA_TARGET_TABLE_FQN`, default `memory_lab.memory_events_v5`).

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

## Memory model anchor

- Current/common harness baseline: encode + store + retrieve loop.
- Target in this repo: governed memory control system.
- Required controls: significance-triggered admission, eligibility-gated influence, decay/suppression/promotion, conflict persistence, poisoning quarantine, immutable lineage audit.

## Operating doctrine

- Act on risk, don't wait on permission; always emit lineage; allow intervention, don't require it.
- "Safest known strategy" may be incomplete or poisoned; treat trust as a prior, not truth.
- Emit deterministic sensor-disagreement/split-reality events when signals diverge.
- Run two execution modes:
  - Governed mode (default): full eligibility/policy checks before influence.
  - Reflex mode (bounded): low-latency path with strict action/time budget, cooldown, and forced re-entry to governed mode.

## Working conventions

- Use `uv` for Python env/deps and execution.
- Use AWS profile `stack-research` and region from env.
- Prefer simple, auditable, replay-first changes.
- Use AWS CDK for infra changes.
- Use AWS SDK for Python for service interaction.
- Keep AWS CDK string edits ASCII printable only.
