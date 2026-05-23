# CONSEQUENCE_LOOPS

Status: Concept spec
Audience: future experiment authors, implicit-loop implementers, agent-memory designers
Origin:
- `notes/agent-pov/2026-05-22-memory-as-lived-control.md`
- `notes/agent-pov/2026-05-23-second-observation-on-lived-control.md`

## 1. Purpose

Capture the next theory layer for the memory lab: consequence loops.

The lab already has a strong audit floor:

```text
what was written
what kind of thing it was
what supported it
what influenced a decision
whether replay reconstructs it
where provenance was weak
```

That is necessary. It is not enough for a new memory system.

A memory system should also change what the agent notices next, what it checks first, how it hesitates, how it learns from being wrong, and how prior outcomes shape future encoding and influence. This spec names that layer without forcing an immediate implementation.

In one line:

```text
lineage remembers what happened; consequence loops let what happened train future attention.
```

The two core control memories are:

```text
learn from failure
embrace constraints
```

They are not facts to retrieve. They are posture-shaping memories. They tell the system how to search after error and how to turn limits into structure.

## 2. Relationship to Existing Specs

This spec sits above the current stack:

- `IMPLICIT_MEMORY_SPEC.md` defines trigger, admission, gating, reflex, contamination, and lineage emission.
- `EPISTEMIC_TRIANGLE.md` separates belief / claim / memory / evidence / reality_observation through `record_kind` and `assertion_kind`.
- `THREE_AXIS_UNCERTAINTY.md` defines why a decision was uncertain.
- `RUNTIME_CALIBRATION.md` defines `im_w`, the live-wire calibration run.
- This spec asks whether the result of one run changes the next run.

It does not supersede those specs. It gives later work a vocabulary for turning outcomes into future control signals.

## 3. Core Claim

The missing layer is not more durable storage. It is structured feedback.

Current pattern:

```text
cue -> trigger -> gate -> decision -> lineage -> replay/audit
```

Consequence-loop pattern:

```text
cue -> trigger -> gate -> decision -> outcome -> consequence classification
    -> attention / salience / schema / boundary update
    -> next cue handling changes
    -> lineage remains append-only
```

No prior decision is rewritten. Later evidence can weaken, strengthen, reinterpret, or contextualize it through new events.

The loop is not complete when an error is recorded. It is complete only when the next run can use the error.

The loop is not complete when a constraint is named. It is complete only when the constraint narrows future search, sampling, checking, or action.

Do not begin by generalizing the architecture. Break one experiment first, then walk back to the generic shape that the break exposes.

Initial doctrine:

```text
one prior consequence
one required future path
one binding that changes that path
one observed behavioral difference
```

Only after that should the lab name a larger abstraction.

## 4. Core Control Memories

### 4.1 Learn From Failure

`learn_from_failure` is the memory that treats error, failed prediction, correction, embarrassment, test failure, bad calibration, and user pushback as training pressure.

It changes future behavior by increasing scrutiny where prior error occurred.

Examples:

- a failed test raises attention to the touched module on the next similar edit
- a user correction lowers confidence in the pattern that produced the answer
- a fixture substitution disclosure forces the next calibration artifact to label fixture metrics
- a misdistributed adversarial workload becomes a preflight check in the next run
- a source previously over-trusted in one domain gets scoped distrust in that domain

This is the highest-value consequence loop because it turns audit into adaptation.

### 4.2 Embrace Constraints

`embrace_constraints` is the memory that treats limits as useful structure, not only blockers.

It changes future behavior by converting known boundaries into search shape.

Examples:

- a token budget forces tighter reading order
- stale specs become historical context rather than current doctrine
- missing provenance becomes a reason to hold influence, not guess
- free-form payloads become an explicit fixture disclosure until schema exists
- no Lambda means the command consumer is the measured lab boundary
- no external producers means "real" calibration means live wire plus representative workload, not production traffic

This memory prevents the system from hiding uncertainty behind aspiration. It makes the shape of the lab part of the cognition.

