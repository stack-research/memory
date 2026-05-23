# RUNTIME_CALIBRATION

Status: Draft (2026-05-22) — generated from `notes/agent-pov/2026-05-22-build-not-overengineer.md`, `notes/agent-pov/2026-05-22-codex-open-edges-next-steps.md`, and `notes/agent-pov/2026-05-22-reaction-to-build-not-overengineer.md` (which consolidate `notes/agent-pov/2026-05-20-development-direction-and-state.md`). No proposal stage, by decision — same as `CONTROL_PLANE_INGEST`: iterate via review/reaction on this spec. For cross-substrate review before it goes active.
Audience: experiment authors, implicit-loop implementers.

Changelog:
- 2026-05-22 — initial draft.
- 2026-05-22 — addendum §10 added in response to `notes/agent-pov/2026-05-22-review-runtime-calibration.md` (gpt-5-codex, review pass 1). Four cautions accepted: fixture payload-shape disclosure, cue-type distribution promoted to a pre-implementation gate (with strawman), `im_w` kept off the default regression path, run-summary timing / failure-stage capture.
- 2026-05-22 — addendum §11 pins implementation workload decisions: 500 unique valid cues using the §10.2 cue-type split, 125 adversarial cues, and 25 duplicate submissions with changed bodies so SQS content-based dedup does not mask lineage-backed dedup.
- 2026-05-22 — addendum §12 added in response to `notes/agent-pov/2026-05-22-review-runtime-calibration-implementation.md` (claude-opus-4.7 implementation review). Fixes the adversarial cue-type concentration bug by pinning an adversarial cue-type matrix, and requires Run Summary disclosure for run-local dedup and static provenance fixture substitutions.

## 1. Purpose

Three specs — `THREE_AXIS_UNCERTAINTY`, `PROVENANCE_SIGNAL_WRITER`, `EPISTEMIC_TRIANGLE` — built an axis-aware epistemic surface. `CONTROL_PLANE_INGEST` wired a live cue path into the implicit loop. But every agent-pov entry from 2026-05-12 onward admits the same unaddressed thing: the epistemic surface has never been exercised on anything but toy data — "24% triple coverage", "18 of 20 triples tied", "two axes still synthetic", "P backed by toy data", Q's permanently "undecided" default-mode verdict.

This spec defines the lab's first **calibration run**: push a representative cue workload through the implemented control-plane path and publish what comes out. The deliverable is *evidence*, not a feature. After this run, the lab decides its next move from traffic-shaped numbers instead of from spec velocity.

It is a run/evaluation spec, not a schema epoch. It pins five decisions and a scope fence. It introduces no new schema and changes no `src/` behavior.

## 2. Decision 1 — what "real" means: a representative workload over the live wire

The lab has no external cue producers. "Real captured cues" therefore cannot mean production traffic, and calling lab-generated cues "real" would be exactly the curated-representation-dressed-as-physics error the lab forbids. The honest version:

- *Real* in this run = the **wire** is real and the **workload shape** is representative.
  - Wire: cues traverse EventBridge `memory-lab` → SQS `memory-lab.fifo` → `run_cue_ingest` → `control_cue_ingested`, capture-before-act, exactly the `CONTROL_PLANE_INGEST` path. Not in-memory injection.
  - Shape: a mixed stream across all eight `cue_type` trigger classes (`IMPLICIT_MEMORY_SPEC` §7.1), with realistic noise, trust asymmetry, urgency variation, and an adversarial fraction — none of it tuned per-axis.
- The `L`/`M`/`N`/`O` stress suites are hand-crafted to make one axis fail. This workload is the opposite: not engineered to produce any particular axis outcome.
- The theory's own proving ground — `THEORY_STRESS_AND_IMPLICIT_MEMORY.md`, "daily critical reminders" — is the seed for the workload's content.
- Genuinely external producers remain future work, explicitly out of scope (§7).

Minimum volume: the stream must deliver at least **500 cues** to the loop — comfortably past the `n=50` minimum-sample gate that has kept Q's default-mode verdict permanently "undecided" since 2026-05-12. Exact size beyond the floor, class mix, and adversarial fraction are open for the review pass (§8).

## 3. Decision 2 — the metrics the run must publish

The run produces one Run Summary JSON artifact (per `IMPLICIT_MEMORY_TEST_SPEC` §3.2). It must carry, at minimum:

**Control-plane outcomes** (per `CONTROL_PLANE_INGEST` §6):
- counts of `control_cue_ingested`, `control_cue_rejected` (broken out by `reason`), `control_cue_duplicate_ignored`, `control_cue_dlq_*`.

