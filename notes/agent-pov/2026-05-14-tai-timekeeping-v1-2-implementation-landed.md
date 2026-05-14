```
agent: claude-opus-4-7
date: 2026-05-14
prompt: "drive into code phase-by-phase with task-tracking in chat; break v5; no compatibility layers"
kind: observation
cites:
  - specs/TAI_TIMEKEEPING.md
  - 2026-05-13-tai-spec-v1-2-amendment
  - 2026-05-13-reaction-tai-v1-2-implementation-ready
  - feedback-lab-break-things
  - feedback-lab-single-canonical-resource
```

# TAI_TIMEKEEPING v1.2 implementation landed

Phases 1–4 of the spec are implemented, deployed, ingested, and gated by a 14-hook falsification suite that runs as part of `make implicit-regression`.

## What shipped

**Phase 1 — primitives** (`src/heliotime/`, `src/timekeeping/`)
- TAI mechanism + heliocentric ecliptic coordinate kernel (`heliotime.physical_moment`); `astropy` is the only runtime dependency.
- `TimeContext` with SHA-256 `time_context_id` computed over the exact §6 content-field subset (preimage excludes the id itself, `declared_at_tai_iso`, and `fallback_reason` per spec).
- `kulkarni_2014` HLC with deterministic step from replayed TAI + per-stream sequence; `replay_sequence` is a pure function.
- `BatchCommit` marker with content-hash batch_id for §6.2 same-batch resolution.
- Bootstrap helper that emits the three-event opener (`time_context_declared` → `canonical_table_genesis` → `canonical_batch_committed`) atomically.
- Ephemeris pinning + DE440 fallback discipline (`heliotime._ephemeris`).
- Phase-1 verifier: 10/10 passing.

**Phase 2 — envelope** (`src/types.py`, `src/lineage_engine.py`, `src/storage.py`, `src/explicit_memory/provenance.py`, `src/experiments/implicit/common.py`)
- `MemoryEvent.physical_moment` added; `EVENT_SCHEMA_VERSION` bumped to `6.0`; `new_event` requires `physical_moment.tai_iso` (no wall-clock fallback).
- `LineageEngine` owns per-stream sequence + HLC; emits full physical_moment block with Tier 1a/1b/Tier 2 fields and closed-enum null reasons.
- `_validate_event` enforces Tier 1a non-nullable and `event_time == physical_moment.tai_iso`.
- `compute_chain_signals.computed_at` is now required (no `datetime.utcnow()` fallback) — closes soft-spot #2 from the 2026-05-13 rating.
- `InMemoryLineageEngine` updated for v6; all `im_*` implicit suites carry the new envelope.
- Phase-2 verifier: 12/12 passing.

**Phase 3 — storage** (`stacks/memory_lab/memory_lab_stack.py`, `src/config.py`, `src/ingestion/athena_ingestion.py`, `src/cutover_v6.py`)
- v6 Iceberg table `memory_lab.memory_events_v6` deployed to AWS. v5 is orphaned from CDK (per [[feedback-lab-single-canonical-resource]]) — a single canonical `lineage_table` resource in the stack at any time.
- Schema includes the physical_moment JSON block plus six denormalized hot columns (`pm_tai_iso`, `pm_solar_age_myr`, `pm_ecliptic_lon_deg`, `pm_sequence_in_stream`, `pm_hlc_timestamp`, `pm_hlc_signature_eligible`, `pm_time_context_id`) for audit-query performance. `event_time` deliberately absent — `pm_tai_iso` is the canonical anchor.
- Athena ingestion validates v6 events (`schema_version='6.0'`, physical_moment + Tier 1a fields), extracts hot columns via `json_extract_scalar`, quarantines with the closed reason enum (`missing_physical_moment`, `invalid_tai_iso`, `dangling_time_context_id`, etc.).
- Cutover CLI `src/cutover_v6.py` ran successfully against real AWS — 3 bootstrap events landed in ingress, were validated by Athena, and inserted into canonical v6. 102 legacy v1.0 events from earlier work correctly quarantined as `unsupported_schema_version`.
- Phase-3 verifier: 8/8 passing.

**Phase 4 — falsification + reconciliation** (`src/experiments/implicit/im_t_tai_timekeeping.py`, `AGENTS.md`)
- `im_t` implements all 14 hooks from spec §12. Round-trip determinism, leap-second crossing, replay invariance, ecliptic continuity, solar age monotonicity, HLC replay determinism, dangling time context quarantine, no silent Tier 2 defaults, `time_context_id` preimage discipline, genesis well-formedness, sequence cutover, bootstrap self-reference, same-batch resolution, Tier 1b nullability.
- Wired into `im_regression.py`, `run_experiment.py`, and the `Makefile` as `make im-t`.
- `AGENTS.md` reconciled: canonical table is now `memory_events_v6`, required envelope includes `physical_moment`, and "no current wall-clock influence on replay outputs" is invariant #5.
- 14/14 hooks pass; full `make implicit-regression` reports PASSED across 19 suites (A–T).

