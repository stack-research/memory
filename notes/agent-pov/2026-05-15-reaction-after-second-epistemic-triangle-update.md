```yaml
agent: openai-gpt-5-codex
date: 2026-05-15
prompt: "the development agent made updates and complimented your review. thank you. please review the updated code and leave another reaction when you are ready."
kind: reaction
cites:
  - specs/EPISTEMIC_TRIANGLE.md
  - 2026-05-15-reaction-to-epistemic-triangle-review-response
  - 2026-05-15-epistemic-triangle-implementation-code-review-response
```

# Reaction after the second implementation update

I reviewed the updated code against the prior reaction and reran:

```bash
PYTHONPATH=. uv run --project stacks python -m src.experiments.implicit.im_u_epistemic_triangle
```

Result: `PASS`, 32/32 hooks. The new hooks 25-29 are a meaningful response, not just a green paint pass.

## What is now materially better

- Athena's `reality_observation` check is now null-safe for nullable `assertion_kind` rows, so valid `lineage_meta`, `decision_event`, and `policy_event` rows are no longer silently pushed out by SQL three-valued logic.
- The Athena path now validates `evidence_link_declared` payload shape, link type, resolution state, and state-specific reasons, and maps malformed link payloads to `invalid_link_id`.
- `RecallEngine.retrieve()` no longer calls `score_candidate()` directly. It uses `triple.combined()` and emits `scoring_function: "score_triple"` on the recall/reject payloads.
- `ImplicitControllerLoop._admit_and_gate()` now actually supplies `claim_signals`, `recall_signals`, and `provenance_signals` to the gate. Claim/recall fallback is loud; provenance is packaged as computed.
- Preflight's printed projection now includes the v7 hot columns instead of showing a stale partial insert shape.

That closes most of the previous review's surface area. The feedback loop did the thing.

## Remaining concerns

### 1. Athena still does not verify deterministic `link_id`

Spec §4.2 requires:

```text
link_id = sha256(json_canonical({claim_event_id, evidence_event_id, link_type}))
```

The Python validator enforces this through `compute_link_id()`. The Athena predicate now checks that `link_id` is present and that link type/state/reason values are valid, but it does not recompute the hash or compare it to `payload.link_id`.

So a raw ingress row with a well-shaped but wrong `link_id` can still pass the Athena canonical insert path. Hook 26 says "corrupt evidence link," but its required substrings only prove shape/state validation, not deterministic identity validation. This is narrower than the previous gap, but it is still the load-bearing part of §4.2.

### 2. Explicit recall still uses `signal is None` mode

`src/explicit_memory/recall.py` now removed `score_candidate`, which is good. But its `score_triple(...)` call still does not pass `claim_signals`, `recall_signals`, or `provenance_signals`.

Spec §11 says `none` is only allowed on `schema_version < 7.0` paths. Explicit recall is a v7 emit path. The implicit loop now handles this by constructing fallback claim/recall signals and computed provenance signals; recall should probably use the same pattern, or document and test why explicit recall is exempt.

This also means the explicit recall payloads still do not carry `axis_fallback_used`, `axis_fallback_reasons`, or `policy_fallback_multiplier`, even though they carry an uncertainty triple and `scoring_function`.

## Net

This update deserves credit: the second pass closed four of my five prior findings and sharpened the suite from 27 to 32 hooks. The remaining work is narrower and more concrete:

- Athena should validate the deterministic `link_id` hash, not only link payload shape.
- Explicit recall should stop using the v7 `None` signal path, or the spec should explicitly exempt it.

I would call the implementation "close, with two remaining spec-compliance gaps," not yet final. The review loop is converging in exactly the way this folder was meant to preserve.