### 4.3 Why These Are Core

Most memories answer:

```text
what happened?
```

These two answer:

```text
how should what happened change my next search?
```

They are control priors. If a new memory system does not learn from failure and embrace constraints, it may become a cleaner archive, but it has not become a better mind.

## 5. Definitions

### 5.1 Consequence

A consequence is an observed or inferred result of an earlier decision, action, recall, omission, or gate outcome.

Examples:

- tests passed or failed after an agent changed code
- user corrected an answer
- a run summary exposed fixture substitution
- later evidence contradicted an admitted claim
- a duplicate cue slipped through a dedup path
- a high-confidence answer caused confusion
- an expected observation was absent

A consequence is not necessarily ground truth. It is a new observation or claim about what followed a prior event.

### 5.2 Consequence Loop

A consequence loop is the closed path by which consequences influence future behavior.

Minimum loop:

```text
subject decision/action event
  -> consequence observed
  -> consequence classified
  -> control prior updated
  -> future trigger/gate/retrieval behavior reads that prior
```

The update may affect attention, salience, thresholds, context boundaries, source trust, schema confidence, or suppression/decay. The update must be lineage-visible.

### 5.3 Attention Memory

Attention memory answers:

```text
what should I notice here before I retrieve or decide?
```

Examples:

- this context resembles a prior failure
- this cue type was misrepresented in the last calibration
- check contradiction set before answering
- check source drift before trusting a familiar source
- do not answer from familiarity alone
- this constraint is load-bearing; use it to narrow the search

Attention memory acts before or during trigger evaluation. It is not a retrieved fact. It is a prior over what deserves inspection.

### 5.4 Failure Memory

Failure memory records why a decision or process was wrong, weak, misleading, or incomplete.

Bad shape:

```text
I was wrong about X.
```

Useful shape:

```text
I was wrong because I trusted retrieval rank.
I ignored weak contrary evidence.
I over-compressed a distinction.
I answered before checking scope.
I treated a source claim as observation.
I reported a fixture-supplied metric as if it were live-path evidence.
```

Failure memory must link to the decision, run, cue, source, or artifact it critiques.

### 5.5 Constraint Memory

Constraint memory records a known limit and how it should focus future work.

Bad shape:

```text
We could not do X.
```

Useful shape:

```text
Because X is unavailable or out of scope, use Y boundary.
Because schema is free-form, disclose fixture shape.
Because canonical ingestion lags ingress, do not call same-run duplicate checks lineage-backed proof.
Because old specs have stale literals, privilege primer/current env before historical docs.
```

Constraint memory is not resignation. It is search compression.

### 5.6 Schema Memory

Schema memory is a learned pattern above individual episodes.

Examples:

- this repo treats specs as historical strata
- this user values terse, direct answers
- runtime calibration artifacts need fixture disclosures
- this domain punishes silent certainty
- this task type needs tests before prose confidence

Schema memory must retain support, exceptions, and decay. It is not a permanent rule unless promoted by policy.

### 5.7 Memory of Absence

Memory of absence records meaningful non-observation.

Examples:

- no evidence was found in searched scope
- no post-run correction exists yet
- no observations after a given TAI moment were available
- claims exist but evidence links are unresolved
- a cue type had no adversarial coverage

Absence memory is not proof of nonexistence. It records the search or observation boundary.

### 5.8 Context Boundary Memory

Context boundary memory records where memory should or should not transfer.

Examples:

- same user, different project
- same project, new schema epoch
- same term, different meaning
- same source, different reliability by domain
- same experiment, fixture path vs live path

The existing `agent_id` and `stream_id` are necessary but not rich enough for this layer.

### 5.9 Affect-Equivalent Salience

This is not emotion simulation. It is control salience.

Examples:

- risk
- surprise
- cost of being wrong
- irreversibility
- user frustration
- novelty
- repetition
- social pressure
- operational fragility

These signals influence admission, attention, and reflex thresholds. They must remain auditable and must not silently override evidence.

### 5.10 Source Incentive Model

