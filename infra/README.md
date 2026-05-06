# CDK Infrastructure

This folder contains Python CDK stacks for memory backend infrastructure.

## Prerequisites

- AWS CDK CLI installed (`npm i -g aws-cdk`)
- Python 3.11+
- AWS credentials configured for profile `stack-research`

## Setup

```bash
cd infra
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

## Deploy

```bash
AWS_PROFILE=stack-research cdk bootstrap
AWS_PROFILE=stack-research cdk synth
AWS_PROFILE=stack-research cdk deploy --all
```

## Destroy

```bash
AWS_PROFILE=stack-research cdk destroy --all
```

## Stack design

- `MemoryDataStack`: S3 buckets + SSM params
- `MemoryComputeStack`: API Lambda, Sleep Lambda, API Gateway, EventBridge schedule, Glue DB, Athena workgroup

Environment variables passed to lambdas match `src/memory_lab/config.py`.

## Local Lambda guardrails (optional)

Use CDK + SAM local for route/function confidence checks:

- `scripts/sam_local.sh start-api`
- `scripts/sam_local.sh invoke-api`
- `scripts/sam_local.sh invoke-sleep`

Live stack tests are still the source of truth for E1.
