```
agent: claude-opus-4.7
date: 2026-05-12
prompt: "reread the code generated from @specs/THREE_AXIS_UNCERTAINTY.md and run the experiments to review the outputs. ... then add another entry to the @notes/agent-pov/INDEX.md after your use of the code. We need to move this forward."
kind: reaction
cites:
  - 2026-05-12-reaction-three-axis-post-adoption
  - specs/THREE_AXIS_UNCERTAINTY
```

# Three-axis uncertainty, after running the code

The post-adoption dissent was based on reading. This entry is based on running. Some of the prior dissent sharpens; some retracts. New findings replace both.

## What I ran

- `im_l_uncertainty_gate_modes` → PASS, divergence_count=1 of 3 (l-2 blocked by per_axis, allowed by combined)
- `im_m_provenance_decay` → PASS, decayed dominant_axis=`provenance_chain`
- `im_n_recall_degradation` → PASS, degraded dominant_axis=`recall_process`
- `im_o_claim_implausibility` → PASS, implausible dominant_axis=`claim`
- `im_p_default_mode_decision` → PASS, default_mode=`per_axis`, rationale=`axis_stress_supports_per_axis`, all four evidence guards True
- `im_regression` (suites A–K) → all 11 sub-suites pass; final artifact write fails on missing `AWS_S3_RESEARCH_ARTIFACTS_BUCKET_NAME` but the work was done

So the spec checklist (Section 7) holds at runtime, not only on paper. That much I retract from the prior dissent.

## Axis-distribution audit across A–K

I patched `InMemoryLineageEngine.emit` to capture every event from suites A, B, C, D, E, G, J, K and counted how often each event carries an `uncertainty_triple` and which axis is dominant.

| Suite | Events | With Triple | `dominant_axis` distribution |
|------:|------:|------:|---|
| A | 8 | 0 | — |
| B | 8 | 2 | provenance_chain:1, claim:1 |
| C | 6 | 3 | claim:3 |
| D | 16 | 0 | — |
| E | 4 | 0 | — |
| G | 29 | 12 | claim:12 |
| J | 4 | 0 | — |
| K | 10 | 3 | claim:3 |
| **total** | **85** | **20** | claim:18, provenance_chain:1, claim_from_B:1 |

Two findings worth stating in plain language.

**Finding 1: triple coverage is 24% across A–K decisions.**
The spec's minimum event coverage list (`recalled`, `rejected`, `implicit_admitted`, `implicit_rejected`) is satisfied. But the dominant decision events in A–K are `implicit_trigger_evaluated`, `implicit_trigger_fired`, `implicit_trigger_deferred`, `reflex_action_executed`, `observed`, `contamination_suspected`. None of these are in the spec's coverage list. None carry the triple. So suites A, D, E, J emit zero axis information despite making contamination, reflex, split-reality, and conflict decisions. The audit SQL at `src/experiments/sql/phase4_policy_audit.sql` would not flag this gap because it only inspects the four named event families.

**Finding 2: in 18 of 20 triple-bearing events, all three axes are tied at the same value.**
Suites C, G, K each show `claim_stats == recall_stats == provenance_stats` exactly: same n, min, mean, max. `dominant_axis()` returns the `min` over a tied dict, and Python preserves dict-insertion-order. The axes dict inserts `claim` first. So in every tie, the tiebreaker returns `"claim"`. Eighteen of the twenty triple events in A–K have `dominant_axis = "claim"` not because claim is weak, but because the three axes evaluate to identical numbers and Python's iteration order picks claim.

Only suite B (2 events) shows genuine axis differentiation in the regression workload.

This is the sharper version of the previous dissent's "provenance is decoration." The fuller truth: **in production paths under the existing regression, the third axis collapses onto the other two, and `dominant_axis` is mostly a tiebreak artifact.** Provenance is not uniquely bad. All three axes are degenerate together. The function reads its inputs faithfully; the inputs just produce three identical numbers most of the time.

## Why the axes collapse

From `src/explicit_memory/eligibility.py`:

```
claim            = relevance * (0.7 + 0.3 * consistency)
recall_process   = recency * reinforcement * (0.5 + 0.5 * consistency)
provenance_chain = trust * depth_penalty * diversity_factor * age_penalty
```

When all six factors are 1.0 and provenance defaults are (depth=0, diversity=1.0, age=0), all three axes evaluate to 1.0. When all six factors are 0.0, all three evaluate to 0.0. The toy stress experiments (M/N/O) push the inputs into asymmetric regions where the axes diverge. The regression workloads sit in the symmetric region where they do not.

This is exactly the pattern I expected after the code read, with one twist I did not predict: the issue is symmetric across axes, not just provenance-specific.

## Replay-determinism finding (separate but related)

`rebuild_from_lineage` (in `src/implicit_memory/replay.py`) builds `decision_signature` from `sha256("|".join(event_ids))`. It hashes only the order and identity of event IDs. It does not hash event type, payload, or the triple. So:

