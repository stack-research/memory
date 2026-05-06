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
6. **Sleep engine** — periodic replay, dedupe, compression, semantic promotion, decay, quarantine of contradictions.
7. **Poisoning harness** — treat memory as adversarial; distinguish damaged (missing) from poisoned (coherent-but-false); track spread and quarantine before promotion where appropriate.
8. **Audit engine** — answer: *What does it believe now? Why? What did it believe before? What changed it? What was absent?*

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

- Distributed scale
- real-time throughput as a primary concern
- perfect truth inference
- or full ontology-style reasoning.

## Docs in this repo

- [`AGENTS.md`](AGENTS.md) — operating rules and architecture guardrails for coding agents
- [`notes/AMENDED_NOTES.md`](notes/AMENDED_NOTES.md) — conceptual model, lifecycle, poisoning, biological parallels
- [`specs/BROAD_EXPERIMENT_SPEC.md`](specs/BROAD_EXPERIMENT_SPEC.md) — lab scope, modules, acceptance framing
- [`specs/ENGINEERING_SPEC.md`](specs/ENGINEERING_SPEC.md) — S3 backend, components, audit endpoints, metrics
- [`src/experiments/README.md`](src/experiments/README.md) — runnable experiment index and instructions
- [`src/ingestion/athena_ingestion.py`](src/ingestion/athena_ingestion.py) — Athena SQL ingestion from S3 ingress into canonical lineage tables

## Current ingestion note (v0 lab)

For fast iteration, lineage writes currently flow as:

1. engine emits append-only JSON events to S3 ingress
2. Athena job triages raw vs quarantine
3. Athena writes validated rows to a canonical query table (`memory_lab.lineage_events_canonical` by default)

This keeps the lineage envelope stable while we iterate on tighter S3 Tables canonical write integration.

## Guiding principle

Use biological ideas for **adaptive** behavior; use machines for **auditability**. Do not conflate the two.
