# IAM Hardening Plan

## Objective

Constrain blast radius.

This phase hardens access boundaries so each subsystem can do exactly what it must do — and nothing more.

## Design principle

- **Constrain blast radius** by default.
- Enforce least privilege with explicit role separation.
- Prefer explicit deny guardrails for destructive or out-of-scope operations.
- Keep permissions auditable and easy to reason about.

## Role separation (principals)

1. **Experiment/engine runtime principal**
   - Allowed:
     - write ingress events (`s3:PutObject` on lineage ingress prefix)
     - write/query vectors for approved bucket/index
   - Denied:
     - canonical S3 Tables writes
     - ingress/quarantine deletes

2. **Ingestion principal**
   - Allowed:
     - read ingress objects
     - write quarantine objects
     - execute Athena ingestion statements
     - insert into canonical S3 Tables lineage target
   - Denied:
     - vector write/delete operations

3. **Replay/audit principal**
   - Allowed:
     - read canonical lineage
     - run Athena replay/audit queries
   - Denied:
     - vector mutations
     - ingress/quarantine/canonical writes

4. **CDK deploy principal**
   - Allowed:
     - infrastructure lifecycle operations
   - Denied (in normal runtime):
     - data-plane mutation by default

## Policy boundaries

### S3 ingress + quarantine buckets

- Prefix-scoped writes only (e.g., `lineage-events/...`).
- Runtime roles must not delete or purge evidence objects.
- Keep object versioning and retain controls aligned with audit requirements.

### S3 Vectors

- Restrict to exact `vectorBucketName` and `indexName`.
- Explicitly deny cross-environment or unapproved index operations.
- Restrict delete rights to approved rebuild/maintenance paths only.

### Athena

- Force use of approved workgroup (e.g., `memory-lab`).
- Constrain query execution context (catalog/database) to approved surfaces.
- Restrict query result locations to approved results bucket/prefix.

### S3 Tables canonical lineage

- Only ingestion role can insert canonical rows.
- Replay/audit role is read-only.
- Runtime experiment role has no direct canonical write permissions.

### STS session tagging (recommended)

Tag sessions with:
- `agent_id`
- `stream_id`
- `run_id`

Use tags for audit correlation and policy conditions where possible.

## Required explicit deny controls

1. Deny canonical table writes from experiment role.
2. Deny vector deletes outside rebuild/maintenance role.
3. Deny `s3:DeleteObject` on ingress/quarantine for runtime roles.
4. Deny Athena execution outside approved workgroup/catalog/database.

## Validation plan

Use both happy-path and must-fail tests.

### Must-pass

- Ingestion role can run ingestion end-to-end:
  - read ingress
  - quarantine invalid
  - insert valid into canonical

### Must-fail

- Experiment role tries canonical write -> **must fail**.
- Replay/audit role tries vector put/delete -> **must fail**.
- Runtime role tries delete in ingress/quarantine -> **must fail**.
- Principal tries Athena execution outside approved workgroup/context -> **must fail**.

## Suggested rollout

1. **Document** current principals and permissions (baseline snapshot).
2. **Create/adjust** least-privilege managed policies per principal.
3. **Attach explicit denies** for high-risk actions.
4. **Run validation suite** (must-pass + must-fail).
5. **Turn on monitoring** (CloudTrail/Athena query logs/S3 access logs as available).
6. **Lock and review**: keep policy diffs small and auditable.

## Companion implementation doc

For concrete resource/action mapping, policy skeletons, ARN templates, and execution checks, use:

- `notes/IAM_IMPLEMENTATION_CHECKLIST.md`

## Done criteria

- Role boundaries are enforced and tested.
- Blast radius is constrained for every principal.
- Security-relevant failures are observable and reproducible.
- IAM model is documented and tracked alongside systematization milestones.
