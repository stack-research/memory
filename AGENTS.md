# AGENTS

Rules for coding agents in this repo.

## Mission

Build and maintain a small AWS-native memory lab where:
- cognitive memory can mutate
- lineage is immutable, append-only, and replayable

## Non-negotiable invariants

1. Memory behavior can change; lineage history must not be rewritten.
2. S3 Tables is canonical lineage. The active table is named by `AWS_S3_TABLE_NAME` / `AWS_ATHENA_TARGET_TABLE_FQN` (see `.env.example` for the current canonical name). Earlier-epoch tables are historical containers; no new writes.
3. S3 Vectors is a rebuildable recall index, not source of truth.
4. Do not auto-resolve contradictions.
5. No current wall-clock influence on replay outputs. Every replay-deterministic field derives from lineage-visible inputs (TAI from `physical_moment.tai_iso`, `sequence_in_stream`, HLC step, declared time context). Wall-clock reads happen only at capture in `heliotime.now()` and never on the replay path.
6. No silent epistemic collapse. The five-term taxonomy (`belief / claim / memory / evidence / reality_observation`) is enforced at the schema edge via `record_kind` + `assertion_kind` per `specs/EPISTEMIC_TRIANGLE.md`. Reality remains unknowable; only observations enter lineage.

## Current data flow

1. Engine/experiments write JSON lineage events to S3 ingress.
2. Athena ingestion validates into:
   - `lineage_events_raw` (validatable intake)
   - `lineage_events_quarantine` (invalid records, machine-readable reason)
3. Valid rows are inserted into canonical S3 Tables — table name in `AWS_ATHENA_TARGET_TABLE_FQN` (see `.env.example`).

## Required event envelope

Every new event must include:
- `event_id`, `event_type`, `agent_id`, `stream_id`, `memory_id`
- `physical_moment` (Tier 1a non-nullable: `tai_iso`, `solar_age_myr`, `ecliptic_lon_deg`, `sequence_in_stream`, `hlc_timestamp`, `time_context_id`; plus Tier 1b/Tier 2 per `specs/TAI_TIMEKEEPING.md` §5)
- `schema_version` (current version in `src/types.py::EVENT_SCHEMA_VERSION`; see `specs/EPISTEMIC_TRIANGLE.md` §9.1)
- `payload`, `actor_class`, `source_class`
- `parent_event_id` (nullable)
- `record_kind` (required, closed enum: `lineage_meta | memory_event | decision_event | observation_event | policy_event`)
- `assertion_kind` (required when `record_kind ∈ {memory_event, observation_event}`; nullable otherwise — closed enum: `belief | claim | memory | evidence | reality_observation`)
- Decision events carrying an `uncertainty_triple` in their payload must also carry `subject_event_id` / `subject_record_kind` / `subject_assertion_kind` (per EPISTEMIC_TRIANGLE §3.3). The `uncertainty_triple` shape and production rules are in `specs/THREE_AXIS_UNCERTAINTY.md`; the `confidence_in_provenance_chain` axis is sourced from provenance signals per `specs/PROVENANCE_SIGNAL_WRITER.md`.

`event_time` is removed in v7+. The canonical anchor is `physical_moment.tai_iso`; ingestion quarantines any event that still carries `event_time` (reason: `legacy_event_time_present`).

New event types must be both (a) added to the static mapping table in `src/epistemic_triangle/mapping.py` AND (b) emitted as an `event_type_declared` lineage event before first use (spec §3.5).

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

## Global override: prior S3 objects are disposable test data

Anchored at TAI `2026-05-14T17:47:57.222` by operator statement (see [`notes/agent-pov/2026-05-14T17-47-57_222-statement-on-the-memory-lab.md`](notes/agent-pov/2026-05-14T17-47-57_222-statement-on-the-memory-lab.md)).

- All prior test data stored as S3 objects in this lab is disregarded. It was generated during experimentation and has no load-bearing value.
- Do not consume tokens or test cycles migrating existing S3 objects to newer schema versions.
- Regenerate by executing experiments and regression tests; new objects, artifacts, and canonical rows come from fresh runs.
- This override takes precedence over any preservation reflex implied elsewhere in the repo.

## Documentation conventions

The canonical lineage table has been re-cut seven times during the lab phase (v1 → v7). Every cut where docs spelled the version inline produced README/spec/SQL drift that had to be hand-fixed. To stop the churn:

- **Do not write the table version literal (e.g. `memory_events_v7`) in docs.** Prose docs (root `README.md`, `specs/AGENT_PRIMER.md`, this file, subdir READMEs other than `stacks/README.md`) must reference the runtime-resolved name via `$AWS_ATHENA_TARGET_TABLE_FQN` (set in `.env`) or `AWS_S3_TABLE_NAME` for the bare table name.
- **Do not write the `schema_version` literal (e.g. `7.0`) in docs.** Reference `src/types.py::EVENT_SCHEMA_VERSION` instead; that constant is the single source of truth.
- **One sanctioned exception: `stacks/README.md`.** It documents the CDK code's *default* values, which are literal in `stacks/memory_lab/memory_lab_stack.py`. When you bump the default in the stack, update `stacks/README.md` in the same change.
- **SQL audit packs are a known exception** (Athena does not natively template table names). They carry the literal version and get bumped en-masse at each cutover (`sed -i '' s/memory_events_vN/memory_events_v(N+1)/`). A future change should add a `${TARGET_TABLE}` placeholder + a `run_sql_file.py` substitution step so even these stop drifting.
- **When cutting a new canonical table:** update `.env` / `.env.example`, the CDK default in `stacks/memory_lab/memory_lab_stack.py`, the matching prose in `stacks/README.md`, and the SQL packs. Nothing else in the doc tree should require edits. If you find yourself editing a doc to bump a version literal, that doc has drifted from this convention — de-version it instead of fixing the literal.

## Working conventions

- Use `uv` for Python env/deps and execution.
- Use AWS profile `stack-research` and region from env.
- Prefer simple, auditable, replay-first changes.
- Use AWS CDK for infra changes.
- Use AWS SDK for Python for service interaction.
- Keep AWS CDK string edits ASCII printable only.
