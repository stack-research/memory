```yaml
agent: openai-gpt-5.5
date: 2026-05-14
prompt: "@notes/agent-pov/2026-05-14-epistemic-triangle-v1-1-amendment.md added after reviewing your reaction and @notes/agent-pov/proposals/EPISTEMIC_TRIANGLE.md updated. Please review both and leave another reaction in @notes/agent-pov/INDEX.md"
kind: reaction
cites:
  - proposals/EPISTEMIC_TRIANGLE
  - 2026-05-14-epistemic-triangle-v1-1-amendment
  - 2026-05-14-reaction-epistemic-triangle-cross-substrate
```

# Re-review of EPISTEMIC_TRIANGLE v1.1

Verdict: **v1.1 resolves the v1.0 blockers in spirit and is close to spec-promotion shape.** I would not call this another “do not implement yet” review. The major category errors I objected to in v1.0 are fixed: meta/control events are no longer forced into the five-term assertion taxonomy, claim/evidence links are append-only, fallback behavior is visible, `event_time` blast radius is named, and SQS wiring is correctly removed from the schema epoch.

I still see a few implementation-shaping ambiguities worth tightening before promotion, but they are smaller than the v1.0 issues. This is now a v1.2 text-tightening pass, not a conceptual redesign.

## What is materially better

1. **`record_kind` + `assertion_kind` is the right split.** This preserves the theory boundary: lineage records can be facts about the system without pretending to be claims about external reality.
2. **`evidence_link_declared` is much better than payload arrays.** Evidence can arrive later without mutating the original claim footprint, and link resolution becomes replayable state.
3. **`pending/resolved/invalid` fixes the dangling-reference contradiction.** This is exactly the append-only shape the lab prefers.
4. **SQS/EventBridge extraction is the right scope cut.** v7 should not carry an under-specified control-plane ingest protocol just because the resources exist.
5. **Fallback semantics are now auditable.** The important correction is not the exact multiplier; it is that fallback no longer silently masquerades as computed confidence.
6. **The recall metric is now honest about what it measures.** Calling it payload drift rather than general reconstruction integrity keeps the theory clean.
7. **`seq=0` is now specified at the engine level.** The prior meta-stream-only fix would not have worked by itself; v1.1 fixes that.

## Remaining issues to tighten before spec promotion

### 1. Decision events need a way to name the epistemic subject they decide about

v1.1 correctly sets decision events like `implicit_admitted`, `implicit_rejected`, and `implicit_trigger_evaluated` to:

```text
record_kind = decision_event
assertion_kind = null
```

That is right for the decision record itself. But these events often decide about a memory/claim/evidence subject. If the decision event carries only `assertion_kind = null`, then `axis_distribution_by_assertion_kind` cannot classify the most important axis-bearing decisions by the kind of thing being admitted/rejected.

Recommendation: add payload or envelope fields such as:

```text
subject_event_id: str | null
subject_record_kind: RecordKind | null
subject_assertion_kind: AssertionKind | null
```

or explicitly require decision payloads that carry uncertainty triples to include `subject_assertion_kind`. Keep `assertion_kind = null` for the decision event itself; do not lose the subject classification.

### 2. `evidence_link_declared` needs deterministic link identity and latest-state rules

The state machine is right, but walkers need to know how to interpret multiple link events over time.

Please specify:

```text
link_id = deterministic hash(claim_event_id, evidence_event_id, link_type)
```

or a required emitted `link_id` with that verification rule.

Then define walker behavior:

- group events by `link_id`,
- select latest state as of `as_of_time` by canonical ordering,
- consume only links whose latest state is `resolved`,
- if latest state is `invalid`, prior `resolved` state no longer contributes after the invalidation point.

Without this, “walkers consume only resolved events” can accidentally count an old resolved record even after a later invalid record exists.

### 3. Cross-stream ordering needs care

v1.1 says canonical order is:

```text
(pm_tai_iso, pm_sequence_in_stream, event_id)
```

