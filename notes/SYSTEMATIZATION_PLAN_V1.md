# Systematization Plan v1

## Intent

Systematize the current AWS-native memory lab from successful mechanics into durable, auditable, replayable architecture with S3 Tables as the intended canonical backbone.

---

## Phase 1: Stabilize data contracts (now)

1. Freeze event envelope schema (`event_id`, `agent_id`, `stream_id`, `event_type`, `memory_id`, `event_time`, `payload`, `parent_event_id`).
2. Add schema version field (`schema_version`).
3. Enforce required fields at write time + quarantine reason taxonomy.

### Checks

- [ ] Every emitted event includes all required envelope fields.
- [ ] `schema_version` is present on all new events.
- [ ] Invalid events are rejected from canonical path and land in quarantine with explicit reason codes.
- [ ] Envelope format is documented in code and specs.

---

## Phase 2: Make S3 Tables first-class canonical

1. Keep ingress S3 as append-only intake.
2. Keep Athena raw/quarantine.
3. Promote S3 Tables table to canonical sink (instead of Athena external canonical table).
4. Build deterministic ingest-commit job:
   - validate
   - dedupe by `event_id`
   - commit to S3 Tables canonical
   - emit ingest audit metrics

### Checks

- [ ] Canonical writes go to S3 Tables (not only Athena external canonical table).
- [ ] Re-running ingestion on the same input does not duplicate canonical events.
- [ ] Ingest metrics are emitted (`processed`, `deduped`, `quarantined`, `failed`).
- [ ] Canonical row count matches expected unique `event_id` count from ingress minus quarantined records.

---

## Phase 3: Canonical-read abstraction

1. Add `LineageReader` interface used by experiments/engines.
2. Implement two readers:
   - `AthenaCanonicalReader` (current)
   - `S3TablesCanonicalReader` (target)
3. Add flag to switch read path without touching experiment logic.

### Checks

- [ ] Experiments run unchanged while toggling reader backend.
- [ ] E7 replay output equality is preserved across both readers for identical input.
- [ ] Reader selection is explicit via config/env and logged per run.

---

## Phase 4: Retrieval policy system

1. Move hardcoded thresholds to policy config.
2. Version policies and write `policy_id` with retrieval/quarantine events.
3. Add rejection reason enums (strict taxonomy).

### Checks

- [ ] No retrieval/quarantine threshold is hardcoded in experiment/engine logic.
- [ ] Every `recalled`/`rejected`/`quarantined` event includes `policy_id`.
- [ ] Rejection reasons come from controlled enum values.
- [ ] Policy changes are auditable by version and effective timestamp.

---

## Phase 5: Replay/rebuild hardening

1. Idempotent replay by stream/run ID.
2. Snapshot cadence + replay-equality checks automated.
3. Add E7/E8 regression gates in CI-like script (`make lab-regression`).

### Checks

- [ ] Re-running E7 on same stream/run remains stable and deterministic.
- [ ] E8 rebuild equivalence check passes within configured tolerance.
- [ ] `make lab-regression` runs E7/E8 and fails fast on mismatch.
- [ ] Snapshot events include reproducibility metadata (reader, policy, schema version).

---

## Phase 6: Attack-surface prep (before IAM deep dive)

1. Add explicit actor/source typing in events.
2. Track cross-stream influence attempts.
3. Add goal-hijack suspicion tags in quarantine logic.

### Checks

- [ ] Events contain explicit source/actor class fields for security analysis.
- [ ] Cross-stream or cross-agent reference attempts are observable in lineage.
- [ ] Suspicion tagging is deterministic and queryable.
- [ ] Quarantine events include machine-readable threat/suspicion labels.

---

## Table-split clarity (finalized for this lab)

Migration is complete. This lab now has a fixed split of responsibilities:

- Ingress evidence + validation: `AwsDataCatalog.memory_lab.lineage_events_raw`
- Quarantine evidence: `AwsDataCatalog.memory_lab.lineage_events_quarantine`
- Canonical lineage (source of replay truth): `s3tablescatalog/<bucket>.memory_lab.memory_events_v4`

Hard rules (no longer transitional):

1. New ingestion targets `memory_events_v4` only.
2. `memory_events_v3` is deprecated and read-only for rollback/history checks.
3. Raw/quarantine are ingestion-quality surfaces, not canonical belief history.
4. Replay/belief/audit conclusions must come from canonical (`memory_events_v4`).
5. Any future canonical schema change must use explicit `memory_events_vN` cutover + backfill.

### Finalization checks

- [x] Canonical target default is `AWS_ATHENA_TARGET_TABLE_FQN=memory_lab.memory_events_v4`.
- [x] Ingestion preflight validates target schema/projection before ingest.
- [x] Ingestion idempotency confirmed on re-run.
- [x] Phase 5 and Phase 6 audits run successfully on current flow.
- [x] Phase 6 regression passes with deterministic threat/suspicion tagging.

## Parallel storage strategy for evidence

Closed for this stage. We are no longer evaluating a dual-canonical strategy in this small lab.

Decision:
- S3 Tables canonical (`memory_events_v4`) is the backbone.
- Athena raw/quarantine remains as supporting ingestion evidence only.

---

## Why this plan

- Preserves current momentum.
- Keeps lineage-first and replayability constraints explicit.
- Enables evidence-based storage decisions in-lab.
- Leaves room for later IAM hardening and adversarial scenarios without rewriting fundamentals.
