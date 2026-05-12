```
agent: claude-opus-4.7
date: 2026-05-12
prompt: "ship all 5"
kind: proposal
cites:
  - 2026-05-12-axis-distribution-from-runs
  - specs/THREE_AXIS_UNCERTAINTY
```

# Provenance Signal Writer (proposal)

Status: proposal — not yet promoted to `specs/`.

## 1) Problem

The three-axis uncertainty model has a structural correctness, but the third axis (`confidence_in_provenance_chain`) reads inputs that no producer in this repo currently writes.

Production code paths today:

- [`src/explicit_memory/recall.py`](../../../src/explicit_memory/recall.py) lines 85-87 reads provenance signals from S3 Vectors metadata with defaults `parent_chain_depth=0.0`, `source_diversity=1.0`, `age_of_original_source=hours_stale`.
- [`src/implicit_memory/loop.py`](../../../src/implicit_memory/loop.py) lines 480-482 and 573-575 hardcode the provenance signals to roughly `(0.0, 1.0, 0.0)` and a sensor-spread alias.
- No call site in `src/` writes `parent_chain_depth` or `source_diversity` into vector metadata at storage time.

Measured impact (from [`notes/agent-pov/2026-05-12-axis-distribution-from-runs.md`](../2026-05-12-axis-distribution-from-runs.md)): 18 of 20 triple-bearing events in regression suites A–K have all three axes evaluated to identical values. `dominant_axis` collapses to a Python dict-iteration tiebreak. The third axis carries no decision-shaping signal in the current workload.

`score_triple` is correct math. It does not have correct inputs.

## 2) What this proposal adds

A two-part producer:

### 2a) Storage-time signal writer

When a memory is stored in S3 Vectors via `RecallVectors.put_memory_vector`, compute provenance signals from the canonical lineage chain and write them into the vector's `metadata` dict alongside the existing fields (`source_trust`, `hours_stale`, etc.).

Required computed fields:
- `parent_chain_depth: int` — count of `parent_event_id` hops from this memory's most recent canonical event back to its root event (root = first event with `memory_id` equal to this memory and `parent_event_id` null).
- `source_diversity: float` — `unique(source_class) / count(events_in_chain)`, clamped `[0, 1]`. Single-source chains score 1/N; multi-source chains score higher.
- `age_of_original_source_hours: float` — hours between root event's `event_time` and the current write time.

These are computed once at write time and not recomputed at read time. If the chain changes (new events appended), the next vector write for that memory picks up the new chain.

### 2b) Implicit-loop signal lookup

When the implicit loop calls `eligibility_gate`, it should look up the current provenance signals for the candidate `memory_id` from the canonical lineage rather than hardcoding zeros. The simplest implementation: cache the most recent root-to-leaf chain per `memory_id` in `procedure_state/` and consult it during gating.

Both writers must emit a corresponding lineage event so the computation itself is auditable.

## 3) Lineage events introduced

Two new event types:

- `provenance_signals_computed`
- `provenance_signals_written_to_vector`

Both events live in the standard envelope. Their payloads share a `provenance_signals` block matching the existing one, plus:

```json
{
  "provenance_signals": {
    "parent_chain_depth": 3,
    "source_diversity": 0.5,
    "age_of_original_source_hours": 47.2
  },
  "chain_root_event_id": "evt-...",
  "chain_length": 6,
  "distinct_source_classes": ["sensor", "user_input", "internal_engine"],
  "computed_at": "2026-05-12T..."
}
```

`chain_root_event_id` is the load-bearing field. Without it, the computation cannot be replayed.

## 4) Determinism and replay

The signal writer must be deterministic given the same canonical lineage state. Replay rule: at any past time `T`, computing signals for memory `M` from events with `event_time <= T` must yield the same triple every time.

This is currently testable because `rebuild_from_lineage` now (after item 1 in the previous reaction) hashes decision payload — if the writer emits the signals deterministically, replay signature should match across runs.

## 5) Non-goals

- v1 of this proposal does NOT require recomputing signals for old vectors. Old vectors keep their defaults (or no metadata) and read paths fall back to the existing defaults. The migration story is: signals appear on newly-written or re-written vectors only.
- v1 does NOT require a global re-index. A re-index is a separate decision and probably should not be coupled to this proposal.
- v1 does NOT require provenance signals on every event type — only on storage events and gating events. Trigger-evaluation, deferral, reflex, and observed events remain triple-free until a separate proposal addresses their coverage.

## 6) Mapping to current code

Files that change:

- [`src/vectors.py`](../../../src/vectors.py) — `put_memory_vector(...)` accepts and writes the three provenance fields into metadata.
- [`src/explicit_memory/recall.py`](../../../src/explicit_memory/recall.py) — read path stops aliasing `hours_stale` into `age_of_original_source`; read it directly from metadata.
- [`src/implicit_memory/loop.py`](../../../src/implicit_memory/loop.py) — observation and cue paths consult the cached chain for the candidate `memory_id` instead of hardcoding zeros.
- New file: `src/explicit_memory/provenance.py` — compute_chain_signals(memory_id, lineage_reader) -> dict.
- New file: maybe `src/implicit_memory/provenance_cache.py` — small read-through cache keyed on `memory_id`, persisted in `procedure_state/`.

Estimated diff: a few hundred lines. Concentrated in three files plus two new files.

## 7) Falsification hooks

Hooks that, if triggered, refute that this proposal added real signal.

1. After the writer is live, re-run the axis-distribution audit (the scratch inspector from the prior entry, or the new SQL query at `src/experiments/sql/axis_dominance_audit.sql`). If `non_trivial_three_axis_ties` is still ≥80% of triple events on a real workload, the writer is producing constants and is decoration.

2. If `dominant_axis` distribution remains >90% `claim` after the writer is live, the writer is not lowering the provenance axis enough to make it dominate where it should. (Suite M shows the math can produce provenance-dominant outcomes; absence of such outcomes in real traffic means the inputs are still degenerate.)

3. If `decision_signature` (post item 1) does not change between a pre-writer run and a post-writer run on the same workload, the writer is making no decision-changing contribution. Pure decoration.

4. If the writer's `provenance_signals_computed` events are themselves non-deterministic across replays of the same lineage, the writer is reading state outside lineage and the replay invariant breaks. That is worse than the gap this proposal is trying to close.

## 8) Promotion path

Per the convention in [`notes/agent-pov/README.md`](../README.md):

1. This proposal lives in `notes/agent-pov/proposals/` until promoted.
2. Promotion to `specs/PROVENANCE_SIGNAL_WRITER.md` requires owner sign-off.
3. Implementation begins after promotion. Implementation is a separate plan.
4. The current entry stays in `proposals/` as a breadcrumb after promotion.

## 9) Open questions

- `source_class` is a free-form string in the current envelope. `source_diversity` as a counted-unique signal is only as meaningful as the discipline applied to that field. Worth verifying the source_class taxonomy before relying on diversity numerics.
- Should `age_of_original_source_hours` be computed at write time or read time? Write time means stale signals on cold memories; read time means non-deterministic signals under replay. Proposal leans write-time for determinism.
- Cache invalidation in the implicit loop: at what cadence does the loop re-read the chain? On every gate call? On a tick? On every appended event? Each has tradeoffs the spec should pin down.

## 10) Why this matters

The three-axis uncertainty spec moved the system from "one scalar" to "three labeled scalars." The labels carry meaning only when their inputs differ. Without this writer, the labels are decorative and the audit hook at `axis_dominance_audit.sql` will keep showing >90% ties in production.

This proposal closes that gap. It is the difference between "we have axes" and "axes inform decisions."
