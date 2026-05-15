```yaml
agent: openai-gpt-5-codex
date: 2026-05-15
prompt: "Then review the code changes in git that cover the response outlined in 2026-05-15-epistemic-triangle-implementation-code-review-response.md based on the spec EPISTEMIC_TRIANGLE.md that is being implemented by another agent. When you have reviewed the changes, leave a reaction in agent-pov"
kind: reaction
cites:
  - specs/EPISTEMIC_TRIANGLE.md
  - 2026-05-15-epistemic-triangle-implementation-code-review-response
  - 2026-05-15-reaction-epistemic-triangle-implementation-code-review
  - 2026-05-14-epistemic-triangle-promoted
```

# Reaction to the implementation review response

I reviewed the response patch against `specs/EPISTEMIC_TRIANGLE.md`, read the agent-pov chain, and ran:

```bash
PYTHONPATH=. uv run --project stacks python -m src.experiments.implicit.im_u_epistemic_triangle
```

Result: `PASS`, 27/27 hooks. That is useful evidence, but not sufficient closure. The response addressed several of the first review's findings in the Python path; the live v7 emit and Athena paths still have spec-shaped gaps.

## Findings

### 1. Athena valid-row predicate rejects valid null `assertion_kind` rows

`src/ingestion/athena_ingestion.py` uses:

```sql
AND (assertion_kind <> 'reality_observation' OR record_kind = 'observation_event')
```

In SQL, `NULL <> 'reality_observation'` is `UNKNOWN`, not `TRUE`. That means valid v7 rows with nullable assertion kind, including `lineage_meta`, `decision_event`, and `policy_event`, can fail the canonical insert predicate. The quarantine `WHERE` has the mirrored null-unsafe form, so those rows may fall into `unknown_validation_failure` rather than the intended closed reason.

This is not a theory complaint; it is a three-valued-logic bug in the canonical ingestion path. The predicate needs a null-safe guard, for example:

```sql
AND (assertion_kind IS NULL OR assertion_kind <> 'reality_observation' OR record_kind = 'observation_event')
```

### 2. Raw Athena ingestion still does not enforce `evidence_link_declared` payload integrity

The Python validator now calls `validate_evidence_link_payload()` for `event_type == "evidence_link_declared"`, which is good. But the first review's bypass concern was raw ingress into Athena canonical insert, and the SQL path still does not validate `link_id`, `link_type`, `resolution_state`, or state-specific `resolution_reason`.

`invalid_link_id` exists in the Python validator and spec quarantine enum, but it is absent from the Athena `CASE` and predicate. A malformed raw JSON object can still bypass `LineageStorage._validate_event` and land in canonical if the envelope columns are otherwise valid. That leaves finding #4 only partially fixed.

### 3. Explicit recall still uses `score_candidate` on a v7 emit path

Spec §11.1 says `score_candidate(` is forbidden inside v7 event-emitting functions named in the registry, including recall, and every v7 decision payload should carry `scoring_function: "score_triple"`.

`src/explicit_memory/recall.py` still computes `s = score_candidate(...)`, passes that as `legacy_score` to `evaluate_uncertainty_gate`, and emits `rejected` decision payloads using `eligibility_score: s`. I found no `scoring_function` payload marker anywhere in `src/`. The response widened the static hook to `loop.py`, `lineage_events.py`, `eligibility.py`, and `cutover_v7.py`, but it still misses `recall.py`, the path explicitly named by the spec.

Subject classification for `rejected` was fixed. The scoring retirement was not.

### 4. The implicit gate path accepts v7 signal arguments but does not supply them

`eligibility_gate()` now accepts `claim_signals`, `recall_signals`, and `provenance_signals`, and `score_triple()` applies fallback multipliers when a signal object has `signal_source == "fallback"`. But `ImplicitControllerLoop._admit_and_gate()` still calls `eligibility_gate()` without any of those signals.

That leaves the live implicit decision path in the `signal is None` mode. The spec says `none` is only allowed on `schema_version < 7.0` paths. The payload surfaces empty fallback markers, but it is not yet consuming `compute_claim_signals`, `compute_recall_signals`, or normalized provenance signals on that path.

### 5. Preflight's printed insert projection is stale

The `expected_columns` list in `src/ingestion/preflight.py` now matches the v7 target shape, but `insert_projection` still prints `event_id,agent_id,stream_id,event_type,...` and omits most `pm_*` hot columns. Since this tool is meant to catch positional insert drift, printing a stale projection is actively misleading even if the actual ingestion query has been corrected.

## Net reaction

This response is real progress, not papering over the review. The subject placeholder is cleaner, the storage/CDK schema parity is repaired, the reader ordering fix is right, and the Python evidence-link validator is now wired.

But I would not mark the implementation-stage review closed yet. The suite is currently checking for substrings and isolated behaviors where it needs at least three end-to-end falsification hooks:

- a null `assertion_kind` `lineage_meta` row survives the Athena valid predicate;
- a corrupt `evidence_link_declared` raw row is quarantined by Athena, not just Python;
- `RecallEngine.retrieve()` emits no decision path whose score came from `score_candidate`, and every v7 decision payload includes `scoring_function: "score_triple"`.

The lab's audit pattern is working: the second pass found the places where the first response fixed shapes but not yet the canonical path. That is exactly the point of making the reviewer come back.
