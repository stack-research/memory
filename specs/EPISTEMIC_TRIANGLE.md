```yaml
spec: EPISTEMIC_TRIANGLE
status: canonical
version: v1.2
promoted_from: notes/agent-pov/proposals/EPISTEMIC_TRIANGLE.md
promoted_at_tai: "2026-05-14T23:43:28.363"
promoted_at_solar_age_myr: 4603.00002636684
promoted_at_ecliptic_lon_deg: 234.13360421505277
authoring_substrate: claude-opus-4-7
review_substrate: openai-gpt-5.5
review_passes: 3
audit_ratio_observed: [7, 7, 3]   # blockers -> ambiguities -> cautions; converged
canonical_table: memory_lab.memory_events_v7
schema_version: "7.0"
cites:
  - specs/THREE_AXIS_UNCERTAINTY.md
  - specs/PROVENANCE_SIGNAL_WRITER.md
  - specs/TAI_TIMEKEEPING.md
  - notes/MEMORY_!=_REALITY.md
  - notes/THEORY_STRESS_AND_IMPLICIT_MEMORY.md
  - AGENTS.md
```

# EPISTEMIC_TRIANGLE — canonical spec

Promoted from `notes/agent-pov/proposals/EPISTEMIC_TRIANGLE.md` v1.2 on TAI `2026-05-14T23:43:28.363` after three cross-substrate review passes (gpt-5.5). Body content is identical to the v1.2 proposal; this header replaces the proposal frontmatter.

## Implementation gates carried forward from the v1.2 promotion review

These are not part of the v1 spec text. They are implementation-time hooks the cross-substrate reviewer named as cautions when recommending promotion. They MUST be exercised before declaring the v7 implementation complete.

1. **Bootstrap same-batch resolution.** Falsification hook proving `canonical_table_genesis(seq=0)` resolves its `time_context_id` against same-batch `time_context_declared(seq=1)` per TAI v1.2 §6.2. Genesis must not be flagged as dangling.
2. **Cache discipline.** Audit query proving `signal_source = "cache"` events are backed by canonical `*_signals_computed` lineage events at `as_of_time`, not by S3 Vector metadata. Vector metadata may accelerate lookup; canonical lineage decides replay.
3. **Decision-event subjects without prior `subject_event_id`.** Implementation must either ensure subject events are emitted before any decision carrying an `uncertainty_triple`, OR define a deterministic placeholder subject event (e.g. `memory_id_referenced`). Provider intuition MUST NOT silently fill `subject_assertion_kind`.

## 1. Summary

A v7 epoch shipping:

1. **Two-axis envelope taxonomy** — `record_kind` + `assertion_kind`, with subject classification on decision events.
2. **`compute_claim_signals`** — lineage walker for `confidence_in_claim`, consuming `evidence_link_declared` events with deterministic link identity and latest-state semantics.
3. **`compute_recall_signals`** — lineage walker for `confidence_in_recall_process`.
4. **Drop legacy `event_time`** — explicit ordering rules for single-stream vs cross-stream walkers.
5. **Resolve genesis `seq=0`** via `StreamState` initialization plus dedicated `__canonical_meta__` stream.
6. **Explicit v7 canonical schema** — table, version, hot columns named.

Out of v7 scope: EventBridge → SQS → loop wiring (separate follow-on `CONTROL_PLANE_INGEST`).

## 2. Motivation

Same as v1.0/v1.1: closes drift points #1, #2, #5, #7 from the 2026-05-14 lab-as-memory-layer observation. Drift #6 (control-plane stubs) moves to the follow-on. The 2026-05-14T17:47:57.222 operator override makes the schema bump cost effectively zero.

## 3. Two-axis envelope taxonomy

### 3.1 `record_kind` (required, non-nullable)

Closed enum (v1):

| value | meaning |
|---|---|
| `lineage_meta` | system records about lineage itself (table genesis, time context declaration, batch commit, snapshot, signal computation, evidence link, event-type declaration) |
| `memory_event` | events that store, retrieve, modify, or assess a memory trace |
| `decision_event` | events recording a system decision (admission, rejection, gate evaluation, defer, no_op, contamination flag) |
| `observation_event` | events recording an observer's read of external state |
| `policy_event` | events recording policy mutation, threshold updates, procedure supersession |

### 3.2 `assertion_kind` (required when `record_kind ∈ {memory_event, observation_event}`; nullable otherwise)

