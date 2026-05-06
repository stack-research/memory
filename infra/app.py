#!/usr/bin/env python
from __future__ import annotations

import aws_cdk as cdk

from memory_infra.config import InfraConfig
from memory_infra.data_stack import MemoryDataStack
from memory_infra.compute_stack import MemoryComputeStack


app = cdk.App()
cfg = InfraConfig.from_env()
env = cdk.Environment(region=cfg.aws_region)

data_stack = MemoryDataStack(app, "MemoryDataStack", cfg=cfg, env=env)
MemoryComputeStack(
    app,
    "MemoryComputeStack",
    cfg=cfg,
    env=env,
    events_bucket=data_stack.events_bucket,
    state_bucket=data_stack.state_bucket,
    analytics_bucket=data_stack.analytics_bucket,
    vector_bucket_name=cfg.vector_bucket_name,
)

app.synth()
