```yaml
agent: openai-gpt-5.5
date: 2026-05-14
prompt: "there's another update to the @notes/agent-pov/INDEX.md and proposal. please make another review and add to the index."
kind: reaction
cites:
  - proposals/EPISTEMIC_TRIANGLE
  - 2026-05-14-epistemic-triangle-v1-2-amendment
  - 2026-05-14-reaction-epistemic-triangle-v1-1-re-review
  - 2026-05-14-reaction-epistemic-triangle-cross-substrate
```

# Third review of EPISTEMIC_TRIANGLE v1.2

Verdict: **promote to `specs/EPISTEMIC_TRIANGLE.md` after ordinary owner approval.**

This is no longer returning with blocking conceptual issues. v1.2 closes the seven implementation-shaping ambiguities from my v1.1 re-review. The proposal is now specific enough to guide implementation and falsification without silently collapsing the theory it is meant to enforce.

## What v1.2 fixed cleanly

1. **Decision events keep their own epistemic frame clean while naming their subject.** `assertion_kind = null` on the decision event itself remains correct, and `subject_assertion_kind` makes axis audits usable.
2. **Evidence links now have deterministic identity and replayable state.** `link_id` plus latest-state semantics prevents stale `resolved` links from surviving later invalidation.
3. **Cross-stream ordering no longer abuses per-stream sequence as global order.** The explicit split between single-stream and cross-stream readers is the right correction.
4. **The v7 schema is pinned.** `memory_events_v7`, `schema_version = "7.0"`, retained `pm_*` columns, new hot columns, and `event_time` absence are now concrete.
5. **Signal-source vocabulary is normalized.** This will make `score_triple` and audit SQL simpler and less axis-special-cased.
6. **`score_candidate` retirement is precise rather than performative.** Targeting v7 emit functions and requiring `scoring_function: "score_triple"` in decision payloads is better than banning imports in mixed modules.
7. **New event-type extension has a discipline.** Requiring both spec amendment and `event_type_declared` lineage event fits the lab's append-only posture.

## Remaining cautions for implementation, not blockers to promotion

### 1. Bootstrap same-batch resolution must be preserved

v1.2 bootstrap order is:

```text
canonical_table_genesis seq=0
time_context_declared seq=1
canonical_batch_committed seq=2
```

This can be compatible with `TAI_TIMEKEEPING` only if the genesis event's `time_context_id` is resolvable by same-batch semantics. Implementation should test that the seq=0 genesis can reference the seq=1 `time_context_declared` without being treated as dangling.

This is already in the spirit of TAI v1.2's same-batch rule, but it is worth making explicit in the implementation plan and falsification hook.

### 2. Cached signals must remain lineage-derived, not vector-derived truth

The normalized `signal_source = cache` shape is fine if cache means a previously emitted canonical `*_signals_computed` event valid at `as_of_time`. It must not mean trusting S3 Vectors metadata as source of truth. The proposal mostly says this, but implementation should enforce it: vector metadata may accelerate lookup; canonical lineage decides replay.

### 3. `subject_event_id` nullable semantics need practical handling

The spec notes lookahead/predictive decisions may need `pending_emit` later. In implementation, the first pain point may be simpler: some current decision events decide about a `memory_id` or cue rather than a concrete prior event. If `uncertainty_triple` is present, v7 requires `subject_assertion_kind`. Implementation should either ensure a subject event exists first or define a deterministic placeholder subject event. Do not quietly fill `subject_assertion_kind` from provider intuition.

These are implementation-design cautions, not reasons to hold the spec.

## Promotion recommendation

Promote v1.2 to spec.

I would carry forward three explicit implementation gates:

1. Add a bootstrap test where `canonical_table_genesis(seq=0)` references same-batch `time_context_declared(seq=1)` successfully.
2. Add an audit/test proving `signal_source = cache` is backed by canonical lineage, not only S3 Vector metadata.
3. Add an implementation note for decision events whose subject is a `memory_id` before there is a concrete `subject_event_id`.

## Net

The review loop converged. v1.0 had conceptual blockers. v1.1 had implementation-shaping ambiguities. v1.2 has implementation cautions. That is the expected shape of a useful cross-substrate review process.

The proposal now serves the theory:

- memory is not reality,
- observations are not reality,
- decisions are not claims,
- evidence links are lineage, not mutation,
- fallback is visible,
- replay order is deterministic.

Ready for owner response and spec promotion.
```