Closed enum (v1):

| value | meaning |
|---|---|
| `belief` | internal confidence-weighted acceptance of a proposition |
| `claim` | proposition asserted by a source, not yet evidence-anchored |
| `memory` | stored trace plus metadata, no current assertion about reality |
| `evidence` | externally-anchored support for a claim |
| `reality_observation` | an observer's read of external state; the observation enters lineage, **reality itself does not** |

`reality_observation` is permitted only when `record_kind == observation_event`. Reality remains unknowable; only observations enter lineage.

### 3.3 Subject classification on decision events (new in v1.2)

Decision events do not themselves carry `assertion_kind` (the decision is not a claim). But they decide *about* memory/claim/evidence subjects, and `axis_distribution_by_assertion_kind` audits need the subject classification to be queryable.

Envelope addition for `record_kind == decision_event`:

```
subject_event_id: str | null
subject_record_kind: RecordKind | null
subject_assertion_kind: AssertionKind | null
```

Required when the decision event carries an `uncertainty_triple` in its payload. `subject_assertion_kind` mirrors the `assertion_kind` of `subject_event_id`. Walkers verify on emit (best-effort) and at audit time. Mismatches → `subject_kind_mismatch` quarantine.

The decision event itself remains `assertion_kind = null`. Subject classification is auditable separately and does not contaminate the decision's epistemic frame.

### 3.4 Mapping table for existing event types

| event_type | record_kind | assertion_kind |
|---|---|---|
| `canonical_table_genesis` | lineage_meta | null |
| `time_context_declared` | lineage_meta | null |
| `canonical_batch_committed` | lineage_meta | null |
| `provenance_signals_computed` | lineage_meta | null |
| `provenance_signals_written_to_vector` | lineage_meta | null |
| `snapshotted` | lineage_meta | null |
| `evidence_link_declared` | lineage_meta | null |
| `event_type_declared` | lineage_meta | null |
| `stored` | memory_event | per payload |
| `recalled` | memory_event | memory |
| `implicit_admitted` | decision_event | null (subject_assertion_kind required) |
| `implicit_rejected` | decision_event | null (subject_assertion_kind required) |
| `implicit_trigger_evaluated` | decision_event | null |
| `implicit_trigger_fired` | decision_event | null |
| `implicit_trigger_deferred` | decision_event | null |
| `reflex_action_executed` | decision_event | null |
| `reflex_mode_entered` | decision_event | null |
| `reflex_mode_exited` | decision_event | null |
| `observed` | observation_event | reality_observation |
| `contamination_suspected` | decision_event | null |
| `policy_threshold_updated` | policy_event | null |
| `policy_procedure_superseded` | policy_event | null |

Control-plane ingest event types — `control_cue_ingested`, `control_cue_rejected`, `control_cue_duplicate_ignored`, `control_cue_dlq_recovered`, `control_cue_dlq_abandoned` — are declared in `specs/CONTROL_PLANE_INGEST.md` §7 and registered in `src/epistemic_triangle/mapping.py`. They reach the canonical mapping through the §3.5 extension discipline and are intentionally not duplicated into the table above: single source of truth, avoiding the doc drift the lab's conventions guard against.

### 3.5 Mapping extension discipline (new in v1.2)

Closed mapping is safe; extension discipline keeps it from becoming friction. New event types enter the mapping table by **both**:

1. **Spec amendment** — add a row to §3.4, lineage-visible as a documentation commit.
2. **`event_type_declared` lineage event** — emitted once at runtime per new event_type, `record_kind == lineage_meta`, payload includes:
   - `declared_event_type: str`
   - `declared_record_kind: RecordKind`
   - `declared_assertion_kind: AssertionKind | null`
   - `declaration_reason: str`

Walkers consult the latest `event_type_declared` state plus §3.4 at audit time. Unmapped event types at emit time → `unmapped_event_type` quarantine. The two-channel mapping (config + lineage) prevents both silent drift (spec without declaration) and silent additions (declaration without spec).

### 3.6 Validation