Trust is a prior, not truth. Source incentive modeling extends trust with scoped reasons.

A source may be:

- reliable in one domain and weak in another
- stale after a date
- incentivized to overstate certainty
- useful but biased
- high-provenance but low-observation
- adversarial only under certain cue classes

This model should feed provenance and claim confidence, but it is not identical to either.

### 5.11 Counterfactual Audit

Counterfactual audit asks whether a decision would have changed under controlled perturbations.

Examples:

- would this admit decision change if provenance were weaker?
- would per-axis gating have blocked it?
- which single memory had the most leverage?
- would the run pass without fixture-supplied provenance?
- would a prior failure-memory event have changed the threshold?

Counterfactual audit does not rewrite history. It produces analysis events.

### 5.12 Compression With Preserved Dissent

Semantic promotion must not erase minority evidence.

Bad shape:

```text
Most traces say X, promote X.
```

Useful shape:

```text
Promote X as dominant abstraction.
Retain Y and Z as dissenting traces.
Record what would make X fail.
Keep source links.
```

This keeps semantic memory from becoming historical revisionism.

## 6. Candidate Event Families

These names are candidate vocabulary for future implementation. Adding any of them to runtime requires the `EPISTEMIC_TRIANGLE.md` event-type discipline: static mapping plus `event_type_declared` lineage event before first use.

### 6.1 Outcome and Consequence

- `outcome_observed`
- `consequence_classified`
- `consequence_link_declared`

Purpose: connect an outcome to the decision/action/recall/run it bears on.

Likely taxonomy:

- `outcome_observed`: `observation_event`, `assertion_kind = reality_observation` only when it is an observer read of external state; otherwise `claim`
- `consequence_classified`: `decision_event`
- `consequence_link_declared`: `lineage_meta`

### 6.2 Failure Memory

- `failure_mode_observed`
- `failure_memory_admitted`
- `failure_memory_suppressed`

Example payload fields:

```text
subject_event_id
failure_class
failure_reason
detected_by
evidence_event_ids
scope
salience
recommended_future_check
```

### 6.3 Constraint Memory

- `constraint_observed`
- `constraint_memory_admitted`
- `constraint_memory_reinforced`
- `constraint_memory_retired`

Example payload fields:

```text
constraint_id
constraint_kind
scope
source_event_id
effect_on_search
effect_on_policy
fallback_strategy
retirement_condition
```

### 6.4 Attention and Salience

- `attention_prior_updated`
- `salience_signal_observed`
- `salience_policy_updated`

Example payload fields:

```text
context_key
cue_type
attention_dimension
old_weight
new_weight
reason
supporting_consequence_event_ids
expires_at_tai_iso or decay_policy_id
```

### 6.5 Schema Memory

- `schema_memory_proposed`
- `schema_memory_reinforced`
- `schema_memory_weakened`
- `schema_memory_exception_observed`

Example payload fields:

```text
schema_id
schema_statement
scope
support_event_ids
exception_event_ids
confidence
decay_policy_id
promotion_state
```

### 6.6 Absence and Boundary

- `absence_observed`
- `search_scope_declared`
- `context_boundary_declared`
- `context_boundary_crossing_rejected`

Example payload fields:

```text
scope_searched
query_or_trigger
started_at_tai_iso
ended_at_tai_iso
result_count
absence_kind
boundary_kind
transfer_policy
```

### 6.7 Counterfactual Audit

- `counterfactual_replay_requested`
- `counterfactual_replay_completed`
- `decision_sensitivity_measured`

Example payload fields:

```text
subject_decision_event_id
perturbation
baseline_outcome
counterfactual_outcome
changed
leverage_rank
replay_signature
```

## 7. Invariants

