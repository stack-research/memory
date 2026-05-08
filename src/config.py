from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .policy import RetrievalPolicy, build_policy_id


@dataclass(frozen=True)
class AwsConfig:
    region: str
    profile: str | None
    table_bucket_name: str
    table_namespace: str
    table_name: str
    athena_target_table_fqn: str
    athena_s3tables_catalog: str
    lineage_ingress_bucket_name: str | None
    lineage_ingress_prefix: str
    vector_bucket_name: str
    vector_index_name: str
    embedding_model_id: str
    retrieval_policy: RetrievalPolicy



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
        table_name=os.environ.get("AWS_S3_TABLE_NAME", "memory_events_v4"),
        athena_target_table_fqn=os.environ.get("AWS_ATHENA_TARGET_TABLE_FQN", "memory_lab.memory_events_v4"),
        athena_s3tables_catalog=os.environ.get(
            "AWS_ATHENA_S3TABLES_CATALOG",
            f"s3tablescatalog/{os.environ['AWS_S3_TABLE_BUCKET_NAME']}",
        ),
        lineage_ingress_bucket_name=os.environ.get("AWS_S3_LINEAGE_INGRESS_BUCKET_NAME"),
        lineage_ingress_prefix=os.environ.get("AWS_S3_LINEAGE_INGRESS_PREFIX", "lineage-events/"),
        vector_bucket_name=os.environ["AWS_S3_VECTOR_BUCKET_NAME"],
        vector_index_name=os.environ.get("AWS_S3_VECTOR_INDEX_NAME", "memories-v1"),
        embedding_model_id=os.environ.get(
            "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
        ),
        retrieval_policy=RetrievalPolicy(
            policy_id=build_policy_id(
                name=os.environ.get("MEMORY_RETRIEVAL_POLICY_NAME", "retrieval-default"),
                version=os.environ.get("MEMORY_RETRIEVAL_POLICY_VERSION", "1.0.0"),
                effective_at=os.environ.get("MEMORY_RETRIEVAL_POLICY_EFFECTIVE_AT", "2026-05-07T00:00:00Z"),
            ),
            version=os.environ.get("MEMORY_RETRIEVAL_POLICY_VERSION", "1.0.0"),
            effective_at=os.environ.get("MEMORY_RETRIEVAL_POLICY_EFFECTIVE_AT", "2026-05-07T00:00:00Z"),
            eligibility_threshold=float(os.environ.get("MEMORY_RETRIEVAL_ELIGIBILITY_THRESHOLD", "0.2")),
            quarantine_risk_threshold=float(os.environ.get("MEMORY_QUARANTINE_RISK_THRESHOLD", "0.8")),
        ),
    )
