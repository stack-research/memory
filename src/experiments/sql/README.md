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
- `memory_lab.memory_events_v4` (default)

Or run automatically from repo root:
- `make e2-analysis`

## E5 Promotion Analysis

File: `e5_promotion_analysis.sql`

Covers:
- E5 timeline
- promotion gate snapshots (`snapshotted`)
- semantic promotion record (`promoted`)
- episodic linkage events (`mutated` with `derived_from` relation)

Run automatically from repo root:
- `make e5-analysis`

## Phase 4 Policy Audit

File: `phase4_policy_audit.sql`

Covers:
- policy audit field coverage (`policy_id`, `policy_version`, `policy_effective_at`)
- controlled reason taxonomy usage for `rejected` and `quarantined`
- recent spot-audit rows

Run automatically from repo root:
- `make phase4-audit`

## Phase 5 Replay/Rebuild Hardening Audit

File: `phase5_replay_hardening_audit.sql`

Covers:
- E7 run-scoped replay determinism (`state_signature` stability)
- E8 rebuild equivalence per run/tolerance
- snapshot reproducibility metadata coverage (`reader`, `policy`, `schema`, `run_id`)

Run automatically from repo root:
- `make phase5-audit`

## Phase 6 Attack-Surface Prep Audit

File: `phase6_attack_surface_audit.sql`

Covers:
- actor/source class coverage on events
- cross-scope influence attempt observability
- quarantine suspicion/threat label coverage

Run automatically from repo root:
- `make phase6-audit`
