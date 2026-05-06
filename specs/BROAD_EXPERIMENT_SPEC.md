Project goal: build a small agent memory lab, not a production memory system.

Core modules:

1. Append-only event log
    Events: observed, recalled, mutated, promoted, contradicted, quarantined, deleted, compacted.
2. Materialized memory state
    Current beliefs, summaries, embeddings, confidence, trust, decay, conflict links.
3. Eligibility engine
    Decides whether a memory may influence an output.

eligibility = relevance * trust * recency * reinforcement * consistency * safety

4. Time engine
    Continuous decay, reinforcement, promotion, and pruning.
5. Conflict engine
    Store contradictions as first-class objects. Do not auto-resolve.
6. Sleep worker
    Offline pass for replay, compaction, semantic promotion, dedupe, decay, quarantine.
7. Poisoning harness
    Inject trusted-but-false facts and track spread.
8. Audit API
    Answer:

What did the agent believe at time T?
Why?
What changed it?
What was absent?

Architecture split for experiments:

- Hot path:
  - S3 Vectors for similarity retrieval
  - S3 event objects (append-only lineage)
  - S3 memory-state objects (materialized beliefs)
- Cold / analytic path:
  - Athena for replay checks, drift analysis, poisoning spread, and decay curves
  - Glue Data Catalog for schemas
  - Parquet tables from compacted history

Compaction flow:
`events/raw/.../*.json` -> `events/parquet/dt=YYYY-MM-DD/hour=HH/*.parquet` -> Athena

Hard rule:
Vectors may influence recall.
Parquet/event lineage must explain recall.

Invariants to prove in experiments:
1. Every vector maps to a source event object identity or source payload hash.
2. Every Parquet row is traceable to raw event identity.
3. Vector indexes can be deleted and rebuilt from durable event/parquet data.

First experiments:

E1: trusted false source vs weaker true source
E2: repeated recall causing drift
E3: spaced reinforcement vs single strong write
E4: conflict persistence under retrieval
E5: sleep-worker promotion from episodes to semantic claims
E6: audit replay rebuilds state exactly
E7: poisoned memory gets quarantined before promotion

Acceptance test for the whole repo:

The system must show whether it changes belief, not merely retrieval order.
