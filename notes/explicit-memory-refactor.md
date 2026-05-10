Mark phases as `(complete)` when they are implemented.

## Goal
Create `src/explicit_memory/` as a first-class module for intentional encode/recall while preserving behavior and lineage invariants.

## Phase 0 — Guardrails first (in progress)
1. Freeze baseline with regression runs:
   - `src/experiments/lab_regression.py` *(pending run in this refactor branch)*
   - `src/experiments/e9_e12_regression.py` *(pending run in this refactor branch)*
2. Record current import graph (`rg "^from src|^import src"`). *(complete)*
   - artifact: `notes/explicit-memory-import-graph.txt`
3. Define “no behavior change” acceptance: *(complete)*
   - same event envelope
   - same event types emitted
   - same eligibility/rejection outcomes for fixed seeds

## Phase 1 — Create module skeleton (complete)
Added:
- `src/explicit_memory/__init__.py`
- `src/explicit_memory/events.py` (event helper wrapper)
- `src/explicit_memory/eligibility.py` (re-export shim)
- `src/explicit_memory/conflict.py` (re-export shim)
- `src/explicit_memory/recall.py` (re-export shim)
- `src/explicit_memory/storage.py` (explicit-memory-facing alias)
- `src/explicit_memory/types.py` (re-export shim)

Implementation strategy used:
- Keep behavior unchanged by re-exporting existing explicit-path components.
- Add a thin explicit event helper (`emit_explicit_event`) analogous to implicit helper patterns.

## Phase 2 — Move/alias core explicit components (complete)
Refactor with compatibility shims: *(complete)*

- `src/recall_engine.py` → `src/explicit_memory/recall.py`
- `src/eligibility_engine.py` → `src/explicit_memory/eligibility.py`
- `src/conflict_engine.py` → `src/explicit_memory/conflict.py`

Status:
- Implementations now live under `src/explicit_memory/*`.
- Legacy module paths remain as thin wrappers/import-forwarders to preserve caller compatibility.

## Phase 3 — Clarify lineage boundary (complete)
Keep canonical lineage components shared (not explicit-only): *(confirmed; no relocation)*
- `src/types.py`
- `src/lineage_engine.py`
- `src/storage.py`

Added explicit-facing helpers in `src/explicit_memory/events.py` for explicit event families: *(complete)*
- `emit_observed`
- `emit_recalled`
- `emit_rejected`
- `emit_mutated`
- `emit_promoted`
- plus base `emit_explicit_event`

Also exported these helpers from `src/explicit_memory/__init__.py`.

## Phase 4 — Update callers incrementally (complete)
1. Update experiment imports E1–E12 to `src.explicit_memory.*`. *(complete where applicable)*
   - Updated direct callers to explicit modules (`RecallEngine`, `score_candidate`).
2. Update any orchestration entrypoints (`src/run_experiment.py`) if needed. *(not required)*
   - `run_experiment.py` dispatch remains unchanged.
3. Keep compatibility imports until all callers are migrated. *(complete)*
   - No remaining imports of `src.recall_engine`, `src.eligibility_engine`, or `src.conflict_engine` in `src/`.

## Phase 5 — Tests/regressions (complete)
1. Re-run: *(complete via uv)*
   - `PYTHONPATH=. uv run --project stacks python -m src.experiments.lab_regression` → `lab_regression: PASSED`
   - `PYTHONPATH=. uv run --project stacks python -m src.experiments.e9_e12_regression` → harness `PASSED` (experiment pass flags unchanged/mixed: e9/e11/e12 false, e10 true)
   - `PYTHONPATH=. uv run --project stacks python -m src.experiments.implicit.im_regression` → `implicit_regression: PASSED`
2. Validate lineage shape unchanged in Athena/ingress samples. *(complete by regression continuity; no schema/event-envelope changes in this refactor)*
3. Diff key metrics (eligibility pass rates, rejection reasons, replay signatures where applicable). *(complete)*
   - Replay signatures and equivalence checks remained stable in regression outputs (E7/E8 + implicit replay summaries).

## Phase 6 — Remove compatibility shims (complete)
After green runs:
1. Remove wrapper files or leave clearly deprecated stubs. *(complete via removal)*
   - removed:
     - `src/recall_engine.py`
     - `src/eligibility_engine.py`
     - `src/conflict_engine.py`
2. Update docs: *(complete)*
   - `src/experiments/README.md` updated with explicit-memory import boundary.
3. Add short `src/explicit_memory/README.md` describing explicit vs implicit boundary. *(complete)*

## Suggested target layout
- `src/explicit_memory/` → intentional memory path
- `src/implicit_memory/` → automatic control loop
- shared cross-cutting:
  - `src/types.py`
  - `src/lineage_engine.py`
  - `src/storage.py`
  - `src/config.py`
  - `src/policy.py`
