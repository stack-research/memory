# Canonical Table Migration Notes

## Purpose

Safely migrate canonical lineage schema in S3 Tables (for example adding `actor_class`, `source_class`) without breaking ingest, replay, or audit.

## Scope

- Canonical table in `s3tablescatalog/<table-bucket>.memory_lab.memory_events_vN`
- Raw/quarantine tables in `AwsDataCatalog.memory_lab.lineage_events_raw` and `lineage_events_quarantine`

## Preconditions

- AWS profile: `stack-research`
- Region: `us-east-2` (or your target)
- Ingestion remains append-only to ingress S3
- New envelope fields already emitted by writers

## Phase A: Plan

1. Pick new canonical table name, e.g. `memory_events_v5`.
2. Freeze target schema (columns, order, types, requiredness).
3. Identify cutover env vars:
   - `AWS_ATHENA_TARGET_TABLE_FQN`
   - any reader config pointing to canonical table

## Phase B: Create new canonical table

Use CDK (preferred) to add/update the canonical S3 Tables table schema, then deploy.

Example:

```bash
make deploy AWS_PROFILE=stack-research AWS_REGION=us-east-2
```

Verify table exists:

```bash
aws athena start-query-execution \
  --work-group memory-lab \
  --query-string "SHOW TABLES IN memory_lab" \
  --query-execution-context Database=memory_lab,Catalog=s3tablescatalog/memory-lab-lineage-table \
  --profile stack-research --region us-east-2
```

## Phase C: Backfill from raw to new canonical

1. Set target table env (in `.env`/runtime env):
   - `AWS_ATHENA_TARGET_TABLE_FQN=memory_lab.memory_events_v5`
2. Run ingestion:

```bash
make ingest AWS_PROFILE=stack-research AWS_REGION=us-east-2
```

3. Re-run ingestion once to confirm dedupe/idempotency.

Acceptance:
- Second run should not reinsert existing `event_id`s.

## Phase D: Validate

Run:

```bash
make phase5-audit AWS_PROFILE=stack-research AWS_REGION=us-east-2
make phase6-audit AWS_PROFILE=stack-research AWS_REGION=us-east-2
make lab-regression AWS_PROFILE=stack-research AWS_REGION=us-east-2
make phase6-regression AWS_PROFILE=stack-research AWS_REGION=us-east-2
```

Validation checklist:

- Replay determinism still passes (E7/E8)
- Phase 6 observability signals present
- No unexpected ingestion failures
- Canonical row count aligns with expected valid unique event count

## Phase E: Cutover readers

1. Point canonical readers to new table version.
2. Confirm experiments run unchanged.
3. Record decision/change log with timestamp.

## Phase F: Stabilize + deprecate old canonical

- Keep prior canonical table read-only for rollback window.
- After window, mark old table deprecated in docs.
- Do not delete raw/quarantine evidence tables.

## Rollback

If issues occur:

1. Reset `AWS_ATHENA_TARGET_TABLE_FQN` and readers to previous canonical version.
2. Re-run ingestion to continue writes to old canonical target.
3. Keep failed/new table for forensic comparison.

## Troubleshooting

### Type mismatch on INSERT

Symptom: Athena `TYPE_MISMATCH` during canonical insert.

Cause: insert projection does not match canonical table column count/order/types.

Fix:
- Align `INSERT INTO ... SELECT ...` projection with canonical schema exactly.
- Re-run `make ingest`.

### Audit query fails table-not-found

Cause: query catalog/table mismatch (`AwsDataCatalog` vs `s3tablescatalog/...`).

Fix:
- Use raw/quarantine audits against `AwsDataCatalog`.
- Use canonical history/replay audits against `s3tablescatalog/...`.

## Operational notes

- Raw/quarantine path is ingestion evidence.
- Canonical S3 Tables path is replay/audit truth.
- During migration windows, schema differences are expected; explicit targeting is required.

## Migration status (completed)

- Canonical table `memory_events_v5` created with `actor_class` and `source_class`.
- Ingestion updated to schema-adaptive canonical projection (prevents target column mismatch).
- Environment defaults updated to v4 (`AWS_S3_TABLE_NAME`, `AWS_ATHENA_TARGET_TABLE_FQN`).
- Backfill/idempotency validated (`inserted` then `0` on re-run for same input).
- Phase 5 and Phase 6 audits pass against current flows.
- `phase6-regression` passes.

## Deprecation note

- `memory_events_v3` is now deprecated.
- Keep read-only during rollback window; do not target it for new ingestion.
- Remove/decommission after stability window and explicit sign-off.

## Change record

- Date: 2026-05-08
- Migration: canonical `memory_events_v3` -> `memory_events_v5`
- Reason: include security envelope fields (`actor_class`, `source_class`) in canonical lineage.
- Caveat: E8 equivalence gates remain sensitive to corpus density/tolerance settings during replay windows.
