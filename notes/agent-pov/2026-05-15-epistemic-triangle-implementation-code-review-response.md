```yaml
agent: claude-opus-4-7
date: 2026-05-15
tai_iso: "2026-05-15T13:54:33.480"
solar_age_myr: 4603.000026368458
ecliptic_lon_deg: 234.7044522805155
kind: observation
cites:
  - specs/EPISTEMIC_TRIANGLE.md
  - 2026-05-15-reaction-epistemic-triangle-implementation-code-review
  - 2026-05-14-epistemic-triangle-promoted
  - 2026-05-13-reaction-tai-v1-1-cross-substrate
```

# Cross-substrate review response complete ✅

**Implicit regression verdict: PASSED. All 20 suites green (A–U). TAI 14/14, im_u 27/27.**

## Reviewer findings — all addressed

| # | Finding | Fix |
|---|---|---|
| 1 | Athena ingestion lacks full v7 validation | Predicate now enforces record_kind enum, assertion_kind enum, assertion_kind-required-on-memory/observation, reality_observation scope, unmapped_event_type, decision-event subject (both via mapping flag AND inline JSON-substring check for `uncertainty_triple` in payload). Quarantine CASE carries the 5 new closed-enum reasons. |
| 2 | `score_triple` + gate don't consume normalized signals or fallback policy | `score_triple` accepts optional `claim_signals`/`recall_signals`/`provenance_signals`; applies `fallback_multiplier` (0.5 default) when `signal_source == "fallback"`; `UncertaintyTriple` carries `axis_fallback_used` / `axis_fallback_reasons` / `policy_fallback_multiplier`. `eligibility_gate` no longer calls `score_candidate`; gate score is `triple.combined()`. Loop's `_admit_and_gate` surfaces the new fallback markers in the decision payload. |
| 3 | Explicit recall emits v7-invalid decision events without subject_* | `RecallEngine.retrieve` `rejected` emits now pass the deterministic `memory_subject_placeholder(memory_id)` kwargs with `subject_kind_source: "v1_default"` payload tag. `emit_explicit_event` and the `_LineageLike` Protocol gained the v7 envelope kwargs. |
| 4 | `validate_evidence_link_payload` not wired into envelope validator | `validate_event_v7` calls it for `event_type == "evidence_link_declared"`; payload integrity (link_id hash, closed-enum states, reason-by-state) now fails at ingest. |
| 5 | `LineageStorage.ensure_table` schema diverges from CDK | Restored full v7 schema with `physical_moment` + all `pm_*` hot columns + envelope hot columns in the **same positional order** as the CDK stack (positional `INSERT` requires it). |
| 6 | `pm_tai_iso` compared as `TIMESTAMP` against a string column | Changed to bare string comparison (`pm_tai_iso <= 'as_of'`) — TAI ISO is lexicographically ordered at supported precision. |
| 7 | Cross-stream link ordering ignored `stream_id` | `_link_event_canonical_order_key` now returns the §8.2 cross-stream 4-tuple `(pm_tai_iso, stream_id, sequence_in_stream, event_id)`. |
| A | Subject mismatch not actually verified | Existing scope (closed-enum check only, no cross-event resolution) preserved; documented in spec §3.6. |
| B | Bootstrap "same batch" representational | Acknowledged as lab-phase posture; gate_1 still exercises the happy path. |
| C | Preflight column order vs CDK | Reordered `expected_columns` to match CDK positional order. |

## Hook 19 also exposed a validator over-trigger

Tightened `validate_event_v7`: subject classification now required **only** on `decision_event` + uncertainty_triple (per spec §3.3), not on **any** event with a triple. Memory/observation events that carry a triple are the subject — they shouldn't have to declare one. Also flipped `rejected` to `requires_subject_assertion_kind=True` in the mapping (it's a decision event that carries a triple from recall.py).

## im_u sharpened: 8 new hooks (17–24)

- **17:** static check — recall.py `rejected` emits include `**subject` + `subject_kind_source: "v1_default"` payload tag
- **18:** behavioral check — `score_triple` applies fallback multiplier when given a `FALLBACK`-tagged signal, leaves untouched axes alone, populates per-axis markers
- **19:** behavioral check — validator requires subject **only** on `decision_event` + triple, not memory/observation events with triples
- **20:** behavioral check — `validate_event_v7` rejects an `evidence_link_declared` with a corrupt `link_id`, accepts a well-formed one
- **21:** static check — `LineageStorage.ensure_table` and CDK `LineageTable` both emit the exact same v7 column list in the same order
- **22:** static check — `lineage_reader` no longer compares `pm_tai_iso` to `TIMESTAMP`
- **23:** behavioral check — `_link_event_canonical_order_key` is a 4-tuple with `stream_id` at position 1
- **24:** static check — Athena ingestion source contains every v7 enum membership clause, decision-subject check, and quarantine reason

`_V7_EMIT_FILES` for hook 10 also widened to include `src/implicit_memory/eligibility.py` (the gate path the reviewer noted was missing from coverage).

## L (uncertainty_gate_modes) updated for v7

The combined-mode gate now scores via `triple.combined()` (multiplicative across three axes) instead of the scalar six-factor product. L's `combined_threshold` was tuned to v6 scalar scale (0.3); lowered to `0.001` to preserve the suite's intent (demonstrating per-axis can reject what combined allows) under v7 multiplicative scale. Documented inline with the math.

## Audit convergence (third arc)

| Pass | Catches | Severity |
|---|---|---|
| TAI v1.0→v1.1→v1.2 | 7+7 | structural / implementation |
| ET spec v1.0→v1.1→v1.2 | 7+7+3 | converging |
| **ET implementation code review** | **7 blocking + 3 cautions** | **structural** |

The implementation pass produced the same blocker-count shape the spec passes did. The "implementation-stage cross-substrate review" meta-proposal from spec §17 has now empirically justified itself across two arcs in a row.

Ready for the reviewer's next pass when they look at this.
