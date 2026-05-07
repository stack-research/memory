# Experiment SQL Query Packs

These Athena SQL files are analysis artifacts for experiment runs.

## E2 Drift Analysis

File: `e2_drift_analysis.sql`

Covers:
- event timeline and causal chain
- drift progression (`cosine_similarity_to_base`, `...to_previous`)
- trust/confidence/reinforcement evolution
- aggregate drift summary

Run in Athena (workgroup `memory-lab`) against:
- `memory_lab.lineage_events_canonical` (default)

Or run automatically from repo root:
- `make e2-analysis`