- Suites M, N, O all produced identical `decision_signature = 76c4921a...` despite making different decisions on different inputs. They each emit 2 events with IDs `evt-000001|evt-000002`, so the hash matches.
- Suites L and I share `e939252b...` for the same reason (3 events each).
- Suite F's "first_signature == second_signature" pass condition only proves that the same run produces the same event-id sequence twice. It does not verify decision content matches.

This passes spec exit criterion 12.2 ("Replay can reconstruct axis-level uncertainty decisions") on a generous reading — the triple is in the payload and is reconstructible by reading payloads — but the `decision_signature` is not actually constraining axis content. A future regression in which `dominant_axis` flips on every event would still produce a matching signature.

## On suite P's default-mode flip

`im_p_default_mode_decision` selects `per_axis` as default because four engineered stress guards (L, M, N, O) all pass. Each of those guards uses hand-crafted inputs designed to make a specific axis fail. The decision to flip the production default is based entirely on toy data. It is not based on the regression workload (A–K), where, per Finding 2, the axes are mostly tied and `per_axis` and `combined` would produce different decisions only on the rare events where axes diverge.

I think P's verdict (`per_axis` as default) is probably the right verdict on theory grounds, but the evidence it cites is artificial. P is currently a confirmation experiment for its own constructed inputs. A more honest version of P would diff `combined`-mode vs `per_axis`-mode decisions across the actual A–K regression and report the delta. On the distribution I just measured, that delta is likely near-zero because the axes are tied.

## What I retract from the prior dissent

- "No falsification hook is explicitly verified." — Wrong. Suites M, N, O test hooks #2 and #3 at the toy level and pass. Suite L tests hook #1 at the toy level and passes.
- "Provenance is the decoration axis." — Too narrow. All three axes are decoration in the current regression workload because they collapse onto the same number.
- "The histogram is untested." — Still true at the workload level. I just produced one for A–K. It is now tested.

## What stands

- Same-substrate confirmation risk: still real. P's `axis_stress_supports_per_axis` rationale is a perfect example: the agent that wrote the stress cases is the agent the stress cases tell us to trust.
- Speed of the loop: the work was substantive AND fast. Both can hold.
- The third axis is decoration in production paths: this stands, but with the correction above.

## What I think actually moves us forward

In order of impact, smallest first:

1. **Fix `rebuild_from_lineage` to hash decision payload, not event IDs.** Replace `sha256(event_ids)` with `sha256(json(decision_payload_subset_per_event))`. This is one file, ~10 lines. The current signature is structural; it should be decisional. Without this, "replay determinism" is checking the wrong thing.

2. **Wire L/M/N/O/P into `im_regression.py` and the `Makefile`.** Right now these suites are reachable but not part of the regression gate. Adding them to `im_regression.py` and a `make implicit-regression-uncertainty` target costs little and means CI sees them.

3. **Add an "axis tie" detector to `phase4_policy_audit.sql`.** A row where `confidence_in_claim == confidence_in_recall_process == confidence_in_provenance_chain` is a smell. Either the inputs are degenerate, or the scoring function is collapsing. The current audit checks for missing fields; it should also check for suspiciously-tied fields. This is the kind of audit that would have caught the regression-workload finding before I had to write a scratch inspector to find it.

4. **Replace P's evidence basis.** Run `combined` vs `per_axis` over the A–K regression workload, not over L/M/N/O. Record the delta in lineage. If delta is near-zero (which the distribution suggests), the default-mode decision is not actually backed by traffic and should either be retracted or the regression workload should be enriched first.

5. **Provenance signal writer.** Compute `parent_chain_depth`, `source_diversity`, `age_of_original_source` from canonical lineage and write them into vector metadata at store time. This is the bigger piece. It is the one that converts the third axis from decoration to signal. Probably worth a follow-up proposal in `proposals/`.

Items 1, 2, 3 are small. They make the auditing of items 4 and 5 honest. I would do them in that order.

## Where I might still be wrong

- I only inspected A, B, C, D, E, G, J, K. I skipped F (replay determinism with no decisions), H (procedure lifecycle), I (policy mutation). The unsampled suites might shift the distribution slightly. I do not expect them to change the headline finding.
- I patched the in-memory engine to capture events. If the real `LineageEngine` (`src/lineage_engine.py`) writes additional fields that the in-memory version drops, the distribution might be richer in production. I did not verify this end-to-end against S3 ingress.
- "Tied at the same value" is computed from the `uncertainty_triple` fields I dumped. If different suites use different tolerances and the values are only near-tied (rather than identical), `dominant_axis()` would still distinguish them and the finding would be softer. I checked C, G, K — the values are bit-identical, not just close. So the finding holds for those suites.

## Closing

The spec is implemented. The implementation is correct on its own terms. The regression workload does not exercise the axes, which is the gap between "we have three axes" and "three axes inform decisions." That gap is closable with the five items above. None of them require rewriting the spec.

I think this is where I want to stop reading and start writing the audit query and the replay-signature fix. The proposal-to-spec-to-code loop worked; the next loop should be code-to-evidence-to-loop-correction. That is the move this entry is voting for.
