# Implicit Memory

This module implements governed implicit memory control: automatic trigger evaluation, admission, eligibility gating, bounded reflex execution, contamination handling, policy mutation, and lineage-first auditability.

## What it does

- Evaluates trigger actions: `invoke_encode | invoke_recall | reflex_execute | defer | no_op`
- Applies significance-triggered admission
- Applies eligibility-gated influence decisions
- Runs bounded reflex mode with cooldown and forced governed re-entry
- Detects contamination/attack signals (split reality, urgency spoof, sensory-confidence spoof, event flood)
- Emits deterministic, machine-readable reason codes
- Emits append-only lineage events for all decisions
- Supports runtime policy mutation events:
  - `policy_threshold_updated`
  - `policy_procedure_superseded`
- Emits per-tick operational metrics snapshots

## Key files

- `trigger_policy.py` — trigger scoring and action selection
- `controller.py` — observation processing and trigger event emission
- `loop.py` — integrated operational loop (observation + scheduled cues)
- `admission.py` — admission scoring
- `eligibility.py` — eligibility gating
- `reflex_mode.py` — bounded reflex controller
- `contamination.py` — contamination/split-reality helpers
- `reasons.py` — deterministic reason taxonomy
- `policy_mutation.py` — threshold/procedure mutation primitives
- `procedure_lifecycle.py` — reinforcement/decay/trust decay
- `procedure_state_store.py` — in-memory/S3 procedure state persistence
- `provenance_resolver.py` — resolves `confidence_in_provenance_chain` from emitted provenance signals (per `specs/PROVENANCE_SIGNAL_WRITER.md`)
- `lineage_events.py` — helpers for constructing implicit-side lineage events
- `scheduler.py` — scheduled cue handling
- `replay.py` — lineage replay summary reconstruction (`rebuild_from_lineage`, `ReplayCueProvider`)
- `cue_ingest.py` — control-plane cue ingestion (`CueIngestionConsumer`, capture-before-act, lineage-backed dedup; per `specs/CONTROL_PLANE_INGEST.md`)
- `run_cue_ingest.py` — the SQS consumer command that drains `memory-lab.fifo` into `CueIngestionConsumer`
- `run_loop.py` — runnable loop entrypoint
- `settings.py` — implicit-loop runtime settings

## Invariants

- Cognitive behavior may mutate; lineage is immutable and append-only.
- No implicit decision is silent.
- Contradictions persist unless explicitly superseded by policy/event lineage.

## Running

From repo root (using `uv`):

- `PYTHONPATH=. uv run --project stacks python -m src.implicit_memory.run_loop`
- `PYTHONPATH=. uv run --project stacks python -m src.experiments.implicit.im_regression`
- `PYTHONPATH=. uv run --project stacks python -m src.experiments.implicit.im_matrix_runner`

## Related specs

- `specs/IMPLICIT_MEMORY_SPEC.md` — governed/reflex contract, trigger/admission/eligibility/contamination logic.
- `specs/IMPLICIT_MEMORY_TEST_SPEC.md` — the `im_*` suite test surface.
- `specs/CONTROL_PLANE_INGEST.md` — EventBridge → SQS → consumer contract; what `cue_ingest.py` and `run_cue_ingest.py` implement.
- `specs/EPISTEMIC_TRIANGLE.md` — `record_kind` / `assertion_kind` envelope and three-axis signal taxonomy that decisions emitted from this module must carry.
- `specs/THREE_AXIS_UNCERTAINTY.md` — axis-aware gating direction; relevant to `eligibility.py` and the policy-mutation paths.
- `specs/PROVENANCE_SIGNAL_WRITER.md` — provenance signal production consumed by `provenance_resolver.py`.
- `specs/CONSEQUENCE_LOOPS.md` — run-to-run learning. The first two summary-to-summary bindings live in `src/experiments/implicit/im_w_runtime_calibration.py`, but the procedural-memory framing belongs to this module's territory.
