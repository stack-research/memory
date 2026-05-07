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

## Parallel storage strategy for evidence

Run two tracks in parallel:

- Track A (current fast path): Athena canonical table
- Track B (target path): S3 Tables canonical sink

Same event contract, same experiments. Compare:

- ingest complexity
- replay determinism
- audit query ergonomics
- operational cost/overhead

### Comparison checks

- [ ] Each experiment (E1-E8) can run on both tracks with the same input fixture.
- [ ] Output deltas are measurable and documented.
- [ ] Cost and operational complexity are logged per track.
- [ ] Decision record produced for canonical backbone choice.

---

## Why this plan

- Preserves current momentum.
- Keeps lineage-first and replayability constraints explicit.
- Enables evidence-based storage decisions in-lab.
- Leaves room for later IAM hardening and adversarial scenarios without rewriting fundamentals.
