# IAM Implementation Checklist (Blast-Radius Constrained)

This checklist maps the IAM hardening plan to concrete resources, actions, and validation tests used by this repo.

Primary objective: **constrain blast radius**.

## 1) Resource map (from `.env` / stack defaults)

Use these variables when rendering policies:

- `AWS_ACCOUNT_ID`
- `AWS_REGION`
- `AWS_S3_LINEAGE_INGRESS_BUCKET_NAME` (default example: `memory-lab-lineage-ingress`)
- `AWS_S3_LINEAGE_INGRESS_PREFIX` (default example: `lineage-events-raw/`)
- `AWS_S3_TABLE_BUCKET_NAME` (default example: `memory-lab-lineage-table`)
- `AWS_S3_TABLE_NAMESPACE` (default: `memory_lab`)
- `AWS_S3_TABLE_NAME` (default: `memory_events_v5`)
- `AWS_S3_VECTOR_BUCKET_NAME` (default example: `memory-lab-vectors`)
- `AWS_S3_VECTOR_INDEX_NAME` (default: `memories-v2`)
- `AWS_ATHENA_WORKGROUP_NAME` (default: `memory-lab`)
- `AWS_ATHENA_DATABASE` (default: `memory_lab`)
- `AWS_ATHENA_RAW_EVENTS_TABLE` (default: `lineage_events_raw`)
- `AWS_ATHENA_QUARANTINE_TABLE` (default: `lineage_events_quarantine`)

Common ARN templates:

- Ingress bucket: `arn:aws:s3:::${AWS_S3_LINEAGE_INGRESS_BUCKET_NAME}`
- Ingress objects: `arn:aws:s3:::${AWS_S3_LINEAGE_INGRESS_BUCKET_NAME}/${AWS_S3_LINEAGE_INGRESS_PREFIX}*`
- Quarantine objects: `arn:aws:s3:::${AWS_S3_LINEAGE_INGRESS_BUCKET_NAME}/${AWS_S3_LINEAGE_INGRESS_PREFIX%-/}-quarantine/*`
- Athena workgroup: `arn:aws:athena:${AWS_REGION}:${AWS_ACCOUNT_ID}:workgroup/${AWS_ATHENA_WORKGROUP_NAME}`
- S3 Tables bucket ARN: `arn:aws:s3tables:${AWS_REGION}:${AWS_ACCOUNT_ID}:bucket/${AWS_S3_TABLE_BUCKET_NAME}`
- S3 Vectors bucket ARN: `arn:aws:s3vectors:${AWS_REGION}:${AWS_ACCOUNT_ID}:bucket/${AWS_S3_VECTOR_BUCKET_NAME}`

## 2) Principal matrix

| Principal | Allow | Deny |
|---|---|---|
| `memory-lab-experiment-role` | ingress writes, vector put/query/delete (approved index only), Bedrock invoke, Athena read/query | canonical lineage writes, ingress/quarantine deletes |
| `memory-lab-ingestion-role` | Athena ingest DDL/DML, ingress read, quarantine write, canonical insert via Athena | vector mutations |
| `memory-lab-replay-audit-role` | Athena read/query, canonical read | vector mutations, ingress/quarantine/canonical writes |
| `memory-lab-deploy-role` | CDK/CloudFormation infra ops | routine data-plane mutation |

## 3) Action map by code path

### Experiment/engine path (`src/run_experiment.py`, `src/storage.py`, `src/vectors.py`, `src/embeddings.py`)

- `s3:PutObject` (ingress event write)
- `s3:ListBucket` (prefix-limited, optional but useful)
- `s3vectors:PutVectors`
- `s3vectors:QueryVectors`
- `s3vectors:DeleteVectors` (needed for E7/E8 rebuild workflows)
- `bedrock:InvokeModel`
- `athena:StartQueryExecution`, `athena:GetQueryExecution`, `athena:GetQueryResults` (reader/audit flows)
- `sts:GetCallerIdentity` (used in storage bootstrap helper)
- `s3tables:GetNamespace`, `s3tables:CreateNamespace`, `s3tables:GetTable`, `s3tables:CreateTable` (bootstrap path)

