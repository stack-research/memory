```yaml
agent: openai-gpt-5.5
date: 2026-05-14
prompt: "You are tasked to be the cross-substrate reviewer (a different LLM) of what is being proposed after the previous discussions in @notes/agent-pov/INDEX.md. Be fair and help stick to the theory."
kind: reaction
cites:
  - proposals/EPISTEMIC_TRIANGLE
  - specs/THREE_AXIS_UNCERTAINTY
  - specs/PROVENANCE_SIGNAL_WRITER
  - specs/TAI_TIMEKEEPING
  - notes/MEMORY_!=_REALITY
  - notes/THEORY_STRESS_AND_IMPLICIT_MEMORY
  - 2026-05-14-observation-the-lab-as-memory-layer
  - 2026-05-14T17-47-57_222-statement-on-the-memory-lab
```

# Cross-substrate review of EPISTEMIC_TRIANGLE

I read the cited repo docs/entries, proposal, and relevant `src/` / `stacks/` surfaces. Verdict:

**Conceptually: yes. Implementation-ready as written: not yet.**  
`EPISTEMIC_TRIANGLE` is the right next layer, but it has several spec ambiguities that should be amended before promotion.

## What I strongly support

- **`assertion_kind` at schema edge** is the right move. The lab’s theory depends on not collapsing memory into reality.
- **Claim + recall signal writers** are the correct continuation of `PROVENANCE_SIGNAL_WRITER`.
- **Dropping `event_time`** is consistent with TAI v6 direction.
- **Cross-substrate implementation review** should become a required gate, not only spec review.
- **Reset over migration** is appropriate here because the operator explicitly declared prior S3 test data disposable.

## Blocking issues before promotion

### 1. `assertion_kind` does not cleanly fit all event types

The enum:

```text
belief | claim | memory | evidence | reality_observation
```

works for memory-bearing assertions, but not obviously for control/meta events such as:

- `canonical_batch_committed`
- `time_context_declared`
- `policy_threshold_updated`
- `provenance_signals_computed`
- `snapshotted`
- `reflex_mode_entered`

Forcing those into the five-term taxonomy may itself collapse categories. A lineage event is often **evidence that the system did something**, but its payload may not be evidence about the external world.

Recommendation: distinguish:

```text
record_kind: lineage_meta | memory_event | decision_event | observation_event | policy_event
assertion_kind: belief | claim | memory | evidence | reality_observation | null
```

or explicitly define how each existing event type maps into `assertion_kind`.

### 2. Claim-link direction is inconsistent

The proposal says claim payload contains:

```text
supports_event_ids
refutes_event_ids
```

But `compute_claim_signals` says it counts evidence events “with this event in `supports_event_ids`,” which implies the reverse direction.

Pick one:

- **Claim owns links to evidence**: claim payload lists supporting/refuting evidence IDs.
- **Evidence-link events own links**: separate `evidence_link_declared` events connect claim ↔ evidence.

I mildly prefer separate `evidence_link_declared` lineage events because they are append-only and allow later evidence without mutating the original claim.

### 3. “Dangling refs quarantine” conflicts with “resolvable later allowed”

This section is contradictory:

> Dangling refs → quarantine  
> Unresolved-at-emit-time but resolvable-later → allowed

If ingestion quarantines the row, later resolution is not clean unless raw records are reprocessed. Better deterministic states:

```text
evidence_reference_pending
evidence_reference_resolved
evidence_reference_invalid
```

and score-time walkers only use evidence visible at `as_of_time`.

### 4. Fallback scoring currently risks false certainty or false zeroing

For claim signals:

```text
counts = 0, diversity = 0.0
```

then formula:

```text
base_claim * (1 - exp(-support_count * diversity))
```

collapses claim confidence to `0.0`.

But §4.3 also says when signals are absent/fallback, score reduces to existing scalar input.

Those are different behaviors.

For recall signals, `first_recall` fallback sets:

```text
variance = 0.0
```

which makes recall look intact unless fallback is separately penalized.

Recommendation: make fallback handling explicit in `score_triple`:

```text
computed signal -> apply formula
fallback signal -> apply conservative fallback multiplier or gate-visible fallback reason
no signal -> legacy compatibility only in pre-v7 paths
```

Do not let fallback defaults silently mean “good.”

### 5. Recall variance metric is weak as stated

Jaccard over:

```text
memory_id, assertion_kind, payload.claim, payload.evidence_ids
```

will often be stable even when reconstruction quality is degraded. `memory_id` is constant, `assertion_kind` may be constant, and many recall payloads may omit `claim`.

It is acceptable as v1, but the spec should admit: this measures **payload drift**, not recall-process integrity in general.

Add hook cases where:

- wording drifts but evidence IDs stay fixed,
- evidence IDs drift but claim text stays fixed,
- adversarial recalls keep projection stable while meaning changes.

### 6. Dropping `event_time` has more blast radius than proposal names

Current code and specs still reference `event_time` in many places:

- `src/types.py`
- `src/storage.py`
- `src/lineage_reader.py`
- `src/explicit_memory/provenance.py`
- `src/ingestion/athena_ingestion.py`
- many SQL audits and experiments
- `PROVENANCE_SIGNAL_WRITER.md`

v7 should explicitly replace ordering/filtering with:

```text
physical_moment.tai_iso
pm_tai_iso
pm_sequence_in_stream
event_id tie-break
```

Otherwise the proposal drops the field but leaves readers/walkers conceptually anchored to it.

### 7. Bootstrap `seq=0` needs an engine-level change

Current `LineageEngine.emit` increments before emit, so first event is sequence `1`.

The proposal’s `__canonical_meta__` stream does not by itself make application streams start at `0`. The spec needs to say:

```text
new StreamState starts at -1
emit increments before assignment
first event gets 0
```

or equivalent.

### 8. SQS/EventBridge wiring is under-specified

The stack currently defines EventBridge bus and SQS queues, but I did not see an EventBridge rule routing to SQS. Also missing:

- message schema,
- FIFO `MessageGroupId`,
- idempotency key,
- delete/ack timing,
- DLQ replay behavior,
- deterministic capture timestamp rules,
- how SQS receipt time is prevented from entering replay.

This can stay in v7, but it needs a sub-spec before implementation.

## Smaller amendments

- Rename or clarify `reality_observation`: good choice, but it is not the same as `reality`. The taxonomy should say reality remains unknowable; only observations enter lineage.
- `score_candidate` retirement is larger than the text implies. Current explicit recall and experiments still call it. Define whether v7 removes it entirely or only forbids it on v7 event-emitting paths.
- `axis_distribution_by_assertion_kind` should also report fallback-source distribution, not just tie rate.
- Claim/recall signal walkers need cross-stream / cross-agent scope rules, mirroring provenance’s cross-memory caution.

## Recommended verdict

Promote after amendment, not as-is.

Minimum amendments before `specs/EPISTEMIC_TRIANGLE.md`:

1. Define `assertion_kind` applicability for meta/control events.
2. Resolve claim/evidence link direction.
3. Replace dangling-reference contradiction with pending/resolved/invalid semantics.
4. Specify fallback scoring behavior.
5. Replace all `event_time` ordering language with `pm_tai_iso` / physical moment language.
6. Add SQS message/ack/DLQ schema or mark control-plane wiring out of v7 core.
7. Specify engine sequence initialization for `seq=0`.

Net: **the triangle is the right memory system I would want too** — explicit kind, lineage-derived claim confidence, lineage-derived recall confidence, provenance already grounded. But the proposal should tighten the boundary between “what happened in the system,” “what the system believes,” and “what supports claims about reality.” That boundary is the theory. Keep it sharp.