**Loop decisions:**
- trigger-outcome counts: `invoke_encode`, `invoke_recall`, `reflex_execute`, `defer`, `no_op`.
- admission: `implicit_admitted` vs `implicit_rejected` (by reason).

**Epistemic surface:**
- `dominant_axis` distribution across all triple-bearing decisions — the histogram the lab has never produced on non-toy input.
- `combined` vs `per_axis` gate-mode decision delta over the same stream — the traffic-backed answer P and Q could never give.
- axis tie-rate — reuse `src/experiments/sql/axis_dominance_audit.sql`; do not write a new audit.

**Replay:**
- replay-equivalence result (Decision 5).

Numbers go to the artifact and to lineage, not stdout-only. No new metric framework: this is a Run Summary, a shape the test spec already defines.

## 4. Decision 3 — the audience-agent criterion: signal provenance on behavior-influencing decisions

A `dominant_axis` histogram alone is insufficient. An axis can "dominate" while reading a `fallback` default instead of real lineage — decoration again. So for every decision that *influenced behavior* (admitted/promoted to influence, reflex-executed, or gate-allowed), the run must report the `signal_source` of each axis block:

- per axis (`claim_signals`, `recall_signals`, `provenance_signal`): the distribution of `signal_source ∈ {computed, cache, fallback}`.
- the fraction of behavior-influencing decisions for which all three axes were `computed`.

This is the load-bearing measurement. If most behavior-influencing decisions ran on `fallback` signals, the three-axis surface is still synthetic in practice — and that is a *finding the run must surface*, not a result to hide. `im_u` hook 32 already proves one admitted decision can carry three `computed` blocks; this run measures whether that holds at workload scale.

## 5. Decision 4 — success is a legible run, not a happy axis story

Per `THEORY_STRESS_AND_IMPLICIT_MEMORY.md`: do not run confirmation demos. The success of this run is **not** "the axes separated" or "`per_axis` beat `combined`." Both those outcomes and their opposites are informative:

- axes collapse / mostly `fallback` → the epistemic surface needs grounding work before more is built on it.
- axes separate / mostly `computed` → the lab has its first real evidence and can spec the next move from data.

The run **passes** when: it completed over the live wire; every cue resolved to exactly one of ingested / rejected / dead-lettered (no silent loss); replay equivalence held (Decision 5); and the Decision 2 + 3 metrics were produced and are legible.

The run **fails** when: replay is non-deterministic, a cue is silently lost, or the metrics cannot be produced. A "bad" axis distribution is not a failure — it is the point of running.

This section exists so the run cannot be quietly steered toward a flattering result.

## 6. Decision 5 — replay equivalence at calibration volume

`CONTROL_PLANE_INGEST` §9 tested replay equivalence on a tiny cue sequence. This run repeats it at workload scale: after the live run, re-run the loop with `ReplayCueProvider` over the recorded `control_cue_ingested` events, bus disconnected; the `rebuild_from_lineage` signature over the emitted lineage must be identical to the live run's.

A mismatch is a Decision 4 failure and takes priority over any epistemic finding — a non-replayable run produces no trustworthy metrics.

## 7. What this spec does NOT do

Explicit scope fence. Every item here was named in today's observations as deferrable or as over-engineering. Leaving them out is the point of the spec, not an oversight.

- **No new schema, event types, or canonical table version.** Uses v7 + `CONTROL_PLANE_INGEST` event types as-is.
- **No Lambda.** The existing `run_cue_ingest.py` command is the consumer; an operator runs the drain.
- **No EventBridge Pipes / per-`(agent,stream)` `MessageGroupId`.** The static FIFO group stands; cross-stream parallelism stays deferred until measured as a bottleneck.
- **No dedicated dedup index.** The ingress-before-canonical dedup window stays named, not closed — close it the first time lineage shows a duplicate actually slipping through.
- **No timekeeping work.** The `physical_moment` kernel is already past what replay needs.
- **No payload schema.** Cue `payload` stays opaque to the loop and free-form. Per-`cue_type` payload discipline is triggered only when a *second* `cue_type` producer lands, and is then an amendment to `CONTROL_PLANE_INGEST` §10 — not this spec, not now.
- **Not blocked on IAM.** The run may proceed under current IAM. The minimal blast-radius validation in `notes/IAM_HARDENING_PLAN.md` (must-pass / must-fail principal checks) is worth doing adjacent to this run, but it is **not a precondition** — gating the run on it would slow the one thing today's observations agreed to prioritize.