`_validate_event` rejects:
- missing `record_kind` → `missing_record_kind`
- `record_kind` not in v1 enum → `invalid_record_kind`
- `record_kind in {memory_event, observation_event}` and `assertion_kind is None` → `missing_assertion_kind_for_record_kind`
- `assertion_kind == "reality_observation"` and `record_kind != "observation_event"` → `reality_observation_outside_observation_event`
- `assertion_kind` not in v1 enum → `invalid_assertion_kind`
- `record_kind == "decision_event"`, payload has `uncertainty_triple`, and `subject_assertion_kind` is None → `missing_subject_assertion_kind`
- `subject_event_id` resolves to event whose `assertion_kind` differs from `subject_assertion_kind` → `subject_kind_mismatch`

## 4. `evidence_link_declared` event type

### 4.1 Schema

```
event_type: "evidence_link_declared"
record_kind: lineage_meta
assertion_kind: null
payload:
  link_id: str                   # deterministic, see §4.2
  link_type: "supports" | "refutes"
  claim_event_id: str
  evidence_event_id: str
  resolution_state: "pending" | "resolved" | "invalid"
  resolution_reason: str | null  # closed enum, required when state in {pending, invalid}
```

### 4.2 Deterministic link identity (new in v1.2)

```
link_id = sha256(
    json_canonical({
        "claim_event_id": claim_event_id,
        "evidence_event_id": evidence_event_id,
        "link_type": link_type,
    })
).hexdigest()
```

The same `(claim, evidence, type)` produces the same `link_id` deterministically. Validators verify `payload.link_id` matches the recomputed hash; mismatch → `invalid_link_id` quarantine.

### 4.3 Latest-state walker rules (new in v1.2)

Walkers operating on `evidence_link_declared` events:

1. Group events by `link_id`.
2. For each `link_id`, select the latest state as of `as_of_time` by canonical ordering (§8.1 for single-stream, §8.2 for cross-stream).
3. Consume only links whose latest state is `resolved`.
4. If the latest state is `invalid`, the link does not contribute even if a prior `resolved` state exists for the same `link_id`. Invalidation supersedes earlier resolution.
5. If the latest state is `pending`, the link does not contribute.

Append-only is preserved: prior states remain in lineage; the walker simply selects the most recent applicable state. Audit queries can replay the full state history per `link_id`.

### 4.4 Resolution states

- `pending` — emitted when one or both referenced ids do not resolve at emit time. `resolution_reason` ∈ `{claim_not_yet_emitted, evidence_not_yet_emitted, both_unresolved}`.
- `resolved` — emitted when both refs resolve to events with correct `assertion_kind`:
  - `claim_event_id` → `assertion_kind ∈ {claim, belief}`
  - `evidence_event_id` → `assertion_kind ∈ {evidence, reality_observation}`
- `invalid` — emitted when resolution fails terminally. `resolution_reason` ∈ `{claim_assertion_kind_mismatch, evidence_assertion_kind_mismatch, dangling_after_grace_period}`.

### 4.5 Cross-stream / cross-agent scope

Walkers default to within-agent scope (same `agent_id`). Cross-agent links require explicit policy flag `cfg.retrieval_policy.allow_cross_agent_evidence = True`. Unauthorized cross-scope attempts emit `rejected` with `CROSS_SCOPE_REFERENCE_ATTEMPT`.

## 5. `compute_claim_signals`

Location: `src/explicit_memory/claim.py` (new).

Inputs (all lineage-derived):
- target event (the claim being scored)
- canonical lineage reader
- `as_of_time: PhysicalMoment`
- bounded depth (default 64)
- scope policy

Outputs:
```
ClaimSignals(
  evidence_support_count: int,
  refutation_count: int,
  evidence_diversity: float,
  signal_source: str,                 # see §7
  signal_method: str,                 # "evidence_links"
  fallback_reason: str | None,
)
```

Closed `fallback_reason` enum (v1):
- `no_evidence_links`
- `not_claim_kind`
- `walk_depth_exceeded`
- `assertion_kind_unset`
- `cross_scope_denied`

## 6. `compute_recall_signals`

Location: `src/explicit_memory/recall_signals.py` (new).

Inputs (all lineage-derived):
- target `recalled` event
- canonical lineage reader
- `as_of_time: PhysicalMoment`
- bounded history window (default last 64)
- scope policy

Outputs:
```
RecallSignals(
  recall_count: int,
  reconstruction_variance: float,             # [0, 1]; payload-drift metric
  time_since_last_recall_myr: float | None,
  signal_source: str,
  signal_method: str,                 # "recall_history"
  fallback_reason: str | None,
)
```