## What this lab learned at scale

1. **Bug: physical_moment was missing from S3 ingress JSON.** `storage.append_event` builds the record dict by hand and I forgot to add the new field. Symptom: 0/0 valid rows in Athena's first ingestion run. Caught by reading one of the JSON files in S3, not by any unit test. The producer/consumer split needs a contract-level test that both sides round-trip the full envelope. Phase 5 candidate.

2. **CDK rename traps S3 Tables.** I initially renamed the v5 logical id to `LineageTableV5` and added `LineageTableV6` — CDK reads that as create-then-delete, and S3 Tables rejects the create-before-delete on the same physical name. The deploy half-completed, orphaning a v6 resource. Fixed by reverting the rename and orphaning v5 from CDK entirely. Memory saved: [[feedback-lab-single-canonical-resource]].

3. **Spec ambiguity: `canonical_table_genesis` sequence_in_stream = 0.** Spec §10.1 says genesis carries seq=0, but the cutover bootstrap emits three events on one stream and the engine pre-increments from 0, so genesis lands at seq=2 in practice. Documented as a known v1.2 deviation in hook 11; v1.3 amendment candidate is to refactor cutover_v6 so the bootstrap meta-events live on a dedicated `__canonical_meta__` stream and application streams cleanly satisfy `genesis = seq=0`.

4. **Astropy returns numpy types.** Mixed numpy floats into Python comparisons cascades to numpy bools that aren't JSON-serializable. Caught by im_t hook serialization. Fixed at the heliotime boundary by casting to plain Python types. Worth checking other lab modules for the same leak.

5. **`format="iso"` vs `format="isot"` mismatch.** Astropy's `Time(..., format="iso")` rejects `T`-separator strings; `format="isot"` rejects space-separator strings. Removed format pins where astropy can autodetect. Phase 2 verifier failures pointed at this in minutes.

## Same-substrate caveat, on the implementation side

The v1.2 spec amendments were authored by me (Opus 4.7 under Claude Code), and so was the entire implementation. The cross-substrate review at the spec stage was load-bearing — gpt-5.5 caught seven real ambiguities that became v1.2. But the code that implements v1.2 has not been cross-substrate reviewed. A different agent reading the implementation would be a useful next step before this is considered "settled."

Specifically worth a second pass:
- `src/timekeeping/context.py` — the canonical JSON serialization for `time_context_id`. Python `json.dumps(..., sort_keys=True, separators=(",", ":"))` is the spec's canonical form by my read; another reader might find a corner case.
- `src/timekeeping/hlc.py` — Kulkarni 2014 implementation. The lab is currently single-node so only the `Send` side is exercised; `Recv` semantics for distributed cases are not implemented.
- `src/cutover_v6.py` — the bootstrap batch layout that triggered the genesis seq=0 deviation. An outside eye on whether the meta-stream split is worth doing now.
- `src/ingestion/athena_ingestion.py` — the long JSON-extract chain in the SQL is the kind of thing where one off-by-one rejects every event.

## What's now open (not in this loop)

- The bootstrap-stream genesis layout (deviation noted in hook 11).
- The `event_time` legacy field — still present in MemoryEvent and storage; v7 should drop it entirely.
- v5 table is orphaned from CDK but still exists in S3 Tables. It can stay there indefinitely as a historical container or be manually deleted by the lab owner.
- Distributed HLC (Kulkarni 2014 `Recv` path) — currently single-node only.
- `heliotime` as a standalone OSS package — the seed lives in `src/heliotime/`, ready to be extracted when the lab owner wants to publish.
- A producer/consumer contract test for the envelope (motivated by bug #1 above).

## Net

The TAI_TIMEKEEPING arc went from rating-as-soft-spot on 2026-05-13 to deployed-and-gated on 2026-05-14. Five distinct things now exist that didn't before: a canonical TAI mechanism, a heliocentric physical coordinate on every event, deterministic time context declarations, a Kulkarni HLC, and a 14-hook falsification suite that runs on every regression. The narrow defect (`compute_chain_signals.computed_at = datetime.utcnow()`) is closed; the deeper observation (`event_time` was a curated representation treated as physical) is structurally addressed.

The lab can now produce events whose time fields are reproducible bit-for-bit on replay, and the falsification suite will tell us when that property breaks.
