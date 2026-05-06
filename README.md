# Memory

An experimental **memory lab**—not a production memory product. The goal is to probe how synthetic memory behaves when it must **form and revise beliefs**, not merely **retrieve** text in plausible order.

## Core thesis

Memory is not storage. It is a **control system**: past signals gate how strongly they may influence future computation.

## Architecture: two planes

| Plane | Nature | Role |
|--------|--------|------|
| **Cognitive memory** | Mutable, lossy, reconstructive | Encode, retrieve, reconsolidate, decay, promote (episodic → semantic), suppress, generalize |
| **Audit lineage** | Immutable, append-only, replayable | Provenance and full replay; never mutate or silently delete (tombstones only) |

**Invariant:** cognition may mutate; lineage must not.

A memory record is richer than content: claim, source, assertion/event time, confidence, trust, support, conflicts, decay state, last recall, and mutation history.

## What gets built

1. **Append-only event log** — observed, recalled, mutated, promoted, contradicted, quarantined, deleted, compacted (and related).
2. **Materialized memory state** — embeddings, summaries, beliefs, scores, decay, conflict links.
3. **Eligibility engine** — memory does not influence output unless eligible:

   `eligibility = relevance × trust × recency × reinforcement × consistency × safety`

4. **Time engine** — continuous decay and reinforcement (not naive TTL expiry); episodic traces compress toward schemas/beliefs over time.
5. **Conflict engine** — contradictions are first-class; **do not auto-resolve**; reason over disagreement.
6. **Sleep worker** — offline replay, dedupe, compression, semantic promotion, decay, quarantine of contradictions.
7. **Poisoning harness** — treat memory as adversarial; distinguish damaged (missing) from poisoned (coherent-but-false); track spread and quarantine before promotion where appropriate.
8. **Audit API** — answer: *What does it believe now? Why? What did it believe before? What changed it? What was absent?*

## Stack (target)

- **Hot path**
  - **S3 Vectors** — similarity search with retrieval-side metadata filters
  - **S3 objects** — append-only event lineage, materialized memory state, snapshots, manifests
- **Cold / analytic path**
  - **Athena** — replay checks, drift analysis, poisoning spread, decay curves
  - **Glue Data Catalog** — schemas and table metadata
  - **Parquet tables** — compacted event/state history
- **DynamoDB** (optional) — add only if point lookup or query pain appears
- **Python** — API + background workers

Compaction flow: `events/raw/.../*.json -> events/parquet/dt=YYYY-MM-DD/hour=HH/*.parquet -> Athena`

Storage invariant: raw S3 event objects are the source of truth. Memory-state objects and vector records are rebuildable caches. Athena reads compacted parquet, not tiny raw JSON event objects.

Storage boundary rule: keep the S3 Vectors bucket/index retrieval-only. Keep compacted parquet in separate analytics storage (bucket or tightly isolated analytics prefix), not in the vector bucket.

Hard rule: vectors may influence recall; event/parquet lineage must explain recall.

Traceability invariants:
1. Every vector maps to a source event object identity or source payload hash.
2. Every Parquet row is traceable to raw event identity.
3. Vector indexes can be deleted and rebuilt from durable event/parquet data.

## Experiments

| ID | Focus |
|----|--------|
| E1 | Trust vs truth (e.g. low-trust true vs high-trust false) |
| E2 | Reconsolidation drift under repeated / shifting recall |
| E3 | Spaced reinforcement vs single strong write |
| E4 | Conflict persistence without collapse |
| E5 | Episodic → semantic promotion |
| E6 | Poisoning and spread / quarantine |
| E7 | Audit replay—rebuild state from the log exactly |

## Success criteria

The system should demonstrate **belief change driven by experience** (trust, time, conflict, sleep), **not** output that only tracks retrieval order.

Concrete checks (v0):

1. Distinguish belief formation from mere retrieval ordering.
2. Conflicts persist without forcing a single “winner.”
3. Poisoned memory can be quarantined.
4. Replay from the event log reconstructs state.
5. Promotion yields stable abstractions when criteria are met.

## Non-goals (v0)

Distributed scale, real-time throughput as a primary concern, perfect truth inference, or full ontology-style reasoning.

## Docs in this repo

- [`AGENTS.md`](AGENTS.md) — operating rules and architecture guardrails for coding agents
- [`notes/AMENDED_NOTES.md`](notes/AMENDED_NOTES.md) — conceptual model, lifecycle, poisoning, biological parallels
- [`specs/BROAD_EXPERIMENT_SPEC.md`](specs/BROAD_EXPERIMENT_SPEC.md) — lab scope, modules, acceptance framing
- [`specs/ENGINEERING_SPEC.md`](specs/ENGINEERING_SPEC.md) — S3-first backend, components, audit endpoints, metrics
- [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) — API routes, payloads, and error envelope
- [`infra/README.md`](infra/README.md) — CDK bootstrap/synth/deploy/destroy workflow
- [`plans/`](plans/) — canonical archive of project plans (sequentially numbered with original filenames)

## Environment configuration

The project supports `.env`-based configuration for AWS/runtime settings.

1. Copy `.env.example` to `.env`
2. Set values such as:
   - `AWS_PROFILE`
   - `AWS_VECTOR_BUCKET_NAME`
   - `AWS_VECTOR_INDEX_NAME`
   - `AWS_EVENTS_BUCKET_NAME`
   - `AWS_STATE_BUCKET_NAME`
   - `AWS_ANALYTICS_BUCKET_NAME`
   - `MEMORY_ROOT`

`.env` values are loaded at startup and act as defaults; existing shell environment variables still win unless explicitly overridden.

## Infrastructure workflow

Use helper scripts:

- `scripts/cdk.sh synth`
- `scripts/cdk.sh deploy`
- `scripts/cdk.sh destroy`
- `scripts/infra_smoke.sh`

Use AWS profile `stack-research` (default in scripts).

## Guiding principle

Use biological ideas for **adaptive** behavior; use machines for **auditability**. Do not conflate the two.
