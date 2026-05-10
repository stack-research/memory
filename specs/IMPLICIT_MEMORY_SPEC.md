# Implicit Memory Spec (v1)

Status: Complete
Audience: future agent loops, experiment authors, policy implementers

## Implementation gap checklist (current)

This checklist tracks remaining work to reach full runtime alignment with this spec.

- [x] Single integrated implicit runtime path:
  - unify `trigger -> admission -> eligibility gate -> influence/quarantine -> outcome` for observation-driven flow.
- [x] Reflex mode in main runtime loop:
  - handle `reflex_execute` with enter/action/exit events, bounded action budget, cooldown, and forced re-entry to governed mode.
- [x] Admission + influence gating parity:
  - apply significance-triggered admission and eligibility-gated influence consistently for both scheduled-cue and observation paths.
- [x] Deterministic rejection/quarantine reason taxonomy:
  - centralize and enforce machine-readable reasons across all implicit paths.
- [x] Runtime attack-surface controls:
  - implement and validate spoofed urgency detection, spoofed sensory-confidence detection, event-flood handling, and reflex lock-in prevention in the controller loop.
- [x] Policy mutation in operational path:
  - emit and apply `policy_threshold_updated` / `policy_procedure_superseded` as first-class runtime behavior (not experiment-only).
- [x] Continuous evaluation metrics wiring:
  - report primary/secondary metrics from Section 14 in ongoing loop execution.

## 1) Purpose
Define how the lab models **implicit memory**: automatic, state-conditioned invocation of encode/recall/action procedures without explicit user prompting.

This spec exists to move from:
- the encode/store/retrieve loop

to:
- governed memory control (admission, influence gating, decay, reflex bounds, contamination defense, replayability)

## 2) Theory anchor
This repo distinguishes:
- **Reality**: observer-independent world state.
- **Evidence**: externally anchored support.
- **Claim**: proposition asserted by a source.
- **Memory**: stored trace and its metadata.
- **Belief**: current internal acceptance level.

Implicit memory operates in the cognitive plane (mutable behavior) but must remain accountable via lineage (immutable events).

## 3) Scope
### In scope
- trigger policies for automatic invocation
- reflex-mode entry/exit and budgets
- procedural reinforcement/decay
- contamination detection and quarantine hooks
- deterministic lineage emission for all implicit decisions

### Out of scope
- explicit episodic schema details (defined by canonical event envelope)
- infra deployment mechanics
- UI/notification channel implementation

## 4) Non-negotiable invariants
1. Memory behavior can mutate; lineage history is append-only.
2. No implicit decision is silent: every trigger evaluation emits an event.
3. Contradictions are preserved, not auto-resolved.
4. S3 Tables canonical lineage remains source of truth.
5. Reflex mode is bounded and cannot run indefinitely.

## 5) Operating doctrine
Act on risk, do not wait on permission; always emit lineage; allow intervention, do not require it.

Footnote: the "safest known strategy" can be incomplete or poisoned. Sensory-grounded actors can detect reality shifts faster than distant observers.

## 6) Implicit memory model
Implicit memory is modeled as a policy function over current state:

`state -> trigger evaluation -> procedure selection -> execution -> outcome update`

Where state includes:
- current task/context
- risk/urgency signals
- recent outcomes
- trust/safety posture
- conflict pressure
- resource constraints (time/compute/power)

## 7) Trigger policy
### 7.1 Trigger classes
A trigger evaluation may be initiated by:
- prediction error / surprise
- goal impact delta
- safety anomaly
- repetition/reinforcement signal
- contradiction pressure
- explicit remember/recall directive
- scheduled/timed cue (if present)
- sensor disagreement

### 7.2 Trigger output contract
`invoke_encode | invoke_recall | reflex_execute | defer | no_op`

All outputs require lineage event emission, including `defer` and `no_op`.

### 7.3 Admission principle
Significance-triggered write; policy-gated influence.

Do not store every observation. Store only when significance crosses admission threshold.

## 8) Influence gating
After admission, influence eligibility is computed before any state mutation:
- relevance
- trust
- recency
- reinforcement
- consistency
- safety

Eligibility decides:
- promote to active influence
- keep as inactive trace
- quarantine/reject with deterministic reason

## 9) Reflex mode (implicit fast path)
### 9.1 Why it exists
When reaction-time dominates deliberation quality, governed memory may intentionally lose to simpler procedural execution.