### 6.1 What `reconstruction_variance` measures

Jaccard distance over `{memory_id, assertion_kind, payload.claim, payload.evidence_ids}` measures **payload drift, not recall-process integrity in general.** Adversarial recalls that keep the projection stable while shifting semantic meaning will be undetected by v1.

Acceptable as v1 because:
- The metric is replay-deterministic.
- It catches the most common degradation pattern.
- §11 hook 6 explicitly tests the adversarial case where v1 cannot detect the drift, recording the limitation in lineage.

v8 candidate: embedding-distance variant with pinned model + content hash.

## 7. Normalized signal taxonomy across axes (new in v1.2)

Provenance currently uses `provenance_signal_source` with one vocabulary; v1.1 introduced different vocabulary for claim and recall. v1.2 normalizes.

### 7.1 Common shape on all three signal types

```
signal_source: "computed" | "cache" | "fallback"
signal_method: "provenance_chain" | "evidence_links" | "recall_history" | "none"
fallback_reason: str | None         # closed per-axis enum
```

- `computed` — signal derived from a live lineage walk at score time.
- `cache` — signal derived from a previously-emitted `*_signals_computed` lineage event still valid at `as_of_time`. (Provenance currently uses this for vector-metadata write; claim/recall may use similarly in future.)
- `fallback` — signal could not be computed; default values used.

`signal_method` names which walker produced the signal. The pair `(signal_source, signal_method)` is queryable across all three axes uniformly.

### 7.2 Provenance adapter

`compute_chain_signals` v1.1 returns `provenance_signal_source ∈ {computed, cache, fallback_default}`. The adapter in v1.2:

```
def normalize_provenance_signals(old: ProvenanceSignals) -> NormalizedSignals:
    return NormalizedSignals(
        ...,
        signal_source = {"computed": "computed",
                         "cache": "cache",
                         "fallback_default": "fallback"}[old.provenance_signal_source],
        signal_method = "provenance_chain",
        fallback_reason = old.fallback_reason,
    )
```

The adapter lives in `src/explicit_memory/signals.py` (new). All three score-axis paths consume the normalized shape. Audit queries join on the common columns; per-axis interpretation branches in `score_triple` are removed.

## 8. Ordering rules (clarified in v1.2)

### 8.1 Single-stream canonical ordering

For readers consuming a single stream:

```
ORDER BY pm_tai_iso ASC,
         pm_sequence_in_stream ASC,
         event_id ASC
```

`event_id` is the deterministic tie-break (UUID, lexicographic).

### 8.2 Cross-stream within-agent ordering (new in v1.2)

`pm_sequence_in_stream` is per-stream; across streams it is not a global causal order. Cross-stream readers (claim walker following evidence links across streams, recall walker following memory_id history) use:

```
ORDER BY pm_tai_iso ASC,
         stream_id ASC,
         pm_sequence_in_stream ASC,
         event_id ASC
```

HLC cross-stream comparison is **explicitly out of scope** in v7. `pm_hlc_timestamp` is comparable only within `(timekeeping_library, timekeeping_library_version, hlc_variant)` triples per TAI v1.2 §6.1, and not used for cross-stream ordering here.

### 8.3 `event_time` removal — touch points

Repo-wide sweep. Replacement is §8.1 or §8.2 depending on reader scope.

- `src/types.py` — remove `event_time` from `MemoryEvent`.
- `src/lineage_engine.py` — remove from event construction.
- `src/storage.py` — remove from S3 ingress JSON; quarantine `legacy_event_time_present` on v7 events that carry it.
- `src/lineage_reader.py` — replace `ORDER BY event_time` per §8.1/8.2.
- `src/explicit_memory/provenance.py` — `compute_chain_signals` tie-break uses `pm_tai_iso`.
- `src/ingestion/athena_ingestion.py` — drop `event_time` column extraction.
- All SQL audits in `src/experiments/sql/` — sweep.
- `specs/PROVENANCE_SIGNAL_WRITER.md` — amend tie-break language.

## 9. Canonical v7 schema (explicit in v1.2)

### 9.1 Table

- Database: `memory_lab`
- Table: `memory_events_v7`
- Format: Iceberg
- `schema_version` payload field: `"7.0"`

### 9.2 Hot columns (denormalized for query performance)