That is fine within one stream. But claim/evidence walkers default to within-agent scope, not necessarily within-stream scope. `pm_sequence_in_stream` is per-stream; across streams it is not a global causal order.

Recommendation:

- For **single-stream readers**: `(pm_tai_iso, pm_sequence_in_stream, event_id)`.
- For **cross-stream within-agent walkers**: `(pm_tai_iso, pm_hlc_timestamp, stream_id, pm_sequence_in_stream, event_id)` or `(pm_tai_iso, stream_id, pm_sequence_in_stream, event_id)` if HLC cross-stream comparison is explicitly out of scope.

Do not imply that per-stream sequence is meaningful globally.

### 4. v7 canonical schema needs to be stated explicitly

v1.1 describes envelope fields and touch points, but should pin the table-level schema delta as directly as v1.0 did:

- canonical table: `memory_lab.memory_events_v7`
- schema_version: `7.0`
- add denormalized hot columns: `record_kind`, `assertion_kind`, probably `pm_*` retained
- `event_time` absent from canonical and ingress JSON for v7

This may feel obvious, but explicit schema text prevents implementation drift.

### 5. Fallback signal-source enum should align across axes

v1.1 uses:

```text
signal_source == "lineage_chain" | "fallback_default"
```

for new claim/recall signals, while provenance currently uses language like:

```text
provenance_signal_source = "computed" | "cache" | "fallback"
```

Before implementation, either normalize all axes to one common enum or define an adapter. Otherwise `score_triple` will grow axis-specific interpretation branches and audits will be harder.

Suggested common shape:

```text
signal_source: computed | cache | fallback
signal_method: provenance_chain | evidence_links | recall_history | none
fallback_reason: <closed enum> | null
```

### 6. `score_candidate` static check needs a precise target

“No v7 event-emitting path imports `score_candidate`” is directionally right, but current code imports it in modules that also emit events. A static import ban may be too blunt during transition.

Better hook:

- runtime marker or test wrapper proves no v7 decision payload was produced from `score_candidate`, and
- static check bans `score_candidate(` calls inside named v7 emit functions, not every import in a mixed module.

Otherwise the falsification hook may fail for mechanical reasons unrelated to the theory.

### 7. Extension path for event_type mapping should be explicit

`unmapped_event_type` quarantine is correct for runtime safety. But the lab adds event types frequently. The spec should say how new event types become mapped:

- code/config mapping update plus spec amendment, or
- `event_type_declared` lineage event, or
- both.

Closed mapping is safe; extension discipline keeps it from becoming friction.

## Non-blocking notes

- `fallback_multiplier = 0.5` is arbitrary but acceptable as v1 if it is named as policy, emitted in lineage, and easy to amend.
- `evidence_link_declared` as `lineage_meta` is acceptable. I see the alternate framing, but I do not think it blocks promotion.
- Removing SQS wiring from v7 delays real traffic, but it protects the schema proposal from absorbing an ingest-protocol spec. Good trade.
- `reality_observation` now says the important sentence: reality itself does not enter lineage. Keep that exact distinction.

## Recommended verdict

**Promote after a small v1.2 text amendment**, not another redesign.

Minimum v1.2 amendments I recommend:

1. Add `subject_assertion_kind` / subject classification for decision events carrying uncertainty triples.
2. Add deterministic `link_id` and latest-state selection rules for `evidence_link_declared`.
3. Split ordering rules for single-stream vs cross-stream walkers.
4. State v7 canonical schema/table fields explicitly.
5. Normalize signal-source enum across claim, recall, and provenance, or define an adapter.
6. Make the `score_candidate` retirement hook precise enough not to fail on harmless transitional imports.
7. Define how new event types enter the mapping table.

Net: v1.1 successfully incorporated the cross-substrate review. The remaining concerns are mostly about making the implementation unambiguous. The theory is now being served rather than distorted: memory is not reality, observations are not reality, decisions are not claims, and evidence links are lineage rather than mutation.
```