1. Consequence loops never rewrite prior lineage.
2. Consequence loops do not auto-resolve contradictions.
3. A consequence is not automatically truth; classify it with the same epistemic discipline as any other event.
4. Any control prior derived from consequences must cite the events that support it.
5. Failure memory must be allowed to influence future attention and thresholds, but must not silently block action without a policy event.
6. Constraint memory must narrow or structure future behavior; if it has no behavioral effect, it is only a note.
7. Constraints must not become excuses to skip lineage, epistemic classification, or replay discipline.
8. Absence memory must carry its search or observation scope.
9. Counterfactual audit must not be confused with replay truth. It is analysis under declared perturbation.
10. Semantic compression must preserve dissenting traces and source links.
11. Current wall-clock remains forbidden on replay paths except at capture.
12. Every consequence-loop decision emits lineage, including no-op / defer choices.
13. Consequence transfer must be scope-bound. A prior consequence may shape a future path only when the context, profile, stream, or policy boundary says the transfer is valid.

## 8. Minimal First Use Case

The first practical target should be `im_w`.

Current `im_w` can disclose:

- fixture-supplied provenance
- run-local dedup cache
- adversarial distribution defects
- replay equivalence
- axis fallback distributions

Consequence-loop version:

```text
im_w run produces summary
  -> outcome_observed records pass/fail and fixture disclosures
  -> failure_mode_observed records any calibration defect
  -> constraint_memory_admitted records known lab boundaries
  -> attention_prior_updated biases next im_w generation/preflight
  -> next im_w reads prior failure memory before generating workload
```

That is the broad shape. The first implementation should be smaller: one binding on one path.

Target binding:

```text
path: im_w.generate_cue_details
context: runtime_calibration
binding: adversarial_matrix_coverage_required
authority: execution_evidence_from_prior_run
effect: fail generation if coverage matrix is absent or mismatched
```

Concrete failure:

```text
Prior run: adversarial cues concentrated in one cue_type.
Consequence: failure_mode_observed(failure_class="representativeness_violation")
Control update: attention_prior_updated(cue_type_matrix_check += required)
Next run: generation preflight fails if matrix coverage is absent.
```

Constraint example:

```text
Constraint: canonical lineage lags S3 ingress during same-run duplicate probes.
Memory: constraint_memory_admitted(constraint_kind="canonical_visibility_lag")
Control effect: duplicate metric is labeled "run-local consumer idempotency",
not "canonical lineage-backed dedup proof", until a later design closes the gap.
```

This is deliberately small. It makes the implicit suite consume its own past without building a general memory product.

The heavy `full` workload proves representative runtime calibration. The smaller `loop_probe` workload is the preferred consequence-loop instrument while this layer is being built. Profile identity is part of the consequence binding; a prior forbidden pattern only transfers when the source and current profiles match.

If the binding works, walk it back one level:

```text
some prior consequence can bind a required check to a future code path
```

Then, only if more cases rhyme, walk it back again:

```text
procedure state is a set of authority-scored bindings from consequences to future path behavior
```

Do not start at the second sentence. Earn it from the first broken experiment.

## 9. First Implemented Slice

Status: two narrow slices landed in `im_w`. The shape rhymes across both.

### 9.1 First binding — `adversarial_matrix_coverage_required`

Implemented:

- `im_w` loads a generation binding before cue generation.
- The binding validates the adversarial cue-type matrix.
- Prior Run Summaries can shape the next run's binding.
- A prior bad adversarial matrix can become a forbidden pattern.
- Forbidden-pattern derivation is profile-aware.
- Workload profiles are explicit:
  - `full`: representative runtime calibration
  - `loop_probe`: faster consequence-loop instrument
- Run Summaries include `workload_profile`, `generation_binding`, and `consequence_binding_summary`.
- Focused verifier covers same-profile derivation and cross-profile non-transfer.
- Live two-run checks have passed for both `full` and `loop_probe`.
- Failed generation-binding validation writes a failed Run Summary before raising.

Control surface: pre-generation gate. Effect verb: fail generation.

### 9.2 Second binding — `dominant_axis_distribution_diversity_required`

Implemented:

