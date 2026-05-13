from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import boto3

from src.config import _load_project_env_files


def _artifact_bucket_name() -> str:
    _load_project_env_files()
    bucket = os.environ.get("AWS_S3_RESEARCH_ARTIFACTS_BUCKET_NAME")
    if not bucket:
        raise ValueError("AWS_S3_RESEARCH_ARTIFACTS_BUCKET_NAME must be set")
    return bucket


def _artifact_prefix() -> str:
    return os.environ.get("IMPLICIT_ARTIFACT_PREFIX", "implicit").strip("/")


def _s3_client() -> Any:
    profile = os.environ.get("AWS_PROFILE")
    region = os.environ.get("AWS_REGION", "us-east-2")
    if profile:
        return boto3.Session(profile_name=profile, region_name=region).client("s3")
    return boto3.Session(region_name=region).client("s3")


def write_artifact(*, name: str, payload: dict[str, Any]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"{_artifact_prefix()}/{name}-{ts}.json"
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")

    s3 = _s3_client()
    bucket = _artifact_bucket_name()
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    return f"s3://{bucket}/{key}"
