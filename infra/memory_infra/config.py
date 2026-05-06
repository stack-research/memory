from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(slots=True)
class InfraConfig:
    aws_profile: str
    aws_region: str
    events_bucket_name: str
    state_bucket_name: str
    analytics_bucket_name: str
    vector_bucket_name: str
    vector_index_name: str

    @classmethod
    def from_env(cls) -> "InfraConfig":
        return cls(
            aws_profile=os.getenv("AWS_PROFILE", "stack-research"),
            aws_region=os.getenv("AWS_REGION", "us-east-2"),
            events_bucket_name=os.getenv("AWS_EVENTS_BUCKET_NAME", "experimental-memory-events"),
            state_bucket_name=os.getenv("AWS_STATE_BUCKET_NAME", "experimental-memory-state"),
            analytics_bucket_name=os.getenv("AWS_ANALYTICS_BUCKET_NAME", "experimental-memory-analytics"),
            vector_bucket_name=os.getenv("AWS_VECTOR_BUCKET_NAME", "experimental-memory"),
            vector_index_name=os.getenv("AWS_VECTOR_INDEX_NAME", "memories-v1"),
        )
