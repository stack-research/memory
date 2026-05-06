from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AwsConfig:
    region: str
    profile: str | None
    table_bucket_name: str
    table_namespace: str
    table_name: str
    lineage_ingress_bucket_name: str | None
    lineage_ingress_prefix: str
    vector_bucket_name: str
    vector_index_name: str
    embedding_model_id: str



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

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
            value = value[1:-1]

        if override or key not in os.environ:
            os.environ[key] = value


def _load_project_env_files() -> None:
    project_root = Path(__file__).resolve().parent.parent
    _load_dotenv_file(project_root / ".env", override=False)
    _load_dotenv_file(project_root / ".env.local", override=True)


def load_config() -> AwsConfig:
    _load_project_env_files()
    return AwsConfig(
        region=os.environ.get("AWS_REGION", "us-east-2"),
        profile=os.environ.get("AWS_PROFILE"),
        table_bucket_name=os.environ["AWS_S3_TABLE_BUCKET_NAME"],
        table_namespace=os.environ.get("AWS_S3_TABLE_NAMESPACE", "memory_lab"),
        table_name=os.environ.get("AWS_S3_TABLE_NAME", "memory_events"),
        lineage_ingress_bucket_name=os.environ.get("AWS_S3_LINEAGE_INGRESS_BUCKET_NAME"),
        lineage_ingress_prefix=os.environ.get("AWS_S3_LINEAGE_INGRESS_PREFIX", "lineage-events/"),
        vector_bucket_name=os.environ["AWS_S3_VECTOR_BUCKET_NAME"],
        vector_index_name=os.environ.get("AWS_S3_VECTOR_INDEX_NAME", "memories-v1"),
        embedding_model_id=os.environ.get(
            "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
        ),
    )
