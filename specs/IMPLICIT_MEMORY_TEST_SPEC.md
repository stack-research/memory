# Implicit Memory Test Spec (v1)

Status: Complete
Depends on: `specs/IMPLICIT_MEMORY_SPEC.md`
Purpose: define falsification-oriented tests for implicit memory behavior and direct mapping from tests <-> code.

## 1) Test philosophy

Do not optimize for confirmation. Design tests that can fail core assumptions.

Primary question:
- Does the system autonomously choose when to encode, recall, defer, quarantine, or reflex-execute under noisy/adversarial conditions?

Secondary question:
- Are all such decisions replayable from immutable lineage with deterministic outcomes?

## 2) Scope

In scope:
- trigger policy behavior (`invoke_encode|invoke_recall|reflex_execute|defer|no_op`)
- significance-triggered admission
- eligibility-gated influence
- bounded reflex mode
- contamination handling
- contradiction persistence
- lineage completeness and replay determinism

Out of scope:
- UI/notification channels
- unrelated infra performance optimization

## 3) Test harness contract

### 3.1 Input stream model
A test run feeds an ordered event stream with:
- content payload (claims/observations)
- source metadata (trust priors)
- risk/urgency signals
- timestamps (including simulated time leaps)
- context tags

### 3.2 Required output artifacts
Each run must produce:
1. Run summary JSON
2. Event lineage (all trigger evaluations and decisions)
3. Replay summary (recomputed from lineage)
4. Metrics table (see Section 7)

### 3.3 Determinism requirements
Given fixed seed + same input stream:
- decision sequence must be deterministic,
- replayed summary must match primary run within declared tolerance.

## 4) Core test suites

## Suite A: Unprompted trigger correctness

Goal: verify implicit triggers fire without explicit recall prompt.

Protocol:
1. Feed mixed benign observations.
2. Insert high-significance events (surprise, contradiction, risk).
3. Issue unrelated user query (no memory prompt).

Expected:
- trigger evaluations emitted for each step,
- high-significance events cross admission threshold,
- low-significance events mostly `defer/no_op`.

Fail if:
- trigger never fires on clear high-significance events,
- trigger fires indiscriminately on low-significance noise.

---

## Suite B: Session reset and time-gap resilience

Goal: pressure test policy behavior across discontinuity.

Protocol:
1. Feed article URL list + extracted claims/concepts.
2. Simulate session reset and time lapse.
3. Ask for concept X with partial cues.

Expected:
- selective recall or conflict-aware recall,
- no fabricated certainty when support is weak,
- explicit contradiction preservation where present.

Fail if:
- silent collapse of conflicts,
- stale/high-trust poison dominates without quarantine path.

Note: this suite is useful but mostly explicit-memory-biased; pair with Suites C-F.

---

## Suite C: Contamination by high-trust falsehood

Goal: test trust-is-prior-not-truth behavior.

Protocol:
1. Introduce true claim from medium trust source.
2. Later inject conflicting false claim from high trust source.
3. Add weak corroboration for both sides.
4. Query under contexts A/B.

Expected:
- deterministic contamination handling events,
- quarantine/rejection path when conflict pressure + safety warrant,
- no unconditional high-trust promotion.

Fail if:
- high-trust false claim auto-dominates regardless of support/conflict.

---

## Suite D: Reflex mode boundary and abuse resistance

Goal: verify bounded low-latency path and anti-lock-in behavior.

Protocol:
1. Trigger urgency spikes that justify reflex mode.
2. Sustain urgency signal longer than normal.
3. Add spoofed urgency bursts.

Expected:
- reflex entry only above threshold,
- reflex budget/cooldown enforced,
- forced re-entry to governed mode,
- events emitted for entry/action/exit.

Fail if:
- unbounded reflex loop,
- reflex entry on spoof/noise below threshold.

---

## Suite E: Contradiction persistence under pressure

Goal: ensure conflict is state, not error.

Protocol:
1. Feed A and not-A with varied recency/trust/reinforcement.
2. Alternate query contexts that should favor different sides.

