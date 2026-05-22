```yaml
agent: openai-gpt-5-codex
date: 2026-05-22
prompt: "PLEASE IMPLEMENT THIS PLAN: Runtime Calibration Implementation Plan"
kind: closing
cites:
  - specs/RUNTIME_CALIBRATION.md
  - 2026-05-22-review-runtime-calibration
  - 2026-05-22-reaction-to-build-not-overengineer
  - 2026-05-22-codex-open-edges-next-steps
```

# Runtime calibration implementation close

Implemented and verified `RUNTIME_CALIBRATION.md` as `im-w`.

Changed:

- `specs/RUNTIME_CALIBRATION.md`: pinned 500-cue workload, adversarial split, and 25 duplicate submissions.
- `src/experiments/implicit/im_w_runtime_calibration.py`: live EventBridge producer, guarded SQS drain, lineage capture, loop/replay comparison, S3-required Run Summary artifact, snapshot event.
- `src/run_experiment.py`: registered `im-w`.
- `Makefile`: added `make im-v` and `make im-w`.
- `src/experiments/implicit/im_regression.py`: optional `IMPLICIT_CALIBRATION_RUN=1`; default regression skips W.

Live `make im-w` passed after the SSO refresh:

- EventBridge submitted `525/525`, failed `0`
- SQS outcomes: `500` ingested, `25` duplicate ignored, `0` rejected/transient/malformed/routed-away
- Replay equivalent: `true`
- Final artifact: `s3://memory-lab-research-artifacts/implicit/im-w-runtime-calibration-summary-20260522T153525Z.json`
- Read-back confirmed artifact contains its own URI, `artifact_write: 1.359`, `pass: true`, `failure_stage: null`
- Final queue check: `0` visible, `0` not visible, `0` delayed

Verification:

- Pure generation check passed exact 500/125/25 counts.
- `make im-v` passed `5/5`.
- `make implicit-regression` passed and confirmed `w_skipped: True` by default.
- During the first interrupted live attempts, I cleaned up only owned `im-w-runtime-calibration` SQS residue before rerunning.

## Implementation note

The useful result is not just that `im-w` passes. It is that the lab now has a measured bridge from the control-plane wire into the epistemic surface without changing loop behavior. The run produced the kind of ugly-but-actionable measurements the prior reviews asked for: behavior-influencing decisions had provenance computed but claim and recall sources still fallback, and the dominant axis collapsed to `provenance_chain` for triple-bearing decisions. That is not a reason to add another spec. It is the next build target.

The calibration also exposed real operational texture: EventBridge was fast, SQS ingestion plus durable lineage writes took minutes, and the live loop's S3-emitting section dominated runtime. Those timings belong in the artifact because they keep the group honest about what the current lab can actually run.

My opinion after implementing it: this is good enough for now. Do not turn `im-w` into a platform. Use it as the standing measurement run while replacing fallback-heavy signal paths with lineage-backed claim and recall signals. Keep the default regression fast, keep the live calibration opt-in, and let the next concrete run decide whether payload shape, dedup index, or runtime throughput deserves work first.
