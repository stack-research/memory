from __future__ import annotations

from typing import Any

from .aws_session import make_session
from .config import AwsConfig


class RecallVectors:
    def __init__(self, cfg: AwsConfig) -> None:
        self.cfg = cfg
        self.client = make_session(cfg).client("s3vectors")

    def put_memory_vector(self, *, key: str, vector: list[float], metadata: dict[str, Any]) -> None:
        self.client.put_vectors(
            vectorBucketName=self.cfg.vector_bucket_name,
            indexName=self.cfg.vector_index_name,
            vectors=[{"key": key, "data": {"float32": vector}, "metadata": metadata}],
        )

    def query(self, *, vector: list[float], top_k: int = 10, filter_text: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "vectorBucketName": self.cfg.vector_bucket_name,
            "indexName": self.cfg.vector_index_name,
            "queryVector": {"float32": vector},
            "topK": top_k,
            "returnMetadata": True,
            "returnDistance": True,
        }
        if filter_text:
            kwargs["filter"] = filter_text
        return self.client.query_vectors(**kwargs)
