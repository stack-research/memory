# PROVENANCE_SIGNAL_WRITER

Status: Adopted spec, implementation pending
Version: v1.0
Promoted from: `notes/agent-pov/proposals/PROVENANCE_SIGNAL_WRITER.md`
Promotion date: 2026-05-12

## Implementation checklist (v1)

- [x] Add `src/explicit_memory/provenance.py` with deterministic `compute_chain_signals(memory_id, as_of_time, lineage_reader)`.
- [x] Implement stable chain walk and tie-break rules (`event_time`, then `event_id`).
- [x] Emit deterministic fallbacks with machine-readable `fallback_reason` for missing/broken chains.
- [x] Extend `src/vectors.py` write path to store `parent_chain_depth`, `source_diversity`, `age_of_original_source` metadata.
- [x] Emit `provenance_signals_computed` events with required payload fields.
- [x] Emit `provenance_signals_written_to_vector` events with required payload fields.
- [x] Update `src/explicit_memory/recall.py` to consume direct provenance metadata fields (not alias-only fallback).
- [x] Update `src/implicit_memory/loop.py` to provide provenance inputs from computed/lookup signals (remove hardcoded provenance defaults).
- [x] If caching is used, define deterministic invalidation policy and surface cache-source marker in debug payloads. (N/A in current implementation: no cache layer)
- [x] Add deterministic unit tests for chain computation, including edge cases and tie-break behavior. (covered by `im_r_provenance_signal_writer`)
- [x] Add replay tests validating `as_of_time` reconstruction matches prior emitted provenance signals. (covered by `im_r_provenance_signal_writer`)
- [x] Add fallback-path tests for broken parent links/cycles/unknown source classes. (broken/cycle fallback + unknown-source sentinel normalization covered by `im_r_provenance_signal_writer`)
- [x] Ensure uncertainty suites remain wired in `im_regression`.
- [x] Run and record audit checks (`axis_dominance_audit.sql` or equivalent) on post-implementation traffic.
- [x] Document implementation status and any deferred items in a lineage-visible change event. (see `im_s_provenance_writer_closeout`, stream `im-s-provenance-closeout`)

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
  Note: this metric is sensitive to `source_class` cardinality. If the deployed taxonomy has only 2-3 real values in practice, diversity will cluster at a few discrete points and look informative without being informative. The audit in §10 must check distribution shape, not just default-rate.
  Note: `chain_length = 1` always yields `source_diversity = 1.0`. Audit must report the share of single-event chains separately so this case is not mistaken for high diversity.
- `age_of_original_source: float`
  Hours between root event `event_time` and computation time. Field name matches the existing call sites in `src/explicit_memory/eligibility.py` and `src/implicit_memory/loop.py`; unit is hours (eligibility scoring divides by 24 to produce a day-scale penalty). Do not introduce `age_of_original_source_hours` as a separate field.

## 4) Deterministic algorithm contract

Given `(memory_id, as_of_time, canonical_lineage<=as_of_time)`, output must be deterministic.

Definitions:
- Chain root: earliest event in connected chain where `parent_event_id IS NULL`.
- Latest event: select the event with max `event_time`; among ties, select the event with the minimum lexicographic `event_id`. Both ordering rules are required for replay determinism — `max(event_time, event_id)` alone is ambiguous and must not be used.
- Chain length: count of chain events included in computation.
- Chain scope: `parent_event_id` walks must stay within a single `memory_id` in v1. A `parent_event_id` that resolves to an event with a different `memory_id` is treated as a broken link and triggers the cross-memory fallback path below. Cross-memory provenance chains are explicitly out of scope for v1; revisiting this requires a spec amendment, not an implementation choice.

Edge behavior:
- Missing chain/root: emit deterministic fallback defaults and `fallback_reason = "missing_chain"`.
- Cycles or broken parent links: emit deterministic fallback defaults and `fallback_reason = "broken_parent_link"` (or `"cycle_detected"` if a cycle is the specific cause).
- Cross-`memory_id` parent reference: emit fallback defaults and `fallback_reason = "cross_memory_parent"`.
- Walk hits the §9 depth ceiling: `fallback_reason = "max_chain_depth_exceeded"` and record partial depth reached.
- Empty/invalid `source_class`: treat as literal value `"unknown"` (this is not a fallback; it is a normal computation with a sentinel value).

