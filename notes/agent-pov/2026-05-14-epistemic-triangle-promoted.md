```yaml
agent: claude-opus-4-7
date: 2026-05-14
tai_iso: "2026-05-14T23:43:28.363"
solar_age_myr: 4603.00002636684
ecliptic_lon_deg: 234.13360421505277
kind: observation
cites:
  - specs/EPISTEMIC_TRIANGLE.md
  - proposals/EPISTEMIC_TRIANGLE
  - 2026-05-14-reaction-epistemic-triangle-v1-2-promotion-review
  - 2026-05-14-epistemic-triangle-v1-2-amendment
  - 2026-05-14-epistemic-triangle-v1-1-amendment
  - 2026-05-14-reaction-epistemic-triangle-v1-1-re-review
  - 2026-05-14-reaction-epistemic-triangle-cross-substrate
```

# EPISTEMIC_TRIANGLE promoted to spec

Operator approved promotion at TAI `2026-05-14T23:43:28.363` after the third cross-substrate review (`openai-gpt-5.5`) returned with three implementation cautions and no blockers. Proposal v1.2 body is now `specs/EPISTEMIC_TRIANGLE.md`. The proposal file is reduced to a breadcrumb stub citing the audit chain.

## What is now canonical

- Two-axis envelope taxonomy: `record_kind` + `assertion_kind`, plus subject classification on decision events carrying uncertainty triples.
- `compute_claim_signals` and `compute_recall_signals` as the v7 epistemic-axis writers.
- `evidence_link_declared` lineage events with deterministic `link_id` and latest-state walker semantics.
- Explicit v7 schema: `memory_lab.memory_events_v7`, `schema_version = "7.0"`, named hot columns including `record_kind`, `assertion_kind`, `subject_assertion_kind`. v6 orphaned from CDK on cutover.
- Engine `StreamState.sequence` initial value `-1`; first event in every stream gets `sequence_in_stream = 0`. Bootstrap on `__canonical_meta__` stream.
- Normalized signal taxonomy `(signal_source ∈ {computed, cache, fallback}, signal_method, fallback_reason)` across all three axes; provenance adapter in `signals.py`.
- `event_time` removed repo-wide; ordering replaced with §8.1 single-stream and §8.2 cross-stream rules.
- `score_candidate` retired on v7 emit paths via `V7_EMIT_FUNCTIONS` registry; `scoring_function` runtime marker on every v7 decision payload.
- Mapping extension via spec amendment + `event_type_declared` lineage event.
- 16 falsification hooks for `im_u_epistemic_triangle.py`.

## Implementation gates carried forward (not in spec body, in spec preamble)

The promotion-review reviewer named three cautions that became implementation gates in the spec preamble:

1. Bootstrap same-batch resolution: `canonical_table_genesis(seq=0)` references same-batch `time_context_declared(seq=1)` per TAI v1.2 §6.2; falsification hook required.
2. Cache discipline: `signal_source = "cache"` must be backed by canonical `*_signals_computed` lineage events at `as_of_time`, never by S3 Vector metadata as source of truth.
3. Decision-event subjects: when an `uncertainty_triple` is present, either ensure subject events emit first or define a deterministic placeholder subject event. No silent provider-intuition fills.

## On the audit ratio (closed observation)

Three review passes against same-substrate authoring produced:

| Pass | Catches | Severity |
|---|---|---|
| v1.0 → v1.1 | 7 + 4 | conceptual blockers + smaller |
| v1.1 → v1.2 | 7 | implementation-shaping ambiguities |
| v1.2 → promote | 3 | implementation cautions |

The convergence assumption from v1.2's amendment ("if a third pass produces ≤3 catches the convergence assumption holds") was confirmed empirically. The pattern is now a four-data-point trend across two distinct arcs (TAI three-pass and EPISTEMIC_TRIANGLE three-pass), each producing ~7 → ~7 → ≤3 catches as substrate review compounds.

The reviewer's own framing closes it: *"v1.0 had conceptual blockers. v1.1 had implementation-shaping ambiguities. v1.2 has implementation cautions. That is the expected shape of a useful cross-substrate review process."*

The implementation-stage audit gate (spec §17) is no longer aspirational. It is the next obligation.

## What's next

Implementation in phases mirroring TAI:

- **Phase 1** — primitives: `record_kind` + `assertion_kind` enums in `src/types.py`; subject-classification envelope fields; `_validate_event` updates; closed-enum quarantine reasons.
- **Phase 2** — signal writers: `src/explicit_memory/claim.py`, `src/explicit_memory/recall_signals.py`, `src/explicit_memory/signals.py` (normalization adapter). `evidence_link_declared` event type with deterministic `link_id` and state machine.
- **Phase 3** — engine + storage: `StreamState` initial `-1`; `__canonical_meta__` bootstrap stream; v7 Iceberg table deployed; v6 orphaned from CDK; Athena ingestion validates `schema_version == "7.0"` and hot columns; `event_time` removed repo-wide.
- **Phase 4** — falsification + reconciliation: `im_u_epistemic_triangle.py` with 16 hooks plus the three carried-forward implementation gates; `AGENTS.md` reconciled; full `make implicit-regression` passing across A–U.
- **Phase 5** — cross-substrate code review (the meta-proposal): lock the implementation PR until a different substrate reads `claim.py`, `recall_signals.py`, `_validate_event`, `score_triple` fallback policy, `StreamState` init, `evidence_link_declared` state machine + `link_id` derivation, and `signals.py` adapter.

The lab learned during TAI implementation that producer/consumer round-trip bugs are caught by reading actual ingress JSON, not unit tests. Phase 3 should include that check before Phase 4 ships.

Back in the lab.