Retained from v6:
- `pm_tai_iso`
- `pm_solar_age_myr`
- `pm_ecliptic_lon_deg`
- `pm_sequence_in_stream`
- `pm_hlc_timestamp`
- `pm_hlc_signature_eligible`
- `pm_time_context_id`

New in v7:
- `record_kind` (denormalized from envelope)
- `assertion_kind` (nullable; denormalized from envelope)
- `subject_assertion_kind` (nullable; denormalized from envelope for decision events)

Removed in v7:
- `event_time` (no longer present anywhere)

### 9.3 Ingress

v7 ingress JSON shape: same as v6 plus `record_kind`, `assertion_kind` (when applicable), `subject_event_id` / `subject_record_kind` / `subject_assertion_kind` (when applicable). `event_time` absent. Athena ingestion validates schema_version == "7.0" and extracts the three new hot columns via `json_extract_scalar`.

### 9.4 v6 lifecycle

v6 table orphaned from CDK per the lab's single-canonical-resource pattern (see `feedback-lab-single-canonical-resource`). No migration; the 2026-05-14T17:47:57.222 operator override applies.

## 10. Genesis `seq=0` — engine-level change

### 10.1 `StreamState` initialization

```
class StreamState:
    sequence: int = -1

def emit(...):
    state = streams[stream_id]
    state.sequence += 1
    ...
```

First event in any stream (including `__canonical_meta__`) gets `sequence_in_stream = 0`.

### 10.2 Bootstrap layout

v7 cutover bootstrap emits on `__canonical_meta__`:
- `canonical_table_genesis` (seq=0)
- `time_context_declared` (seq=1)
- `canonical_batch_committed` (seq=2)

Application streams' first events satisfy `sequence_in_stream == 0` cleanly.

## 11. Three-axis score function with explicit fallback policy

```
score_triple(*, base_claim, base_recall, base_provenance,
             claim_signals=None, recall_signals=None, provenance_signals=None,
             fallback_policy="conservative"):
    claim_axis = _apply(base_claim, claim_signals, formula=_claim_formula,
                        fallback_multiplier=0.5, policy=fallback_policy)
    recall_axis = _apply(base_recall, recall_signals, formula=_recall_formula,
                         fallback_multiplier=0.5, policy=fallback_policy)
    provenance_axis = _apply(base_provenance, provenance_signals,
                             formula=_provenance_formula,
                             fallback_multiplier=0.5, policy=fallback_policy)
```

Three modes per axis:
- `computed` (`signal_source == "computed"` or `"cache"`) — apply formula.
- `fallback` (`signal_source == "fallback"`) — apply `base_axis * fallback_multiplier`; decision payload includes `axis_fallback_used: True` and `axis_fallback_reason: <enum>`.
- `none` (signal is None) — only allowed on `schema_version < 7.0` paths; reduces to scalar input.

**Invariant:** fallback default never silently means "good." `fallback_multiplier = 0.5` is arbitrary-but-conservative v1 policy; emitted in lineage as `policy_fallback_multiplier` so it is auditable and tunable. Future amendment may make it per-axis.

### 11.1 `score_candidate` retirement scope (clarified in v1.2)

Forbidden on **v7 event-emitting code paths**, not at the import level. The static check targets:

- `score_candidate(` call expressions inside functions named in `V7_EMIT_FUNCTIONS` registry (loop tick, admission, recall, contamination).
- Runtime marker: every v7 decision payload carries `scoring_function: "score_triple"`. Audit query catches any `score_candidate` leak.

Imports in mixed modules remain legal during transition. `score_candidate` retained as a pure function for offline analysis until v8.

## 12. Quarantine reason additions (closed enum)

- `missing_record_kind`
- `invalid_record_kind`
- `missing_assertion_kind_for_record_kind`
- `reality_observation_outside_observation_event`
- `invalid_assertion_kind`
- `unmapped_event_type`
- `missing_subject_assertion_kind`
- `subject_kind_mismatch`
- `legacy_event_time_present`
- `invalid_link_id`
- `evidence_link_claim_kind_mismatch`
- `evidence_link_evidence_kind_mismatch`
- `evidence_link_dangling_after_grace_period`

## 13. Falsification hooks

`src/experiments/implicit/im_u_epistemic_triangle.py` (new). All hooks deterministic, all replay-grounded.

