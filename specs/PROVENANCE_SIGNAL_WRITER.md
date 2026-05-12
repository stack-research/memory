# PROVENANCE_SIGNAL_WRITER

Status: Adopted spec
Version: v1.0
Promoted from: `notes/agent-pov/proposals/PROVENANCE_SIGNAL_WRITER.md`
Promotion date: 2026-05-12

## Implementation checklist (v1)

- [ ] Add `src/explicit_memory/provenance.py` with deterministic `compute_chain_signals(memory_id, as_of_time, lineage_reader)`.
- [ ] Implement stable chain walk and tie-break rules (`event_time`, then `event_id`).
- [ ] Emit deterministic fallbacks with machine-readable `fallback_reason` for missing/broken chains.
- [ ] Extend `src/vectors.py` write path to store `parent_chain_depth`, `source_diversity`, `age_of_original_source_hours` metadata.
- [ ] Emit `provenance_signals_computed` events with required payload fields.
- [ ] Emit `provenance_signals_written_to_vector` events with required payload fields.
- [ ] Update `src/explicit_memory/recall.py` to consume direct provenance metadata fields (not alias-only fallback).
- [ ] Update `src/implicit_memory/loop.py` to provide provenance inputs from computed/lookup signals (remove hardcoded provenance defaults).
- [ ] If caching is used, define deterministic invalidation policy and surface cache-source marker in debug payloads.
- [ ] Add deterministic unit tests for chain computation, including edge cases and tie-break behavior.
- [ ] Add replay tests validating `as_of_time` reconstruction matches prior emitted provenance signals.
- [ ] Add fallback-path tests for broken parent links/cycles/unknown source classes.
- [ ] Ensure uncertainty suites remain wired in `im_regression`.
- [ ] Run and record audit checks (`axis_dominance_audit.sql` or equivalent) on post-implementation traffic.
- [ ] Document implementation status and any deferred items in a lineage-visible change event.

## 1) Purpose

Make `confidence_in_provenance_chain` decision-relevant by producing deterministic provenance signals from canonical lineage and writing them into recall metadata and lineage events.

This spec is additive. It does not rewrite lineage history.

## 2) Scope

In scope:
- Storage-time provenance signal computation and vector metadata write.
- Read-time provenance signal consumption for explicit recall.
- Implicit gate provenance signal lookup replacing hardcoded defaults.
- Lineage events for provenance computation/write.
- Determinism + replay contract.
- Regression/audit success criteria.

Out of scope (v1):
- Global backfill/re-index of old vectors.
- Changing event envelope schema.
- Expanding three-axis coverage to every event family.

## 3) Required signals

For each `memory_id`, compute:
- `parent_chain_depth: int`  
  Number of parent hops from latest event in chain to root event.
- `source_diversity: float`  
  `unique(source_class) / chain_length`, clamped `[0.0, 1.0]`.
- `age_of_original_source_hours: float`  
  Hours between root event `event_time` and computation time.

## 4) Deterministic algorithm contract

Given `(memory_id, as_of_time, canonical_lineage<=as_of_time)`, output must be deterministic.

Definitions:
- Chain root: earliest event in connected chain where `parent_event_id IS NULL`.
- Latest event: max `(event_time, event_id)` in chain (tie-break by `event_id` lexicographic ascending for stability).
- Chain length: count of chain events included in computation.

Edge behavior:
- Missing chain/root: emit deterministic fallback defaults and `fallback_reason`.
- Cycles or broken parent links: emit deterministic fallback defaults and `fallback_reason`.
- Empty/invalid `source_class`: treat as literal value `"unknown"`.

Required fallback defaults:
- `parent_chain_depth = 0`
- `source_diversity = 1.0`
- `age_of_original_source_hours = max(0, hours_stale)` when available, else `0.0`

## 5) Replay contract

Replay at time `T` must recompute the same provenance signals using only events with `event_time <= T` (and tie-breaks above).

Any computation that depends on non-lineage mutable state must be marked with deterministic fallback + reason and must not silently alter decision payloads.

## 6) Lineage events

Add event types:
- `provenance_signals_computed`
- `provenance_signals_written_to_vector`

Both must include:
- `provenance_signals` block
- `chain_root_event_id`
- `chain_length`
- `distinct_source_classes`
- `computed_at`
- `as_of_time`
- `fallback_reason` (nullable)

## 7) Integration points

- `src/explicit_memory/provenance.py` (new): canonical computation API.
- `src/vectors.py`: write signals to vector metadata.
- `src/explicit_memory/recall.py`: consume direct metadata fields (no alias-only shortcut).
- `src/implicit_memory/loop.py`: use computed/lookup provenance signals for eligibility gate input.
- Optional cache layer allowed, but cache invalidation must be deterministic and documented.

## 8) Migration and fallback semantics

- No mandatory global backfill in v1.
- Old vectors without fields remain readable via deterministic defaults.
- New writes must include fields.
- Rewrites of existing memories should include fields when available.

## 9) Performance and cost guardrails

- Default per-memory chain lookup must be bounded and auditable.
- If using cache, define TTL/invalidation in config and emit cache-source marker in debug payloads.
- Avoid unbounded lineage scans per gate call; prefer indexed latest-event + bounded parent walk.

## 10) Test and acceptance criteria

Must pass before marking implemented:
1. Determinism tests: repeated runs on identical lineage produce identical signal outputs.
2. Replay tests: `as_of_time` replay reproduces prior emitted signals.
3. Fallback tests: missing/corrupt chain paths emit deterministic fallback + reason.
4. Regression inclusion: uncertainty suites remain in `im_regression` gate.
5. Audit checks (`axis_dominance_audit.sql` or equivalent):
   - provenance metadata default-rate decreases on post-implementation traffic,
   - non-trivial three-axis ties trend down on workloads that actually call gate logic,
   - dominant-axis distribution is not a pure tie artifact.

## 11) Non-negotiable alignment

- Keep append-only lineage invariant.
- Do not treat vectors as source of truth.
- Do not auto-resolve contradictions.
- Emit deterministic machine-readable reasons for rejection/quarantine/fallback.

## 12) Implementation planning note

Promotion of this spec is not implementation. Implementation should proceed in small auditable phases with lineage-first observability.