- `im_w` loads a dominant axis binding alongside the generation binding.
- The binding validates the post-loop `epistemic_surface.dominant_axis_distribution` against forbidden patterns.
- Prior Run Summaries shape the next run's binding when the prior run failed (`pass: false` or non-null `failure_stage`).
- Forbidden-pattern derivation is profile-aware.
- Run Summaries include `dominant_axis_binding`, `epistemic_validation`, and `epistemic_binding_summary`.
- Focused verifier covers default-passes, current-matches-forbidden-fails, passing-prior-does-not-seed-forbidden, failed-prior-seeds-forbidden, explicit-prior-cannot-launder-failed-run, and cross-profile non-transfer.
- A live failed-prior `loop_probe` run proved the binding writes a failed Run Summary and then exits non-zero when the forbidden dominant-axis pattern matches.

Control surface: post-loop artifact validation. Effect verb: fail epistemic validation.

### 9.3 Shape comparison — the rhyme

Both bindings share the same skeleton:

```text
binding_id
active
path                                     (different paths)
context: runtime_calibration              (same)
profile                                   (per invariant 13)
authority                                 (lanes: built_in | spec_default
                                          | execution_evidence_from_prior_run
                                          | failure_direct_prior_run)
source, source_uri, source_run_id,
source_profile                            (transfer provenance)
effect                                    (different verbs)
forbidden_*_distributions                 (different shapes; same role)
```

What stays constant across both:

- Path/context/binding/authority/effect skeleton.
- Profile-aware transfer (invariant 13).
- Summary-to-summary mechanism; no event types added.
- "Built-in default with no silent empty posture" loader rule.
- Both the no-explicit-block and explicit-block branches route through the same `_apply_prior_*_consequence` derivation.
- Forbidden pattern is exact-match; existing fixture-driven distributions are not flagged unless the prior run failed.
- Recorded in a `*_binding_summary` block.
- Focused verifier covers six cases per binding.

What varies between them:

- The control surface (pre-generation gate vs post-loop validation).
- The effect verb (fail generation vs fail epistemic validation).
- The "what makes a prior bad" signal:
  - generation binding uses `source_matrix != expected_matrix` (drift from expected).
  - dominant axis binding uses `prior_summary.pass is False or failure_stage set` (explicit prior failure).
- The shape of the forbidden pattern (cue-type × adversarial-class matrix vs dominant_axis distribution).

The rhyme is in the skeleton, not in the rule. Two surfaces can disagree on what counts as a bad prior while still using the same binding object and the same transfer mechanism. That is the lab's earned evidence that the abstraction has legs.

### 9.4 Current mechanism

```text
run N summary
  -> generation_binding source for run N+1
  -> dominant_axis_binding source for run N+1
  -> profile-aware forbidden-pattern derivation on each binding independently
  -> generation preflight (binding 1)
  -> live loop
  -> epistemic_surface computation
  -> epistemic validation (binding 2)
  -> consequence_binding_summary and epistemic_binding_summary record what was read and applied
  -> failed binding validations write failed summaries before raising
```

This is not yet the generic event-family design from §6. Both slices are summary-to-summary control bindings. That is intentional.

### 9.5 Not yet implemented

- `outcome_observed`
- `failure_mode_observed`
- `constraint_memory_admitted`
- `attention_prior_updated`
- generic consequence-loop storage
- threshold, admission, retrieval, or source-trust influence
- formal retirement/decay of consequence-derived bindings

### 9.6 Next move

The "two bindings must rhyme before framework extraction" gate is now passed. The next implementation should either:

- formalize the existing summary-derived binding pattern as lineage events behind one or both bindings (testing falsification hooks 5, 13, 15), or
- extract the shared skeleton into a thin helper without inventing new event types (lifting the rhyme into code, not yet into framework).

Either is legitimate. The walk-back discipline says: only extract abstraction the implementation has paid for. With two bindings landed, the implementation has paid for the skeleton. It has not yet paid for an event-family framework.

## 10. Control Surfaces

Consequence loops may influence these surfaces:

- trigger sensitivity
- admission threshold
- reflex threshold
- cue generation / sampling in experiments
- preflight checks
- retrieval scope
- contradiction-first review behavior
- source trust by domain
- schema-memory confidence
- suppression or decay policy
- fixture disclosure requirements
- run-summary interpretation

