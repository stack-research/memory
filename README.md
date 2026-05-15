# Memory Lab

A small AWS-native memory lab where cognitive memory can mutate and lineage is immutable, append-only, and replayable.

Behavior is a moving target. History is not.

## Start here

If you are an agent or a human new to this repo, read [`specs/AGENT_PRIMER.md`](specs/AGENT_PRIMER.md). That is enough to start.

After the primer, the only other required reading is [`AGENTS.md`](AGENTS.md). Deeper specs and notes are on the primer's deep-dive list and should be opened only when the task asks for them.

## Repo layout

- [`stacks/`](stacks/) — AWS CDK infra (S3 Tables, S3 Vectors, ingress bucket, Athena, EventBridge, SQS). See [`stacks/README.md`](stacks/README.md).
- [`src/`](src/) — engine (`lineage_engine`, `storage`), explicit memory, implicit memory, ingestion, experiments, `epistemic_triangle` (v7 record/assertion taxonomy), `heliotime` + `timekeeping` (TAI capture and `physical_moment` construction).
- [`specs/`](specs/) — load-bearing contracts. Start with `AGENT_PRIMER.md`.
- [`notes/`](notes/) — theory and design pivots. Not contracts.

## Non-negotiable invariants

1. Memory behavior can change; lineage history must not be rewritten.
2. S3 Tables is canonical lineage. The active table is named by `AWS_ATHENA_TARGET_TABLE_FQN` in `.env` (and the current `schema_version` lives in `src/types.py::EVENT_SCHEMA_VERSION`). Earlier-epoch tables are historical containers; no new writes. Do not hardcode the version in docs — see `AGENTS.md` § Documentation conventions.
3. S3 Vectors is a rebuildable recall index, not source of truth.
4. Do not auto-resolve contradictions.
5. No implicit decision is silent: every trigger evaluation emits an event.

## Quick start

Requirements: `uv`, AWS profile `stack-research`, `AWS_REGION` set, `.env` populated (see [`.env.example`](.env.example)).

Synth and deploy infra:

```bash
make synth
make deploy
```

Run the implicit regression suite:

```bash
make implicit-regression
```

Run a single explicit experiment (`e1..e12`):

```bash
make exp-e1
```

Run a single implicit loop tick (no Makefile target):

```bash
PYTHONPATH=. uv run --project stacks python -m src.implicit_memory.run_loop
```

Run any experiment by name (`e1..e12`, `im-a..im-u`, `im-aws`, `im-regression`):

```bash
PYTHONPATH=. uv run --project stacks python -m src.run_experiment <name>
```

Athena ingestion (raw to canonical):

```bash
make ingest
```

See the [`Makefile`](Makefile) for the full list of targets.

## Where to read next

- [`specs/AGENT_PRIMER.md`](specs/AGENT_PRIMER.md) — what this system is, in one file.
- [`AGENTS.md`](AGENTS.md) — rules for coding agents.

Anything else is on the primer's deep-dive list.