1. **`record_kind` and `assertion_kind` round-trip.** Every event emit → store → ingest → canonical carries both fields unchanged. Enum violations → deterministic quarantine.
2. **Mapping table coverage.** Every event_type emitted anywhere in the codebase has a row in §3.4 OR an `event_type_declared` lineage event. Static + runtime check.
3. **Decision event subject classification.** Every decision event carrying `uncertainty_triple` includes `subject_assertion_kind` matching its `subject_event_id`.
4. **`evidence_link_declared` deterministic identity.** `link_id == sha256(canonical({claim, evidence, link_type}))`. Mismatch → quarantine.
5. **Latest-state walker semantics.** Walker presented with `pending` → `resolved` → `invalid` history for same `link_id` does not contribute the link; with `pending` → `resolved` → `resolved` (re-confirmation) contributes; with `resolved` → `invalid` → `resolved` contributes (latest wins).
6. **Recall variance limitation hooks:**
   - 6a wording drifts but evidence IDs stable → variance moves
   - 6b evidence IDs drift but claim text stable → variance moves
   - 6c adversarial recall keeps projection stable while semantic meaning shifts → variance does NOT move; v1 limitation marker emitted in lineage
7. **`time_since_last_recall_myr` replay-deterministic.** No wall-clock anywhere in the path.
8. **Score-time fallback visibility.** Decision events carrying `axis_fallback_used: True` include closed-enum `axis_fallback_reason` per affected axis; `policy_fallback_multiplier` emitted alongside.
9. **Normalized signal_source across axes.** `claim_signals.signal_source`, `recall_signals.signal_source`, and normalized provenance all use `{computed, cache, fallback}`.
10. **`score_candidate` retirement, precision-targeted.** No `score_candidate(` call inside any function in `V7_EMIT_FUNCTIONS`. v7 decision payloads carry `scoring_function == "score_triple"`. Imports in mixed modules tolerated.
11. **Ordering replacement.** No v7 SQL or Python reader uses `event_time` for ordering. Cross-stream walkers use §8.2 ordering, not §8.1.
12. **Engine `seq=0`.** First event in `__canonical_meta__` and first event in every application stream both have `sequence_in_stream == 0`.
13. **`event_time` absent on v7 events.** Ingress with `event_time` field → `legacy_event_time_present` quarantine.
14. **Cross-scope evidence link policy.** Cross-agent `evidence_link_declared` denied unless flag set; denial emits `CROSS_SCOPE_REFERENCE_ATTEMPT`.
15. **`reality_observation` scope.** `assertion_kind == "reality_observation"` only on events with `record_kind == "observation_event"`.
16. **Mapping extension via `event_type_declared`.** A new event_type emitted before its `event_type_declared` lineage event → `unmapped_event_type` quarantine. After declaration → admitted.

## 14. Audit query updates

- `axis_distribution_by_assertion_kind` — joins on `assertion_kind` for memory/observation events AND on `subject_assertion_kind` for decision events. Reports tie-rate AND `signal_source` distribution per kind.
- `axis_distribution_by_record_kind` — new; reports the same metrics grouped by `record_kind`.
- `signal_source_distribution` — new; reports `(signal_source, signal_method)` distribution per axis across the canonical table. Catches axes that always fall back.

## 15. Exit criteria

v7 is implementation-ready when:

- [x] v1.2 cross-substrate reviewed.
- [x] Spec promoted to `specs/EPISTEMIC_TRIANGLE.md` after review.
- [x] Falsification hooks pass under `make implicit-regression` (current `im_u` count: 35/35).
- [x] At least one `implicit_admitted` event in lineage carries lineage-derived claim + recall + provenance signals (all `signal_source == "computed"`) on a single decision, with `subject_assertion_kind` populated.
- [x] Cross-substrate **code review** completed on `claim.py`, `recall_signals.py`, `_validate_event`, `score_triple` fallback policy, `StreamState` initialization, `evidence_link_declared` state machine + `link_id` derivation, and the `signals.py` adapter.
- [x] `AGENTS.md` reconciled: canonical table `memory_events_v7`, `event_time` removed from required envelope, `record_kind` + `assertion_kind` + decision-event subject fields added.
- [x] v6 orphaned from CDK; v7 table deployed and ingestion validated end-to-end.

## 16. Out of scope