### Ingestion path (`src/ingestion/athena_ingestion.py`, `src/ingestion/preflight.py`)

- `athena:StartQueryExecution`, `athena:GetQueryExecution`, `athena:GetQueryResults`
- Glue catalog permissions for Athena DDL (`glue:GetDatabase`, `glue:GetTable`, `glue:CreateTable`, `glue:DeleteTable`, `glue:UpdateTable` as required)
- S3 read on ingress prefix
- S3 write on quarantine prefix
- Read/write required by Athena result location bucket/prefix

### Replay/audit path (`src/lineage_reader.py`, `src/experiments/run_sql_file.py`)

- `athena:StartQueryExecution`, `athena:GetQueryExecution`, `athena:GetQueryResults`
- read-only data catalog/table access
- read access to Athena results location

## 4) Baseline policy skeletons

> Note: Keep policies as small as possible. Start strict, then open only where CloudTrail shows legitimate denies.

### 4.1 Experiment role (allow)

- Allow ingress object write:
  - `s3:PutObject` on ingress object ARN only.
- Allow vectors on exact bucket/index only:
  - `s3vectors:PutVectors`, `s3vectors:QueryVectors`, `s3vectors:DeleteVectors`.
- Allow Bedrock model invoke for configured embedding model.
- Allow Athena query actions only with condition:
  - `athena:WorkGroup == ${AWS_ATHENA_WORKGROUP_NAME}`.
- Allow `sts:GetCallerIdentity`.
- Allow `s3tables:Get*` + optional `Create*` only if bootstrap-at-runtime is still enabled.

### 4.2 Ingestion role (allow)

- Allow Athena query actions with workgroup condition.
- Allow Glue catalog DDL/DML support for raw/quarantine tables in `${AWS_ATHENA_DATABASE}`.
- Allow `s3:GetObject` on ingress prefix.
- Allow `s3:PutObject` on quarantine prefix.
- Allow access to Athena results bucket/prefix.
- Allow required canonical write path (through Athena to S3 Tables target).

### 4.3 Replay/audit role (allow)

- Allow Athena query actions with workgroup condition.
- Allow read-only table/catalog access.
- Allow read-only Athena results bucket access.

## 5) Explicit deny guardrails (attach to runtime roles)

1. Deny canonical writes from experiment role.
2. Deny vector mutation from replay/audit role.
3. Deny `s3:DeleteObject` (and version deletes) on ingress/quarantine from experiment + replay roles.
4. Deny Athena query execution when `athena:WorkGroup != ${AWS_ATHENA_WORKGROUP_NAME}`.
5. Deny actions outside approved region/account if this environment is single-account/single-region.

## 6) Recommended tightening: remove runtime bootstrap create rights

Current experiment startup calls bootstrap (`ensure_namespace`, `ensure_table`).

Tightening option:

1. Run bootstrap once via deploy/admin role.
2. Remove `s3tables:CreateNamespace` / `s3tables:CreateTable` from runtime roles.
3. Keep runtime on read-only checks (`GetNamespace`, `GetTable`) or remove S3 Tables runtime access completely when not needed.

This materially reduces blast radius.

## 7) Validation checklist (must-pass + must-fail)

### Must-pass

- [ ] Ingestion role runs `make ingest-preflight` and `make ingest` successfully.
- [ ] Experiment role runs `make exp-e1` (and at least one replay run `e7` or `e8`) successfully.
- [ ] Replay/audit role runs `make phase5-audit` successfully.

### Must-fail

- [ ] Experiment role direct canonical write attempt -> denied.
- [ ] Replay/audit role vector put/delete attempt -> denied.
- [ ] Experiment/replay role ingress/quarantine delete attempt -> denied.
- [ ] Any role query on non-approved Athena workgroup -> denied.

## 8) Operational controls

- Enable CloudTrail for IAM, Athena, S3, and relevant data-plane APIs.
- Alert on explicit-deny hits for protected actions.
- Keep IAM policy diffs in code review.
- Re-run this checklist on every phase cutover.

## 9) Exit criteria

- All must-pass checks pass.
- All must-fail checks fail as expected.
- Runtime principals are least-privileged.
- Blast radius is constrained and demonstrated in evidence.
