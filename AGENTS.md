# AGENTS

Rules for coding agents in this repo.

## Mission

Build and maintain a small AWS-native memory lab where:
- cognitive memory can mutate
- lineage is immutable, append-only, and replayable

## Non-negotiable invariants

1. Memory behavior can change; lineage history must not be rewritten.
2. S3 Tables is canonical lineage (`memory_lab.memory_events_v6`). v5 and earlier tables are historical containers; no new writes.
3. S3 Vectors is a rebuildable recall index, not source of truth.
4. Do not auto-resolve contradictions.
5. No current wall-clock influence on replay outputs. Every replay-deterministic field derives from lineage-visible inputs (TAI from `physical_moment.tai_iso`, sequence_in_stream, HLC step, declared time context). Wall-clock reads happen only at capture in `heliotime.now()` and never on the replay path.

## Current data flow

1. Engine/experiments write JSON lineage events to S3 ingress.
2. Athena ingestion validates into:
   - `lineage_events_raw` (validatable intake)
   - `lineage_events_quarantine` (invalid records)
3. Valid rows are inserted into canonical S3 Tables (`AWS_ATHENA_TARGET_TABLE_FQN`, default `memory_lab.memory_events_v6`).

## Required event envelope

Every new event must include:
- `event_id`, `event_type`, `agent_id`, `stream_id`, `memory_id`
- `physical_moment` (Tier 1a non-nullable: `tai_iso`, `solar_age_myr`, `ecliptic_lon_deg`, `sequence_in_stream`, `hlc_timestamp`, `time_context_id`; plus Tier 1b/Tier 2 per `specs/TAI_TIMEKEEPING.md` §5)
- `schema_version` (currently `6.0`), `payload`
- `actor_class`, `source_class`
- `parent_event_id` (nullable)
- `event_time` is the legacy field; in v6 its value equals `physical_moment.tai_iso` and it is no longer load-bearing for replay. Drop in a future epoch.

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

## Lab-phase schema/reset policy

- This repo is a single-team research lab; optimize for discovery speed over migration comfort.
- Destructive resets of S3/Athena/Glue state are allowed when they accelerate better schema/design learning.
- Prefer reset + clean re-ingest/replay over complex compatibility migrations during lab phase.
- When a reset occurs, record it as a lineage boundary event (who/when/why/what changed) and start a new canonical table/version explicitly.
- Do not rewrite surviving lineage history in place; cut new versions/epochs instead.

## Working conventions

- Use `uv` for Python env/deps and execution.
- Use AWS profile `stack-research` and region from env.
- Prefer simple, auditable, replay-first changes.
- Use AWS CDK for infra changes.
- Use AWS SDK for Python for service interaction.
- Keep AWS CDK string edits ASCII printable only.