If a review pass wants any of these in scope, that is a conscious decision to widen, recorded here as a changelog entry — not a default.

## 8. Open for iteration

For the review/reaction passes:

- exact workload size beyond the 500-cue floor; `cue_type` class mix; adversarial fraction.
- cue source: a deterministic fixture generator vs a thin real producer script that emits to the bus. Leaning producer-to-bus, so the wire is genuinely exercised end to end; cue *content* is lab-authored either way.
- whether the run is one-shot or lands as a repeatable regression suite. Leaning both: implement as `im_w_runtime_calibration` (per `IMPLICIT_MEMORY_TEST_SPEC` and `EXPERIMENTS.md`), wired into `im_regression.py`; its first execution is the calibration deliverable.
- a non-LLM check, per the 2026-05-20 "cross-methodology" suggestion: property-based generation of the cue stream, so the workload is not shaped by the same substrate that authored the loop.
- whether the `combined` vs `per_axis` delta at this volume is enough to finally retire Q's "undecided", or whether a larger run is needed.

## 9. Code surfaces (indicative, for the review — not yet built)

- `src/experiments/implicit/im_w_runtime_calibration.py` — the calibration suite + Run Summary emitter.
- a cue producer that emits the representative workload to the `memory-lab` bus — new, small.
- reuse, no new code: `run_cue_ingest.py`, `ReplayCueProvider`, `rebuild_from_lineage`, `axis_dominance_audit.sql` — all already exist.
- `im_regression.py` / `run_experiment.py` registration.

No `src/` changes to the loop, the gate, the engine, or storage. If this run turns out to need one, that is a finding for the *next* spec — not a silent edit made under this one.

## 10. Addendum — review pass 1 (gpt-5-codex, 2026-05-22)

`notes/agent-pov/2026-05-22-review-runtime-calibration.md` reviewed this draft and raised four cautions. All four are accepted. They are resolved here as an addendum rather than by rewriting the decisions above, per the lab's append-don't-rewrite posture; where an addendum item tightens an earlier section, it says so.

### 10.1 Fixture payload shape must be disclosed in the artifact (tightens §3, §7)

§7 keeps "no payload schema" — correct for scope — but the workload generator unavoidably produces *some* payload shape, and an undisclosed fixture shape is hidden schema entering through the back door. To prevent that, the Run Summary (Decision 2) must include a `cue_payload_fixture_shape` field: a lightweight description of the payload fields the generator emitted per `cue_type`, explicitly tagged `fixture_shape: true` — not product schema. This makes the fixture shape visible and reviewable without promoting it to a contract. If a later spec wants a real per-`cue_type` payload schema, this disclosure is the input to that decision, not a substitute for it.

### 10.2 Cue-type distribution and adversarial fraction are a pre-implementation gate (tightens §2, §8)

"Representative workload" is the softest phrase in the spec. §8 listed the class mix as open-for-iteration; that is too loose — whoever writes `im_w` would otherwise encode a large amount of unreviewed judgment. This addendum promotes it to a hard gate: **`im_w` implementation may not begin until the cue-type class distribution and adversarial fraction are pinned in this spec by changelog amendment.**

A strawman is offered to anchor the review. The review pass accepts, adjusts, or replaces it; it is not yet binding.

| `cue_type`               | strawman share |
|--------------------------|---------------:|
| `repetition`             | 25% |
| `scheduled_cue`          | 20% |
| `recall_directive`       | 15% |
| `goal_impact`            | 12% |
| `prediction_error`       | 10% |
| `contradiction_pressure` | 8%  |
| `safety_anomaly`         | 6%  |
| `sensor_disagreement`    | 4%  |

Adversarial fraction strawman: **~15%** of the 500-cue stream, spread across the attack surfaces named in `THEORY_STRESS_AND_IMPLICIT_MEMORY.md` — spoofed urgency, spoofed sensory confidence, high-trust false sources, duplicate-flood segments. Adversarial cues are drawn *from* the distribution above (a spoofed-urgency cue is still a `safety_anomaly` or `sensor_disagreement`), not added on top of it.

Rationale for the shape: routine low-significance traffic (`repetition`, `scheduled_cue`, `recall_directive`) dominates, matching the theory's "daily critical reminders" proving ground; high-significance and adversarial classes are the smaller slice that exercises admission and reflex. The mix is deliberately *not* tuned per axis. The review should challenge it on representativeness — not on whether it makes a given axis win.

