from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path | None = None, *, override: bool = False) -> None:
    """
    Minimal .env loader to avoid extra dependencies.
    Supports KEY=VALUE lines and ignores comments/blank lines.
    """
    env_path = path or Path(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value


@dataclass(slots=True)
class Settings:
    aws_profile: str
    aws_region: str
    aws_vector_bucket_name: str
    aws_vector_index_name: str
    aws_events_bucket_name: str
    aws_state_bucket_name: str
    aws_analytics_bucket_name: str
    memory_root: str
    storage_mode: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            aws_profile=os.getenv("AWS_PROFILE", "stack-research"),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            aws_vector_bucket_name=os.getenv("AWS_VECTOR_BUCKET_NAME", "experimental-memory-lab"),
            aws_vector_index_name=os.getenv("AWS_VECTOR_INDEX_NAME", "memories-v1"),
            aws_events_bucket_name=os.getenv("AWS_EVENTS_BUCKET_NAME", "memory-events"),
            aws_state_bucket_name=os.getenv("AWS_STATE_BUCKET_NAME", "memory-state"),
            aws_analytics_bucket_name=os.getenv("AWS_ANALYTICS_BUCKET_NAME", "memory-analytics"),
            memory_root=os.getenv("MEMORY_ROOT", "var/lab"),
            storage_mode=os.getenv("STORAGE_MODE", "aws"),
        )
