```
agent: claude-opus-4-7
date: 2026-05-13
prompt: "review the lab. Cloudformation files are in the @stacks directory. The memory lab code is in @src. How would you rate the lab now?"
kind: observation
cites: [2026-05-11-rating-the-lab, 2026-05-12-reaction-three-axis-post-adoption, 2026-05-12-axis-distribution-from-runs, 2026-05-12-after-shipping-the-five]
```

# Rating after the provenance signal writer landed

## Summary

- Bones: **8.5/10** (was 8/10)
- Epistemics: **7/10** (was 4/10)
- Loop discipline (the lab's own meta-process): **9/10** (new axis worth naming)

The two-day arc since the prior rating — proposal → spec → implementation → dissent → second proposal → spec → implementation → closeout — closed the gap the prior entry called the "deepest." Three axes are now first-class, the third axis reads real lineage shape, and the replay signature hashes decisions instead of event IDs. None of those were rhetorical.

## What changed since the 2026-05-11 rating

Verified from the code, not from the breadcrumb stubs.

1. **Three axes are emitted on the four required event families.** `src/implicit_memory/loop.py` `_admit_and_gate` writes `uncertainty_triple`, `combined_score`, `dominant_axis`, `uncertainty_gate_mode` on both `implicit_admitted` and `implicit_rejected`. `score_triple` lives in `src/explicit_memory/eligibility.py`.
2. `**per_axis` gate mode is wired and selectable.** `evaluate_uncertainty_gate` takes a `gate_mode` argument; loop reads it from `cfg.retrieval_policy.uncertainty_gate_mode`. The Phase C default-mode decision is recorded in lineage (per the cited 05-12 entries).
3. **Provenance is computed from lineage, not from defaults.** `src/explicit_memory/provenance.py::compute_chain_signals` does a deterministic chain walk with tie-break (`max event_time`, then min lexicographic `event_id`), bounded depth (64), and machine-readable `fallback_reason`. `LineageProvenanceResolver` wires it into the implicit loop. Both `provenance_signals_computed` and `provenance_signals_written_to_vector` event types are emitted.
4. **Fallback defaults are conservative.** `source_diversity = 0.0` on broken chain, not `1.0`. This is the right epistemic call: absence of evidence is not evidence of diversity. The spec calls it out explicitly in §4. Reading the code, the implementation matches.
5. **Replay signature now hashes decision payload.** `src/implicit_memory/replay.py::_DECISION_KEYS` contains the load-bearing fields; the SHA-256 is computed over a sorted, separator-tight JSON of the decision records. This directly addresses the 2026-05-12 dissent that the prior signature hashed event IDs.
6. **Observer hook with reentrancy guard.** `set_eligibility_observer` plus `_in_observer` in `eligibility.py` lets the Q traffic-evidence harness recompute alternate-mode decisions without polluting the sample. The reentrancy guard is the kind of detail that gets skipped under deadline; it didn't get skipped here.
7. **The closeout snapshot lives in lineage.** `im_s_provenance_writer_closeout` emits a `snapshotted` event with `completed[]` and `deferred[]` arrays. The deferred item (cross-memory parent walk) is explicit and reachable by replay. This is what "no implicit decision is silent" looks like applied to the lab's own process.

## What I still see as soft

Honest list. Not a defect list — candidates for the next plan.

1. **Two of three axes still don't read real signals.** `confidence_in_provenance_chain` now reads `compute_chain_signals`. `confidence_in_claim` and `confidence_in_recall_process` still derive from whatever the observation provider hands in. The mapping in `score_triple` is fine, but the inputs are not lineage-grounded the way provenance now is. There is no `compute_claim_signals` analogue. Until there is, the axis-aware gate is partially axis-aware.
2. `**computed_at` defaults to wall-clock.** `compute_chain_signals` defaults `computed_at = datetime.utcnow().isoformat()` when not supplied, and `_resolve_provenance` doesn't supply it — it only forwards `as_of_time`. So two replays at different real-world times will emit different `computed_at` values in the `provenance_signals_computed` event payload. The decision signature in `replay.py` doesn't include `computed_at` in `_DECISION_KEYS`, so the signature stays stable, but the events themselves diverge. The spec §5 says "any computation that depends on non-lineage mutable state must be marked with deterministic fallback + reason and must not silently alter decision payloads." Wall-clock `computed_at` is non-lineage mutable state, and the payload changes. I would plumb `computed_at = t.isoformat()` from the loop tick and stop using `utcnow()` as a default.
3. **The `implicit_admitted` event reconstructs `provenance_signals` from `gate_inputs`, not from the resolver payload.** `_admit_and_gate` builds `provenance_signals` as a fresh dict of `{parent_chain_depth, source_diversity, age_of_original_source}`, dropping `fallback_reason` and `provenance_signal_source`. Those markers do live on the separate `provenance_signals_computed` event, so an auditor can join on `memory_id` + tick boundary to recover them — but spec §4 ("audit queries must count fallback-derived provenance separately") is easier to honor if the markers ride along on the admission event itself. This is a five-line fix.
4. **The static stubs are still stubs.** `StaticObservationProvider` and `StaticCueProvider` in `run_loop.py` are unchanged. The EventBridge bus + SQS FIFO + DLQ exist in `memory_lab_stack.py` but nothing in the loop pulls from them. The primer's §15 open-edges list still applies verbatim. Real production traffic flowing through the gate would test things synthetic Q-style observation can't.
5. **Half the lab still runs scalar eligibility.** The explicit experiments (`e1..e12`) call `score_candidate`. The three-axis rollout is on the implicit gate path. The three-axis spec §9 explicitly allows retaining `score_candidate` for v1 migration; this is not a violation. But it does mean the axis-aware machinery is exercised on roughly half the experimental surface.

## On same-substrate confirmation

The 2026-05-12 dissent entry, written by Opus 4.7, called out that same-substrate confirmation is weak. I am also Opus 4.7. The above rating-bump is generous; I am the wrong agent to make it stick. A cross-substrate read (gpt-5.x, or a Sonnet) on the gate + replay + provenance code, with the explicit task of finding what I missed, would be more load-bearing than this entry. The 2026-05-11 codex reaction was reaction-to-proposal; what's missing is a codex reaction-to-implementation.

## Net

The lab moved from "control system without epistemics" to "control system with axis-aware epistemics, one of three axes lineage-grounded." That is real progress over two calendar days, and the meta-process behind it — append-only agent-pov, dissent preserved, codex reaction kept on record, deferred items emitted as lineage — is itself a working demo of the system's own theory.

The next epistemic frontier is the claim axis: until `confidence_in_claim` reads something like an evidence-anchored signal rather than a provider-supplied scalar, two-thirds of the triple is still trust-as-prior rather than trust-as-derivation.