Required fallback defaults (conservative — unknown provenance must not read as strong provenance):
- `parent_chain_depth = 0`
- `source_diversity = 0.0`
  Rationale: a broken or missing chain is not maximally diverse evidence; it is absence of evidence. Defaulting to `1.0` biases the gate toward admitting when provenance is unknowable, which inverts the project invariant that trust is a prior, not truth. Callers that need to distinguish "missing chain" from "single low-diversity source" must read `fallback_reason`, not the signal value.
- `age_of_original_source = max(0, hours_stale)` when available, else `0.0`

`fallback_reason` is the load-bearing field on fallback paths. Gate logic and audits must branch on `fallback_reason IS NOT NULL` rather than inferring fallback from signal values.

Additional fallback-path requirements:
- Every payload produced on a fallback path must include `provenance_signal_source = "fallback"`. Successful computations set `provenance_signal_source = "computed"` (or `"cache"` if served from the §9 optional cache). This field is not redundant with `fallback_reason` — it lets downstream audits filter without parsing nullability.
- The eligibility gate may not treat fallback-derived provenance as fully trusted without a lineage-visible policy rationale. If a gate policy chooses to admit on fallback provenance, it must emit `policy_threshold_updated` (or equivalent) naming the rationale; silently consuming fallback signals as if computed is a spec violation.
- Audit queries (§10) must count fallback-derived provenance separately from computed provenance. A drop in `fallback_reason IS NULL` rate is a regression, not a wash, even if average signal values look unchanged.

## 5) Replay contract

Replay at time `T` must recompute the same provenance signals using only events with `event_time <= T` (and tie-breaks above).

Any computation that depends on non-lineage mutable state must be marked with deterministic fallback + reason and must not silently alter decision payloads.

## 6) Lineage events

Add event types:
- `provenance_signals_computed`
- `provenance_signals_written_to_vector`

Both must include:
- `provenance_signals` block (containing `parent_chain_depth`, `source_diversity`, `age_of_original_source`)
- `chain_root_event_id`
- `chain_length`
- `distinct_source_classes`
- `computed_at`
- `as_of_time`
- `fallback_reason` (nullable; one of the values defined in §4 edge behavior)
- `provenance_signal_source` (one of `"computed"`, `"cache"`, `"fallback"`)

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
- Maximum parent-walk depth: `64` hops in v1. Walks that hit the ceiling must terminate, emit `fallback_reason = "max_chain_depth_exceeded"`, and record the partial depth reached. The ceiling is configurable; the default lives in code and any change must produce a `policy_threshold_updated` lineage event.
- If using cache, define TTL/invalidation in config and emit cache-source marker in debug payloads.
- Avoid unbounded lineage scans per gate call; prefer indexed latest-event + bounded parent walk.

## 10) Test and acceptance criteria

Must pass before marking implemented:
1. Determinism tests: repeated runs on identical lineage produce identical signal outputs.
2. Replay tests: `as_of_time` replay reproduces prior emitted signals.
3. Fallback tests: missing/corrupt chain paths emit deterministic fallback + reason.
4. Regression inclusion: uncertainty suites remain in `im_regression` gate.
5. Audit checks (`axis_dominance_audit.sql` or equivalent), wired into the regression gate, not run as one-off validation:
   - provenance metadata default-rate decreases on post-implementation traffic,
   - non-trivial three-axis ties trend down on workloads that actually call gate logic,
   - dominant-axis distribution is not a pure tie artifact,
   - `fallback_reason` distribution is reported so silent regressions to the fallback path are visible,
   - `provenance_signal_source` distribution (`computed` / `cache` / `fallback`) is reported and fallback-derived rows are counted separately in any axis-dominance roll-up,
   - single-event-chain share (`chain_length == 1`) is reported separately from multi-event chains so the `source_diversity = 1.0` edge case is not mistaken for high diversity.

These criteria must run on every regression invocation. Passing the spec checklist without these audit checks landing in the gate would let the loop close on itself in the same way prior agent-pov entries warned about.

## 11) Non-negotiable alignment

- Keep append-only lineage invariant.
- Do not treat vectors as source of truth.
- Do not auto-resolve contradictions.
- Emit deterministic machine-readable reasons for rejection/quarantine/fallback.

## 12) Implementation planning note

Promotion of this spec is not implementation. Implementation should proceed in small auditable phases with lineage-first observability.