### 9.2 Entry condition (example)
`urgency * risk * sensory_confidence > reflex_threshold`

### 9.3 Guardrails
- max consecutive reflex actions
- reflex time budget
- cooldown period before re-entry
- mandatory re-checkpoint to governed mode
- emit all reflex actions/events for post-hoc audit

### 9.4 Failure/attack considerations
- spoofed urgency
- spoofed sensory confidence
- reflex lock-in
- event flooding to hide causality

## 10) Reinforcement and decay
Implicit procedures are not static:
- reinforce procedures after successful outcomes
- decay stale/unused procedures
- apply trust decay under prolonged unresolved high-urgency states
- supersede older procedures via append-only policy-update events

## 11) Contamination model
Contamination = poisoned, stale, or adversarial signals steering trigger/procedure selection.

Controls:
- treat trust as prior, not truth
- emit `split_reality_detected` on sensor disagreement
- quarantine suspicious trigger sources
- deterministic reason taxonomy for quarantine/rejection
- preserve conflicting traces for later replay and analysis

## 12) Lineage requirements for implicit decisions
Minimum event families:
- `implicit_trigger_evaluated`
- `implicit_trigger_fired`
- `implicit_trigger_deferred`
- `implicit_no_op`
- `implicit_admitted`
- `implicit_rejected`
- `reflex_mode_entered`
- `reflex_action_executed`
- `reflex_mode_exited`
- `procedure_reinforced`
- `procedure_decayed`
- `contamination_suspected`
- `policy_threshold_updated`
- `policy_procedure_superseded`

All events must include required envelope fields (see `AGENTS.md`):
- `event_id`, `event_type`, `agent_id`, `stream_id`, `memory_id`
- `event_time`, `schema_version`, `payload`
- `actor_class`, `source_class`
- `parent_event_id` (nullable)

## 13) Reference pseudocode
```python
def implicit_loop(observation, ctx):
    trig = evaluate_trigger(observation, ctx)
    emit("implicit_trigger_evaluated", trig)

    if trig.action in {"defer", "no_op"}:
        emit(f"implicit_{trig.action}", trig)
        return

    if trig.action == "reflex_execute":
        enter_reflex_if_allowed(ctx)
        emit("reflex_mode_entered", ctx)
        outcome = run_reflex_procedure(observation, ctx)
        emit("reflex_action_executed", outcome)
        exit_reflex(ctx)
        emit("reflex_mode_exited", ctx)
        update_procedure_strength(outcome)
        return

    # invoke_encode / invoke_recall
    candidate = build_candidate_trace(observation, ctx)
    adm = admission_score(candidate, ctx)
    if adm < ADMISSION_THRESHOLD:
        emit("implicit_rejected", {"reason": "low_significance", "score": adm})
        return

    emit("implicit_admitted", {"score": adm})

    gate = eligibility_gate(candidate, ctx)
    if gate.allow_influence:
        mutate_cognitive_state(candidate, gate)
    else:
        quarantine_or_hold(candidate, gate.reason)
    emit("implicit_trigger_fired", {"gate": gate.to_dict()})
```

## 14) Evaluation criteria
Primary metrics:
- false reflex rate
- missed critical trigger rate
- time-to-action under risk
- replay determinism
- contamination containment rate

Secondary metrics:
- trigger precision/recall per class
- contradiction persistence quality
- lineage completeness (% decisions with full causal chain)
- governance overhead (latency/cost)

## 15) Experiment guidance (theory stress first)
Prefer falsification-oriented tests:
- adversarial urgency spoofing
- trust inversion scenarios
- delayed evidence reversal
- prolonged high-urgency degradation
- reflex budget exhaustion
- contamination via high-trust false inputs

Success is not “always right.” Success is:
- bounded failure,
- auditable causality,
- deterministic replay,
- safe recovery.

## 16) Integration points
- Existing experiments (E1-E12) cover explicit-memory behaviors and replay/rebuild patterns.
- This spec adds the implicit/procedural layer to be implemented and tested in future loops.

## 17) Open questions
- Best default reflex thresholds per domain
- Optimal decay function per procedure family
- How to tune intervention hooks without reintroducing human-gate bottlenecks
- How to prevent overfitting trigger policy to known attacks