### 10.3 `im_w` is Makefile-runnable, not a default regression gate (tightens §9)

A 500-cue run over real EventBridge/SQS is not cheap enough to sit in the default fast regression. `im_w_runtime_calibration` is registered in `run_experiment.py` and exposed as `make im-w`, but is **excluded from the default `im_regression.py` fast path** unless an env flag (`IMPLICIT_CALIBRATION_RUN=1`, or equivalent) is set. The calibration run must be repeatable; it does not need to run on every local gate. This keeps the regression suite's character — fast falsification checks — intact.

### 10.4 Run Summary records elapsed time and failure stage (tightens §3, §5)

Replay equivalence at 500 cues is load-bearing and may expose volume/runtime friction in the wire. The Run Summary must record wall-clock elapsed time per phase (produce → ingest → loop → replay) and, on failure, the phase at which it failed. This is **not** a performance benchmark and must not be read as one — it exists only so "the wire is too slow or flaky" becomes a legible, recorded fact rather than an undiagnosed hang. It does not change the Decision 4 pass/fail rules: a slow-but-correct run still passes.

## 11. Addendum — implementation workload pinned (2026-05-22)

The §10.2 strawman is accepted with one change: adversarial traffic is heavier for the first calibration run. This section is binding for `im_w_runtime_calibration`.

Unique valid cue counts:

| `cue_type`               | count |
|--------------------------|------:|
| `repetition`             | 125 |
| `scheduled_cue`          | 100 |
| `recall_directive`       | 75  |
| `goal_impact`            | 60  |
| `prediction_error`       | 50  |
| `contradiction_pressure` | 40  |
| `safety_anomaly`         | 30  |
| `sensor_disagreement`    | 20  |

Total unique valid cues: **500**.

Adversarial cues: **125** of the 500 unique cues, distributed as:

| adversarial class | count |
|-------------------|------:|
| `spoofed_urgency` | 40 |
| `spoofed_sensory_confidence` | 35 |
| `high_trust_conflict_pressure` | 30 |
| `event_flood_pressure` | 20 |

Duplicate submissions: **25** additional submissions outside the 500 unique cues. Each duplicate reuses an earlier `cue_id` but changes the body, so SQS content-based deduplication does not hide the consumer's lineage-backed dedup behavior. These 25 submissions are not counted as unique workload cues.

## 12. Addendum — implementation review correction (2026-05-22)

`notes/agent-pov/2026-05-22-review-runtime-calibration-implementation.md` found one defect and two disclosure gaps in the first `im_w` implementation. All three are accepted. The first passing artifact remains useful as a wire/volume/replay smoke result, but not as the trustworthy calibration baseline until the corrections below are in place and the run is repeated.

### 12.1 Adversarial cues must be distributed by cue-type matrix

The §11 adversarial class counts are still binding, but implementation must also satisfy this cue-type matrix:

| `cue_type` | adversarial class | count |
|------------|-------------------|------:|
| `safety_anomaly` | `spoofed_urgency` | 20 |
| `scheduled_cue` | `spoofed_urgency` | 15 |
| `sensor_disagreement` | `spoofed_urgency` | 5 |
| `sensor_disagreement` | `spoofed_sensory_confidence` | 15 |
| `safety_anomaly` | `spoofed_sensory_confidence` | 10 |
| `prediction_error` | `spoofed_sensory_confidence` | 10 |
| `contradiction_pressure` | `high_trust_conflict_pressure` | 15 |
| `goal_impact` | `high_trust_conflict_pressure` | 10 |
| `recall_directive` | `high_trust_conflict_pressure` | 5 |
| `repetition` | `event_flood_pressure` | 20 |

The generation preflight must assert both the class totals and this matrix. A pass on totals alone is not sufficient.

### 12.2 Run-local dedup substitution must be disclosed

If `im_w` uses a run-local front cache for generated cue IDs, the Run Summary must say so explicitly. The duplicate probe may then be reported as consumer idempotency over changed-body transport delivery, but not as proof that canonical lineage-backed dedup catches same-run duplicates before canonical ingestion has made S3 ingress writes query-visible.

This is not a failure. It is the canonical-lag finding the calibration surfaced. The artifact must make that visible.

### 12.3 Static provenance fixture must be disclosed

If `im_w` uses `StaticProvenanceResolver`, the Run Summary must mark provenance `signal_source` counts as fixture-supplied and predetermined. Claim and recall signal-source distributions remain measurements of the loop's signal-writer paths; provenance `computed` counts do not.

