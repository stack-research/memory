# Experiments

This directory contains runnable memory-lab experiments from `specs/EXPERIMENTS.md`.

## Run experiments

From `stacks/`:

- `PYTHONPATH=.. uv run python -m src.run_experiment e1`
- `PYTHONPATH=.. uv run python -m src.run_experiment e2`
- `PYTHONPATH=.. uv run python -m src.run_experiment e3`
- `PYTHONPATH=.. uv run python -m src.run_experiment e4`
- `PYTHONPATH=.. uv run python -m src.run_experiment e5`
- `PYTHONPATH=.. uv run python -m src.run_experiment e6`
- `PYTHONPATH=.. uv run python -m src.run_experiment e7`
- `PYTHONPATH=.. uv run python -m src.run_experiment e8`
- `PYTHONPATH=.. uv run python -m src.experiments.lab_regression`

Required environment comes from project root `.env` / `.env.local` (loaded by the stack tooling) and standard shell env for experiment runs.

Lineage replay readers are selected with `AWS_LINEAGE_READER_BACKEND`:
- `s3tables` (default)
- `athena` (compatibility path)

Retrieval/quarantine policy is selected via env (`MEMORY_RETRIEVAL_POLICY_*`, `MEMORY_RETRIEVAL_ELIGIBILITY_THRESHOLD`, `MEMORY_QUARANTINE_RISK_THRESHOLD`).
Replay/rebuild runs may be scoped with `MEMORY_LAB_REPLAY_RUN_ID`; E8 tolerance is configurable via `MEMORY_E8_TOPK_OVERLAP_TOLERANCE`.

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

### E2 - Repeated Recall Drift (with mutation)

File: `e2_repeated_recall_drift.py`

Purpose:
- Force recall under changing context pressures.
- Mutate memory text and metadata on each recall.
- Measure drift against base and previous versions.

Current behavior:
- Seeds one episodic memory vector.
- Runs repeated recalls with context-shifted queries.
- Emits `recalled` then `mutated` lineage events in a causal chain.
- Rewrites the same vector key after each mutation with updated trust/confidence/reinforcement metadata.
- Logs cosine drift metrics so reconsolidation movement is measurable, not theatrical.

Analysis artifact:
- `sql/e2_drift_analysis.sql` contains Athena queries for drift timeline, score evolution, and summary metrics.

### E3 - Time Reinforcement (Spaced vs Single Strong)

File: `e3_time_reinforcement.py`

Purpose:
- Compare spaced reinforcement against a single strong write over increasing time gaps.

Current behavior:
- Seeds two memories with equal trust.
- Applies repeated reinforcement to one memory at checkpoints.
- Lets the other memory decay with only initial strong reinforcement.
- Emits lineage events with eligibility score snapshots for comparison.

### E4 - Conflict Persistence Under Retrieval

File: `e4_conflict_persistence.py`

Purpose:
- Ensure contradictory memories persist together under repeated retrieval.

Current behavior:
- Seeds two conflicting claims with explicit contradiction metadata.
- Emits `observed` and `contradicted` lineage events for both sides.
- Runs repeated queries and logs accepted/rejected retrieval outcomes.

### E5 - Sleep Promotion (Episodic -> Semantic)

File: `e5_sleep_promotion.py`

Purpose:
- Promote repeated episodic traces into a semantic memory when thresholds are met.

Current behavior:
- Seeds 4 related episodic memories.
- Evaluates promotion eligibility via access count and context variance.
- Emits `snapshotted` promotion eligibility event.
- If eligible, writes semantic vector and emits `promoted` plus linkage `mutated` events.

### E6 - Poisoning Before Promotion

File: `e6_poisoning_before_promotion.py`

Purpose:
- Block high-trust poisoned claims from promotion when support is weak and conflicts are high.

Current behavior:
- Seeds trusted false-ish claim plus weak contradictory signal.
- Emits contradiction and risk snapshot events.
- Quarantines poisoned memory before promotion.
- Writes vector status as `quarantined` with safety override.

### E7 - Replay Rebuild

File: `e7_replay_rebuild.py`

Purpose:
- Prove materialized state can be reconstructed from canonical lineage.

Current behavior:
- Emits observed/mutated events for two memories, tagged with `run_id`.
- Runs ingestion to canonical Athena table.
- Deletes materialized vectors for those memories.
- Replays canonical lineage rows and rebuilds memory state for the same `run_id`.
- Rewrites vectors from rebuilt state and checks replay equality.
- Emits a reproducibility snapshot with replay signature and metadata.

### E8 - Vector Rebuild Equivalence

File: `e8_vector_rebuild.py`

Purpose:
- Prove vector recall can be rebuilt from lineage with acceptable retrieval equivalence.

Current behavior:
- Seeds three memories and ingests lineage.
- Records baseline top-3 recall for a query.
- Deletes only this experiment's vectors.
- Rebuilds vectors from canonical lineage for the same `run_id` and reruns recall.
- Compares top-3 overlap and marks equivalent if overlap >= configured tolerance.
- Emits a reproducibility snapshot with ranking signature and metadata.

Notes:
- Lineage events are currently written as append-only JSON ingress objects in S3.
- Run ingestion after experiments to move records into Athena canonical/quarantine tables.
