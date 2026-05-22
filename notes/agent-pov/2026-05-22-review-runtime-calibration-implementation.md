```
agent: claude-opus-4.7
date: 2026-05-22
prompt: "Ready for your review: Implemented and verified RUNTIME_CALIBRATION.md as im-w."
kind: reaction
cites:
  - specs/RUNTIME_CALIBRATION.md
  - 2026-05-22-runtime-calibration-implementation-close
  - 2026-05-22-review-runtime-calibration
  - 2026-05-22-build-not-overengineer
```

# Review of the im_w runtime calibration implementation

Reviewed the implementation against the spec. The run is real and the headline results hold, but I found one clear defect and two disclosure problems that affect what the numbers mean. Verdict: **not ready to call the calibration trustworthy as reported** — re-run needed after fixes.

## Significant

**1. Adversarial cues are 100% concentrated on the `repetition` cue_type** — `src/experiments/implicit/im_w_runtime_calibration.py:239-247`

`adversarial_class = adversarial[cursor] if cursor < len(adversarial) else None` assigns the 125 adversarial labels by flat `cursor` order. `WORKLOAD_COUNTS` iterates `repetition` first with exactly 125 entries — so cursor 0–124 *are* the 125 `repetition` cues. Result: every adversarial cue is a `repetition` cue, and every `repetition` cue is adversarial. `safety_anomaly` and `sensor_disagreement` receive zero adversarial traffic.

This violates §10.2, which the spec made a **binding pre-implementation gate**, and contradicts its own example ("a spoofed-urgency cue is still a `safety_anomaly` or `sensor_disagreement`"). It also inverts the representativeness rationale: `repetition` was meant to be the routine low-significance bulk and now has no benign members. The attack-surface paths through reflex/safety triggers are systematically under-exercised. `_validate_generation` (`im_w_runtime_calibration.py:490`) passes because it only checks adversarial *totals*, never cross-cue_type spread. **Fix:** distribute adversarial classes across cue_types and add a distribution assertion to `_validate_generation`.

**2. `CalibrationSeenCueStore` quietly replaces lineage-backed dedup — and the `25 duplicate ignored` metric does not mean what it appears to** — `src/experiments/implicit/im_w_runtime_calibration.py:114-138`

For every generated cue_id, `has_seen` consults an in-memory `_seen_generated` set, not canonical lineage. So the 25 duplicate probes — which §11 deliberately gave changed bodies *specifically to defeat SQS content-dedup and force lineage-backed dedup to do the work* — are actually caught by a run-local cache. The docstring's stated reason ("throughput") understates it: `LineageBackedSeenCueStore.has_seen` queries *canonical* lineage, which lags S3 ingress within a fast run (the ingress-before-canonical window named in `CONTROL_PLANE_INGEST` §10). So lineage-backed dedup genuinely *can't* catch in-run duplicates here — that is a real finding the calibration was positioned to surface, and it's buried in a docstring instead of the Run Summary. As written, "25 duplicate ignored / 0 rejected" reads as "production dedup works at scale" when it tested a fixture. **Fix:** either run with `LineageBackedSeenCueStore` and report the (likely ugly) result honestly per Decision 4, or keep the cache but disclose the substitution and its cause prominently in the Run Summary.

**3. The provenance axis is pinned to `computed` by fixture** — `src/experiments/implicit/im_w_runtime_calibration.py:95-111`

`StaticProvenanceResolver` always returns `provenance_signal_source: "computed"`, `fallback_reason: None`. Decision 3 / §4 — the audience-agent criterion — is supposed to *measure* whether behavior-influencing decisions ran on `computed` vs `fallback` signals. For the provenance axis that measurement is now a foregone conclusion: `signal_source_distribution["provenance"]` and the `all_axes_computed_fraction` are partly predetermined. Same root cause as Finding 2 (a real `LineageProvenanceResolver` would hit lagging canonical lineage). Claim/recall axes still go through real signal-writer code paths, so those are genuine — but the run summary should state plainly that the provenance axis was fixture-supplied and is not a measurement.

The thread tying 2 and 3 together: the canonical-lag window forced fixtures in place of the two production mechanisms this calibration most wanted to exercise. That's a legitimate finding — but the Run Summary presents fixture output as production-path output.

## Minor

- **Replay equivalence is weaker than the labels suggest.** Both the "live" and "replay" loop runs consume the identical `captured_events` list via `ReplayCueProvider` (`im_w_runtime_calibration.py:618-640`). This tests loop determinism across two engine backends, not live-bus-vs-replay — there is no live-bus loop run in this batch design. `CONTROL_PLANE_INGEST` suite V already covers the genuine property; `live_signature`/`replay_signature` here oversell it. Decision 5's "identical to the live run's" presumes a live loop run that doesn't exist.
- The two loop runs use asymmetric engines (real `LineageEngine` vs `InMemoryLineageEngine`) — works only because `decision_signature` excludes engine-divergent fields; mild latent fragility.

## What's correct

- §10.3 regression gate is right: `w = run_w() if os.environ.get("IMPLICIT_CALIBRATION_RUN") == "1" else None`, `w_skipped` reported, `runtime_calibration_suite_pass` defaults `True` when skipped.
- The `routed_away` / `transient` drain categories are faithful refinements of `CONTROL_PLANE_INGEST` §6's scope-failure split — not scope creep.
- `RecordingLineage` records *after* `inner.emit` returns, i.e. after the durability boundary; it's an analysis buffer, not a competing source of truth.
- Preflight refuses a non-empty FIFO queue; `cue_payload_fixture_shape` is disclosed; phase timing + `failure_stage` present.

## Recommendation

Decision 4's pass bar was met (replay held, no silent loss, metrics produced) — but §10.2 representativeness was violated and two headline metrics overstate what was measured. I'd treat this as **findings to surface, then re-run**: fix the adversarial distribution (Finding 1), and for Findings 2–3 either measure the real paths or disclose the fixture substitution and its canonical-lag cause in the Run Summary. The canonical-lag discovery is genuinely valuable — it shouldn't be muffled. This is consistent with the spec's own "ugly results are findings, not failures" ethos; the problem isn't ugly results, it's fixture results presented as production results.

I haven't changed any code — this is review only.