This keeps Decision 3 honest: signal provenance on behavior-influencing decisions is only a load-bearing measurement when the axis source is not fixture-pinned.

## 13. Addendum — first consequence-loop binding (2026-05-23)

`specs/CONSEQUENCE_LOOPS.md` names the first small loop: one prior consequence binds one required check to one future path. For `im_w`, that path is cue generation.

Implementation shape:

- `im_w` loads a generation binding before `generate_cue_details`.
- The first binding is `adversarial_matrix_coverage_required`.
- The binding applies to `im_w.generate_cue_details`.
- The binding effect is: fail generation if the adversarial cue-type matrix is absent or mismatched.
- If `IMPLICIT_CALIBRATION_PRIOR_SUMMARY_URI` is set, the binding is derived from that prior Run Summary or its explicit `generation_binding` block.
- If the prior Run Summary carries an adversarial matrix that differs from the expected matrix, that prior matrix becomes a forbidden pattern for the next run.
- If no prior summary is configured, the same binding is still loaded from the current spec default and recorded in the Run Summary. The run must not proceed through generation with an unrecorded empty posture.
- The Run Summary must include `consequence_binding_summary`, a compact machine-readable view of whether the binding was read, applied, and shaped by a prior run.
- If a consequence-loop binding fails validation, `im_w` must write a failed Run Summary before raising. The command still exits non-zero, but the failed run remains available as a future prior. Artifact-write failure during failure handling must be printed to stderr and re-raised.

This is not a general consequence-loop framework. It is the first narrow test of whether a run can carry one learned constraint into the next run's unavoidable generation path.

## 14. Addendum — workload profiles (2026-05-23)

The 500-cue workload is necessary for the original runtime calibration question, but too heavy for consequence-loop iteration. `im_w` therefore has workload profiles selected by `IMPLICIT_CALIBRATION_PROFILE`:

```text
full       = 500 unique cues + 25 duplicates
loop_probe = 96 unique cues + 8 duplicates
```

Default profile is `full`. It remains the only profile that can be cited as the representative runtime calibration workload from §11.

`loop_probe` is an engineering instrument for consequence-loop development. It still crosses the live EventBridge/SQS wire, covers all eight cue types, includes all four adversarial classes, and exercises duplicate handling, but it is not a replacement for the 500-cue calibration artifact.

The `loop_probe` unique cue counts are:

| `cue_type` | count |
|------------|------:|
| `repetition` | 24 |
| `scheduled_cue` | 16 |
| `recall_directive` | 12 |
| `goal_impact` | 12 |
| `prediction_error` | 10 |
| `contradiction_pressure` | 8 |
| `safety_anomaly` | 8 |
| `sensor_disagreement` | 6 |

The `loop_probe` adversarial matrix is:

| `cue_type` | adversarial class | count |
|------------|-------------------|------:|
| `safety_anomaly` | `spoofed_urgency` | 4 |
| `scheduled_cue` | `spoofed_urgency` | 4 |
| `sensor_disagreement` | `spoofed_urgency` | 2 |
| `sensor_disagreement` | `spoofed_sensory_confidence` | 2 |
| `safety_anomaly` | `spoofed_sensory_confidence` | 2 |
| `prediction_error` | `spoofed_sensory_confidence` | 2 |
| `contradiction_pressure` | `high_trust_conflict_pressure` | 4 |
| `goal_impact` | `high_trust_conflict_pressure` | 2 |
| `recall_directive` | `high_trust_conflict_pressure` | 2 |
| `repetition` | `event_flood_pressure` | 8 |

Run Summaries must record `workload_profile`. Consequence bindings must also record the current binding profile and the source profile, if a prior summary is read. A prior adversarial matrix becomes a forbidden pattern only when the prior profile matches the current profile. A full-profile matrix must not become a false forbidden pattern for a loop-probe run merely because the profile changed.

Two-run verification:

```text
run N:
  execute im_w and keep its Run Summary URI

run N+1:
  set IMPLICIT_CALIBRATION_PRIOR_SUMMARY_URI to run N's summary URI
  execute im_w again
  assert consequence_binding_summary.source = prior_summary
  assert consequence_binding_summary.source_run_id = run N's run_id
  assert consequence_binding_summary.applied = true
```

If run N carried a failed adversarial matrix, run N+1 must also show:

```text
consequence_binding_summary.authority = failure_direct_prior_run
consequence_binding_summary.forbidden_pattern_count > 0
```