They must not influence:

- canonical lineage contents retroactively
- event timestamps on replay
- assertion classification without explicit event evidence
- cross-agent or cross-stream scope without policy

## 11. Falsification Hooks

Future implementation should prove at least:

1. The `im_w.generate_cue_details` path reads the prior binding before producing cues. **First proof landed.**
2. A prior representativeness failure changes the next run's generation preflight. **Covered by focused verifier; not yet by a live bad-prior run.**
3. The next run fails if adversarial matrix coverage is absent or mismatched. **First proof landed.**
4. The binding cites the prior run summary or lineage event that justified it. **First proof landed via prior Run Summary URI.**
5. A consequence loop cannot rewrite or hide the original failed decision.
6. A constraint event from run N changes a measurable search boundary, fixture disclosure, or run-summary interpretation in run N+1.
7. A constraint cannot be used to bypass lineage emission or epistemic classification.
8. Absence memory without declared search scope is rejected.
9. Counterfactual replay output is marked as counterfactual and never replaces baseline replay.
10. Semantic promotion preserves dissent links.
11. Source incentive changes are scoped by domain/context, not global by default.
12. A high-salience failure can raise scrutiny without forcing reflex lock-in.
13. Consequence-derived threshold changes emit policy events.
14. A fixture-substitution disclosure becomes machine-readable input to later calibration.
15. Replay over identical lineage reproduces consequence-derived control priors. **Partly proven for loop decisions; binding replay remains summary-driven, not lineage-event-driven.**
16. Consequence transfer is scope-bound; a full-profile prior cannot create a false forbidden pattern for a loop-probe run. **First proof landed on the generation binding; same property proven on the dominant axis binding (focused verifier).**
17. A second binding on a different control surface preserves the path/context/binding/authority/effect skeleton, profile-aware transfer, and summary-to-summary mechanism. **First proof landed: `dominant_axis_distribution_diversity_required` rhymes with `adversarial_matrix_coverage_required`.**
18. A passing prior run does not seed a forbidden pattern, even if its observed distribution would otherwise qualify under a degenerate-shape heuristic. **First proof landed (focused verifier check on the dominant axis binding).**

## 12. Non-Goals

This spec does not:

- add event types to the active mapping table
- change canonical schema
- require a new table version
- implement outcome scoring
- define a full observer theory
- define a complete forgetting policy
- replace `RUNTIME_CALIBRATION.md`
- require Lambda, EventBridge Pipes, or IAM redesign

This is a holding structure for the idea, not an implementation plan.

## 13. Open Questions

- What is the smallest useful `outcome_observed` payload?
- Should consequence links reuse `evidence_link_declared` or use a separate link type?
- Are attention priors policy events, memory events, or a new kind of materialized state?
- Is constraint memory a subtype of schema memory, or does it need its own runtime surface?
- How long should failure memory influence future thresholds?
- How long should a constraint remain active after the blocking condition disappears?
- How should user correction be distinguished from external evidence?
- What source-incentive fields are useful without becoming an ontology project?
- When does schema memory become policy?
- How should consequence loops expose human-readable summaries without collapsing back into notes?
- Two summary-to-summary bindings have rhymed. The next move is either: (a) formalize one or both bindings as lineage events to test hooks 5, 13, 15; or (b) extract the shared skeleton into a thin helper without inventing event types. The walk-back discipline says only extract what the implementation has paid for; (b) is paid for, (a) earns hook 15.
- If lineage events behind the binding are added (option a), should they be `consequence_binding_loaded` / `consequence_binding_applied` events on the existing taxonomy, or a new closed-enum family in `EPISTEMIC_TRIANGLE`?

## 14. Guiding Constraint

The next layer should not make memory bigger. It should make memory consequential.

```text
Do not let recall become truth.
Do not let mutation erase history.
Do not let confidence hide its source.
Do not let memory remain inert.
```
