from __future__ import annotations

from typing import Any

from memory_lab.cloud_service import S3MemoryLabService
from memory_lab.config import Settings, load_dotenv


def handler(_event: dict[str, Any], _context: Any) -> dict[str, Any]:
    load_dotenv()
    settings = Settings.from_env()
    cloud = S3MemoryLabService(
        events_bucket=settings.aws_events_bucket_name,
        state_bucket=settings.aws_state_bucket_name,
        vector_bucket=settings.aws_vector_bucket_name,
        vector_index_name=settings.aws_vector_index_name,
        region=settings.aws_region,
    )
    cloud._materialize()
    return {"ok": True, "compaction_outputs": [], "memory_count": len(cloud.beliefs_current())}
