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
- `scheduler.py` — scheduled cue handling
- `replay.py` — lineage replay summary reconstruction
- `run_loop.py` — runnable loop entrypoint

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

- `specs/IMPLICIT_MEMORY_SPEC.md`
- `specs/IMPLICIT_MEMORY_TEST_SPEC.md`
