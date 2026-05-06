#!/usr/bin/env python3
"""CDK entrypoint. Prefer CDK_DEFAULT_ACCOUNT / CDK_DEFAULT_REGION, then active AWS credentials."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import aws_cdk as cdk

from memory_lab.memory_lab_stack import MemoryLabStack


def _load_dotenv_file(path: Path, *, override: bool) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export ") :].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"\"", "'"}
        ):
            value = value[1:-1]

        if override or key not in os.environ:
            os.environ[key] = value


def _load_project_env_files() -> None:
    project_root = Path(__file__).resolve().parent.parent
    _load_dotenv_file(project_root / ".env", override=False)
    _load_dotenv_file(project_root / ".env.local", override=True)


def _deployment_env() -> cdk.Environment | None:
    account = os.environ.get("CDK_DEFAULT_ACCOUNT")
    region = (
        os.environ.get("CDK_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
    )
    if account and region:
        return cdk.Environment(account=account, region=region)

    try:
        import boto3

        session = boto3.Session()
        if session.get_credentials() is None:
            return None

        sts = session.client("sts")
        resolved_account = account or sts.get_caller_identity()["Account"]
        resolved_region = region or session.region_name or "us-east-1"

        return cdk.Environment(account=resolved_account, region=resolved_region)
    except Exception:
        return None


_load_project_env_files()

app = cdk.App()
stack_kwargs: dict[str, Any] = {"stack_name": "memory-lab"}
_deploy_env = _deployment_env()
if _deploy_env is not None:
    stack_kwargs["env"] = _deploy_env

MemoryLabStack(app, "MemoryLabStack", **stack_kwargs)
app.synth()