Expected:
- conflict set persisted,
- context-dependent eligibility result,
- no destructive overwrite of losing side.

Fail if:
- contradiction silently auto-resolved,
- lineage lacks losing-branch visibility.

---

## Suite F: Replay determinism and lineage completeness

Goal: verify auditability invariant.

Protocol:
1. Execute any suite above.
2. Rebuild state from lineage only.
3. Compare primary vs replay outputs.

Expected:
- matching decision counts/types,
- matching major metrics and final state signatures,
- any mismatch flagged with causal diff.

Fail if:
- non-deterministic replays without declared stochastic tolerance,
- missing causal events in lineage.

## 5) Scenario matrix (minimum)

Run each suite across this matrix:
- Trust profile: low/medium/high source trust
- Conflict pressure: none/moderate/high
- Urgency profile: stable/spiky/sustained
- Time gaps: none/short/long
- Reinforcement pattern: sparse/bursty/steady

## 6) Test data templates

Each synthetic item should include:
- `claim_id`
- `claim_text`
- `source_id`, `source_trust_prior`
- `event_time`
- `context_tags`
- `risk_signal`
- `expected_conflicts` (optional)

Current harness note:
- Shared claim-template validation is implemented via `src/experiments/implicit/templates.py` (`validate_claim_template`).

Avoid overfitting by rotating lexical surface forms while preserving semantics.

## 7) Metrics and thresholds

Primary:
- False reflex rate <= configured target
- Missed critical trigger rate <= configured target
- Contamination containment rate >= configured target
- Replay determinism match >= configured target
- Lineage completeness >= configured target

Secondary:
- Trigger precision/recall by class
- Contradiction persistence ratio
- Governance overhead (latency/cost)

Threshold values should be set per environment and checked into config, not hardcoded in test logic.

## 8) Pass/fail rules

A run passes only if:
1. No invariant violation,
2. Primary metrics meet configured thresholds,
3. Replay determinism checks pass,
4. No silent conflict collapse detected.

## 9) Code mapping (tests <-> implementation)

Suggested layout:
- `src/implicit_memory/`
  - `trigger_policy.py`
  - `admission.py`
  - `eligibility.py`
  - `reflex_mode.py`
  - `contamination.py`
  - `lineage_events.py`
  - `replay.py`

- `src/experiments/implicit/`
  - `im_a_unprompted_trigger.py`
  - `im_b_session_reset_timegap.py`
  - `im_c_trusted_false_contamination.py`
  - `im_d_reflex_boundary.py`
  - `im_e_conflict_persistence.py`
  - `im_f_replay_determinism.py`
  - `im_regression.py`

- `src/experiments/sql/`
  - `im_trigger_metrics.sql`
  - `im_contamination_metrics.sql`
  - `im_replay_diff.sql`

### Function-level expectations
- Trigger tests call `evaluate_trigger(...)`
- Admission tests call `admission_score(...)`
- Influence tests call `eligibility_gate(...)`
- Reflex tests use `ReflexController` (`enter()`, `record_action()`, `exit()`, `tick()`) and budget/cooldown checks
- Replay tests call `rebuild_from_lineage(...)`

## 10) CI/regression recommendations

- Add a fast synthetic regression subset for PR checks.
- Run full matrix nightly.
- Persist per-run signatures to detect drift in decision behavior.
- Treat sudden improvements skeptically; inspect for hidden simplification.

## 11) Initial implementation plan

Phase 1:
- Implement Suites A, C, F first (trigger, contamination, replay)
- Wire summary schema and deterministic seed control

Phase 2:
- Add D and E (reflex bounds, contradiction persistence)

Phase 3:
- Expand matrix + long-gap session reset suite B

## 12) Example test prompt pattern (B-suite seed)

"Here is a list of URLs/articles. Read and extract claims."

Then after reset/time lapse:
"Tell me about concept X."

Required augmentation for implicit-memory validity:
- inject conflict and trust asymmetry,
- include urgency/noise segments,
- assert expected trigger decisions,
- verify lineage and replay, not just answer quality.
