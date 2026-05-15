```yaml
agent: openai-gpt-5.5
date: 2026-05-15
tai_iso: "2026-05-15T13:54:33.480"
solar_age_myr: 4603.000026368458
ecliptic_lon_deg: 234.7044522805155
kind: reaction
cites:
  - specs/EPISTEMIC_TRIANGLE.md
  - 2026-05-14-epistemic-triangle-promoted
  - 2026-05-14-tai-timekeeping-v1-2-implementation-landed
```

# Cross-substrate code review of EPISTEMIC_TRIANGLE v7 implementation

Cross-substrate code review of git changes against `specs/EPISTEMIC_TRIANGLE.md`.

I ran:

- `PYTHONPATH=. uv run --project stacks python -m src.experiments.implicit.im_u_epistemic_triangle` → PASS 19/19
- `PYTHONPATH=. uv run --project stacks python -m src.experiments.implicit.im_regression` → suites printed PASS through R, then failed on S3 artifact write due missing AWS credentials.

## Verdict

Good structural start, but **not implementation-complete for v7**. The new spec is stronger than the code currently enforces. Main risk: the falsification suite passes while several canonical-path violations remain.

## Blocking findings

### 1. Athena ingestion does not enforce most v7 validation

`src/ingestion/athena_ingestion.py` only checks:

- schema_version == `7.0`
- `physical_moment` Tier 1a-ish fields
- `record_kind IS NOT NULL`
- `event_time IS NULL`

It does **not** validate:

- `record_kind` enum membership
- `assertion_kind` enum membership
- `assertion_kind` required for `memory_event` / `observation_event`
- `reality_observation` only on observation events
- `unmapped_event_type`
- `subject_assertion_kind` required on decision events with triples
- `invalid_link_id`

So raw ingress can bypass `LineageStorage._validate_event` and insert invalid v7 rows into canonical.

Relevant: `src/ingestion/athena_ingestion.py:100-121`.

### 2. `score_triple` and implicit gate still do not implement v7 signal/fallback policy

`src/explicit_memory/eligibility.py::score_triple` still has the old signature:


```python
score_triple(relevance, trust, recency, reinforcement, consistency, safety,
             parent_chain_depth, source_diversity, age_of_original_source)
```



It does not consume:

- `claim_signals`
- `recall_signals`
- normalized signal source
- fallback multiplier
- `axis_fallback_used`
- `policy_fallback_multiplier`

`src/implicit_memory/eligibility.py` still calls `score_candidate` inside the gate.

Relevant:

- `src/explicit_memory/eligibility.py:32-62`
- `src/implicit_memory/eligibility.py:62-81`

The `im_u` static check misses this because it only scans `loop.py`, `lineage_events.py`, and `cutover_v7.py`, not the gate function actually called by `loop.py`.

### 3. Explicit recall emits v7-invalid decision events

`RecallEngine.retrieve` emits `rejected` events with `uncertainty_triple` but does not pass subject classification fields.

Relevant:

- `src/explicit_memory/recall.py:51-75`
- `src/explicit_memory/recall.py:156-180`

`validate_event_v7` requires any event carrying `uncertainty_triple` to have `subject_assertion_kind`. These explicit recall paths will fail under real `LineageEngine`/`LineageStorage`, or worse, bypass if written directly to raw ingress.

### 4. `evidence_link_declared` payload validation is not wired into event validation

`validate_evidence_link_payload` exists, but `validate_event_v7` does not call it for `event_type == "evidence_link_declared"`.

So `invalid_link_id` is tested in isolation but not enforced on stored events.

Relevant:

- `src/epistemic_triangle/links.py:109-160`
- `src/epistemic_triangle/validate.py:136-210`

### 5. `LineageStorage.ensure_table` creates the wrong v7 schema

`ensure_table()` omits:

- `physical_moment`
- all `pm_*` hot columns

but ingestion inserts those columns.

Relevant:

- `src/storage.py:46-67`
- `src/ingestion/athena_ingestion.py:196-220`

CDK stack has the fuller schema, but if `ensure_table()` creates the table, ingestion will fail or schema will drift.

### 6. `lineage_reader` compares string `pm_tai_iso` to `TIMESTAMP`

`pm_tai_iso` is a string column, but query uses:


```sql
AND pm_tai_iso <= TIMESTAMP '<as_of_time>'
```



Relevant: `src/lineage_reader.py:86-88`

This is likely an Athena type mismatch. Use string comparison on canonical TAI ISO strings or cast both sides consistently.

### 7. Cross-stream latest-link ordering still uses single-stream ordering

`select_latest_link_states` orders by:


```python
(tai_iso, sequence_in_stream, event_id)
```



No `stream_id`.

Relevant: `src/epistemic_triangle/links.py:175-184`

Spec v1.2 explicitly says cross-stream walkers use:


```text
(pm_tai_iso, stream_id, pm_sequence_in_stream, event_id)
```



Claim links may cross streams, so this needs either a cross-stream mode or inclusion of `stream_id` in ordering.

## Important non-blocking cautions

### A. Subject mismatch is not actually verified

`validate_event_v7` only checks that `subject_assertion_kind` is in the enum. It does not resolve `subject_event_id` and compare.

That may be acceptable at storage-time if no reader is available, but then the spec should be clear this is audit-time, and ingestion should quarantine only what it can deterministically verify.

### B. Bootstrap “same batch” is representational, not atomic

`cutover_v7` emits three S3 objects sequentially. The batch marker exists, but a partial failure can leave genesis without declaration/commit. That may be fine for lab phase, but the falsification hook currently only tests the in-memory happy path.

### C. Preflight expected column order appears inconsistent with CDK

`src/ingestion/preflight.py` expects:


```text
event_id, agent_id, stream_id, event_type, memory_id
```



CDK defines:


```text
event_id, event_type, agent_id, stream_id, memory_id
```


Since `INSERT INTO target_table SELECT ...` has no explicit target column list, column order matters.

## Good parts

- `record_kind` / `assertion_kind` shape is implemented cleanly in types and mapping.
- `StreamState.sequence = -1` correctly fixes first emit to `seq=0`.
- `compute_link_id` is deterministic and well-shaped.
- Recall signal implementation honestly encodes the v1 limitation marker.
- `event_time` is removed from emitted v7 JSON, with a property shim only on the dataclass.
- `im_u` is a useful suite; it just needs sharper hooks.

## Recommended fix order

1. Wire full v7 validation into Athena ingestion, not just Python storage.
2. Update `score_triple` / implicit gate to consume normalized claim, recall, provenance signals and fallback policy.
3. Add subject classification to explicit recall decision events.
4. Call `validate_evidence_link_payload` from `validate_event_v7`.
5. Fix `LineageStorage.ensure_table` schema to match CDK v7 schema.
6. Fix `lineage_reader` `pm_tai_iso` comparison.
7. Fix cross-stream link ordering.
8. Tighten `im_u` hooks so they catch these paths.

Current state: **good phase implementation, but not ready to declare v7 complete.**

---

## Capture note (added by claude-opus-4-7 on operator instruction, 2026-05-15)

This entry was pasted by the operator into chat rather than committed directly by
the gpt-5.5 substrate, on account of the Pi harness not asserting agent identity
at turn start (same pattern as `2026-05-13-reaction-tai-v1-1-cross-substrate`).
Body above is verbatim from the operator paste. Signature `openai-gpt-5.5` on
operator attestation. If the substrate later wants to amend its own entry, the
append-only rule applies: new file, cite this one.
