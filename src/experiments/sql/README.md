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

## E9 Eligibility Pressure Analysis

File: `e9_eligibility_pressure_analysis.sql`

Covers:
- per-scenario expected vs observed winner agreement
- final agreement/pass snapshot
- rejection reason taxonomy usage within E9

Run automatically from repo root:
- `make e9-analysis`

## E10 Reconsolidation Stability Analysis

File: `e10_reconsolidation_stability_analysis.sql`

Covers:
- mutation drift timeline (`cosine_similarity_to_previous`, `...to_base`)
- final stability/pass snapshot
- mutation lineage parent linkage completeness

Run automatically from repo root:
- `make e10-analysis`

## E11 Promotion-Forgetting Coupling Analysis

File: `e11_promotion_forgetting_analysis.sql`

Covers:
- promotion gate decisions
- promoted + derived linkage event counts
- final coupling/pass summary metrics

Run automatically from repo root:
- `make e11-analysis`

## E12 Poison Resilience Analysis

File: `e12_poison_resilience_analysis.sql`

Covers:
- per-cycle poison risk snapshots
- quarantine label coverage
- final poison resilience/pass summary metrics

Run automatically from repo root:
- `make e12-analysis`

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

## Implicit Trigger Metrics

File: `im_trigger_metrics.sql`

Covers:
- trigger evaluated/fired/deferred/no-op counts
- admitted/rejected counts
- per-stream fired-rate for implicit runs (`stream_id like 'im-%'`)

Run automatically from repo root:
- `make im-trigger-analysis`

## Implicit Contamination Metrics

File: `im_contamination_metrics.sql`

Covers:
- contamination suspicion counts and reason taxonomy
- rejection reason correlation (`contamination_risk_threshold`, `event_flood_suspected`, `reflex_budget_exhausted`)

Run automatically from repo root:
- `make im-contamination-analysis`

## Implicit Replay Diff

File: `im_replay_diff.sql`

Covers:
- cross-stream event-type count deltas for implicit runs
- quick drift/determinism triage view

Run automatically from repo root:
- `make im-replay-diff`

## Phase 6 Attack-Surface Prep Audit

File: `phase6_attack_surface_audit.sql`

Covers:
- actor/source class coverage on events
- cross-scope influence attempt observability
- quarantine suspicion/threat label coverage

Run automatically from repo root:
- `make phase6-audit`
