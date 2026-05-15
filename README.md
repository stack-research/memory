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

## Timekeeping kernel (`src/heliotime`, `src/timekeeping`)

Most systems treat a UTC wall-clock string as "the time." This lab treats UTC as a civil convention layered on a more durable substrate: **TAI** (uninterrupted SI seconds, no leap seconds) for the physical mechanism, and **heliocentric ecliptic coordinates** (solar age in megayears plus Earth's heliocentric longitude in degrees) for an observer-independent coordinate frame. Together they give every lineage event a `physical_moment` block that is byte-identical on replay and meaningful well beyond civil calendar conventions — neither property holds for UTC.

[`src/heliotime`](src/heliotime/) is the kernel: pure functions from an explicit input moment (`datetime`, ISO string, or `astropy.time.Time`) to a `PhysicalMoment` (`tai_iso`, `solar_age_myr`, `ecliptic_lon_deg`). The only wall-clock read in the whole repo is `heliotime.now()` — named that way so replay paths can never accidentally call it. `astropy` is the only dependency.

[`src/timekeeping`](src/timekeeping/) layers the rest of the v7 envelope on top:

- [`context.py`](src/timekeeping/context.py) — `TimeContext` and a deterministic `time_context_id` (SHA-256 of a canonical-JSON serialization of the content fields; idempotent re-declaration).
- [`hlc.py`](src/timekeeping/hlc.py) — Kulkarni-2014 hybrid logical clock keyed off `physical_moment.tai_iso`. Replay-deterministic by construction.
- [`batch.py`](src/timekeeping/batch.py) — `canonical_batch_committed` markers that resolve "same atomic batch" without relying on wall-clock proximity.
- [`events.py`](src/timekeeping/events.py) — payload builders for `time_context_declared`, `canonical_table_genesis`, and `canonical_table_boundary`.

### Why this is interesting outside this lab

The kernel is intentionally self-contained. `heliotime` depends only on `astropy`; `timekeeping` depends on `heliotime` and the Python standard library. Neither imports from `src/lineage_engine`, `src/storage`, or anything AWS-shaped. The conceptual move — *do not let civil-calendar conventions or wall-clock reads leak into the data plane of a system whose correctness depends on replay determinism* — generalizes to log pipelines, event-sourced systems, distributed databases, simulation harnesses, and any append-only ledger.

There is a credible **side-project / standalone Python package** here (working name: `heliotime`). The migration path is intentionally cheap: pull `src/heliotime/` and `src/timekeeping/` out as their own package, publish to PyPI, add the dependency to `pyproject.toml`, delete the in-tree copy. The spec lives in [`specs/TAI_TIMEKEEPING.md`](specs/TAI_TIMEKEEPING.md); the seed motivation is in [`notes/solar_time/`](notes/solar_time/).

## Where to read next

- [`specs/AGENT_PRIMER.md`](specs/AGENT_PRIMER.md) — what this system is, in one file.
- [`AGENTS.md`](AGENTS.md) — rules for coding agents.

Anything else is on the primer's deep-dive list.
