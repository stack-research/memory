# Experiments

This directory contains runnable memory-lab experiments from `specs/EXPERIMENTS.md`.

## Run experiments

From `stacks/`:

- `PYTHONPATH=.. uv run python -m src.run_experiment e1`

Required environment comes from project root `.env` / `.env.local` (loaded by the stack tooling) and standard shell env for experiment runs.

## Experiments

### E1 - Trusted False Source vs Weak True Source

File: `e1_trusted_false_vs_weak_true.py`

Purpose:
- Compare a high-trust false claim against a lower-trust true claim.
- Exercise retrieval + eligibility scoring + lineage event emission.

Current behavior:
- Embeds both claims with Bedrock.
- Writes vectors to S3 Vectors index.
- Emits `observed` lineage events.
- Runs recall query and emits `recalled` or `rejected` events.

Notes:
- Lineage events are currently written as append-only JSON ingress objects in S3.
- We will add more experiments here as they are implemented.
