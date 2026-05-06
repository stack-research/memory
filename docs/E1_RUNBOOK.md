# E1 Runbook (Live Cloud)

This runbook executes E1 (Trust vs Truth) against live deployed stacks.

## Preconditions

- AWS profile `stack-research` configured.
- `.env` populated with required values:
  - `AWS_REGION`
  - `AWS_EVENTS_BUCKET_NAME`
  - `AWS_STATE_BUCKET_NAME`
  - `AWS_ANALYTICS_BUCKET_NAME`
  - `AWS_VECTOR_BUCKET_NAME`
  - `AWS_VECTOR_INDEX_NAME`
- API URL from `MemoryComputeStack` output set as `MEMORY_API_BASE_URL`.

## Command Sequence

1. Preflight:
   - `scripts/preflight.sh`
2. Bootstrap (first time only):
   - `AWS_PROFILE=stack-research scripts/cdk.sh bootstrap`
3. Deploy:
   - `AWS_PROFILE=stack-research scripts/cdk.sh deploy`
4. Smoke:
   - `scripts/infra_smoke.sh`
5. Run E1 live:
   - `MEMORY_API_BASE_URL=<api-url> python3 scripts/run_e1_live.py`
6. Evaluate pass/fail:
   - `MEMORY_API_BASE_URL=<api-url> python3 scripts/test_e1_live.py`
7. Optional teardown:
   - `AWS_PROFILE=stack-research scripts/cdk.sh destroy`

## Troubleshooting

- `Missing required environment vars for deploy`: export required env vars before `scripts/cdk.sh deploy`.
- `sam: command not found`: install AWS SAM CLI locally.
- `lineage empty`: confirm `STORAGE_MODE=aws` in lambda env and check bucket write permissions.
- `retrieve results empty`: verify ingestion completed and API URL targets current deployed stage.
