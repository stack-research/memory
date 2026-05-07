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

    def query(
        self,
        *,
        vector: list[float],
        top_k: int = 10,
        filter_text: str | None = None,
        agent_id: str | None = None,
        stream_id: str | None = None,
    ) -> dict[str, Any]:
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

        response = self.client.query_vectors(**kwargs)
        if not agent_id and not stream_id:
            return response

        filtered: list[dict[str, Any]] = []
        for row in response.get("vectors", []):
            metadata = row.get("metadata", {})
            if agent_id and metadata.get("agent_id") != agent_id:
                continue
            if stream_id and metadata.get("stream_id") != stream_id:
                continue
            filtered.append(row)

        response["vectors"] = filtered
        return response