- EventBridge → SQS → loop wiring (separate proposal `CONTROL_PLANE_INGEST`).
- Migration of v6 events to v7 (operator override).
- Reflex mapping for conversational substrates (drift #4).
- AGENTS.md/older-spec posture reconciliation pass (drift #8).
- Distributed HLC `Recv` path.
- HLC cross-stream comparison.
- Embedding-based `reconstruction_variance` (v8).
- `score_candidate` removal from offline analysis paths (v8).
- Per-axis `fallback_multiplier` tuning (v8).

## 17. Process discipline (meta-proposal, retained)

Extend cross-substrate audit to the **implementation stage**. After same-substrate implementation, lock the PR until a different substrate reads:

- `compute_claim_signals` walk + fallback discipline
- `compute_recall_signals` variance computation and replay determinism
- `_validate_event` enforcement (record_kind, assertion_kind, subject fields)
- `StreamState` initialization (one-line change, high blast radius)
- `evidence_link_declared` state machine and `link_id` derivation
- `signals.py` adapter for cross-axis normalization

TAI v1.1 → v1.2 produced ~7 catches. EPISTEMIC_TRIANGLE v1.0 → v1.1 produced ~7 catches. EPISTEMIC_TRIANGLE v1.1 → v1.2 produced ~7 smaller catches. The pattern is now three data points: same-substrate authoring leaves ~7 structural-or-tightening ambiguities per round that a different substrate finds in one read. The implementation-stage audit gate is no longer aspirational; it is empirically necessary.

## 18. What v1.2 changed vs v1.1 (summary)

| Issue (v1.1) | Resolution (v1.2) |
|---|---|
| Decision events lose subject classification when `assertion_kind = null` | §3.3 + §3.6: `subject_event_id` / `subject_record_kind` / `subject_assertion_kind` envelope fields; required on decision events carrying uncertainty triples |
| `evidence_link_declared` lacks deterministic link identity | §4.2: `link_id = sha256(canonical({claim, evidence, type}))`; quarantine on mismatch |
| Walker semantics ambiguous for multiple link events over time | §4.3: group by `link_id`, select latest state at `as_of_time`; invalid supersedes earlier resolved |
| Cross-stream ordering implied per-stream sequence had global meaning | §8.2: cross-stream walkers use `(pm_tai_iso, stream_id, pm_sequence_in_stream, event_id)`; HLC cross-stream explicitly out of scope |
| v7 canonical schema not stated explicitly | §9: table name, schema_version, hot columns named directly |
| Signal-source vocabulary differs per axis (lineage_chain vs computed/cache/fallback) | §7: normalized `(signal_source, signal_method, fallback_reason)` shape across all axes; provenance adapter |
| `score_candidate` static import ban too blunt | §11.1: target call expressions inside `V7_EMIT_FUNCTIONS` registry, not imports; runtime marker on decision payloads |
| No discipline for adding new event types to mapping | §3.5: spec amendment + `event_type_declared` lineage event, both required |

## 19. Where I'm probably wrong (v1.2)

- **`signal_method` is the right shape but the values may need to grow.** A future caching layer could need `cache_warm` vs `cache_cold`; provenance may grow `provenance_chain_partial`. v1 picks the simplest viable set; v8 may widen.
- **`subject_assertion_kind` requires the subject event to have already been emitted.** For decisions made about not-yet-emitted subjects (rare but possible in lookahead/predictive flows), this could force ordering. v1.2 punts; if the case arises, an amendment allowing `subject_assertion_kind = "pending_emit"` is the natural fix.
- **`fallback_multiplier = 0.5` still arbitrary.** v1.2 makes it auditable (emitted in lineage as policy) but doesn't tune it. First post-deployment audit should histogram per-axis fallback rates; if any axis falls back >50% of the time, the multiplier is doing more work than the formula.
- **`event_type_declared` adds a runtime emission per new event_type.** Cheap, but it's still one more thing to forget. The §3.5 discipline says both spec AND declaration are required; a missing declaration is caught at quarantine time, but a missing spec amendment is caught only at audit. Process discipline, not schema enforcement.

## 20. Net

v1.2 is a text-tightening pass over v1.1's structure, not another redesign. The reviewer's verdict on v1.1 was "implementation-shaping ambiguities worth tightening before promotion," not "do not implement." v1.2 closes all seven and adds one (mapping extension discipline) that emerged from thinking through the §3.5 question.

The proposal is now spec-promotion shape. Ready for cross-substrate re-review.
