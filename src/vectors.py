from __future__ import annotations

from typing import Any

from .aws_session import make_session
from .config import AwsConfig


class RecallVectors:
    def __init__(self, cfg: AwsConfig) -> None:
        self.cfg = cfg
        self.client = make_session(cfg).client("s3vectors")
        self._lineage = None
        self._lineage_agent_id: str | None = None
        self._lineage_stream_id: str | None = None

    def set_lineage_context(self, *, lineage, agent_id: str, stream_id: str) -> None:
        self._lineage = lineage
        self._lineage_agent_id = agent_id
        self._lineage_stream_id = stream_id

    def delete_memory_vectors(self, keys: list[str]) -> None:
        if not keys:
            return
        self.client.delete_vectors(
            vectorBucketName=self.cfg.vector_bucket_name,
            indexName=self.cfg.vector_index_name,
            keys=keys,
        )

    def put_memory_vector(self, *, key: str, vector: list[float], metadata: dict[str, Any]) -> None:
        merged = dict(metadata)
        if "parent_chain_depth" not in merged:
            merged["parent_chain_depth"] = 0.0
        if "source_diversity" not in merged:
            merged["source_diversity"] = 1.0

        if "age_of_original_source" in merged:
            age = float(merged["age_of_original_source"])
        elif "age_of_original_source_hours" in merged:
            age = float(merged["age_of_original_source_hours"])
        elif "hours_stale" in merged:
            age = float(merged["hours_stale"])
        else:
            age = 0.0

        merged["age_of_original_source"] = max(0.0, age)
        merged["provenance_signal_source"] = merged.get("provenance_signal_source", "computed")

        self.client.put_vectors(
            vectorBucketName=self.cfg.vector_bucket_name,
            indexName=self.cfg.vector_index_name,
            vectors=[{"key": key, "data": {"float32": vector}, "metadata": merged}],
        )

        if self._lineage is not None and self._lineage_agent_id and self._lineage_stream_id:
            self._lineage.emit(
                event_type="provenance_signals_written_to_vector",
                agent_id=self._lineage_agent_id,
                stream_id=self._lineage_stream_id,
                memory_id=key,
                actor_class="retrieval_engine",
                source_class="vector_index",
                payload={
                    "provenance_signals": {
                        "parent_chain_depth": merged["parent_chain_depth"],
                        "source_diversity": merged["source_diversity"],
                        "age_of_original_source": merged["age_of_original_source"],
                    },
                    "chain_root_event_id": merged.get("chain_root_event_id"),
                    "chain_length": merged.get("chain_length"),
                    "distinct_source_classes": merged.get("distinct_source_classes"),
                    "computed_at": merged.get("computed_at"),
                    "as_of_time": merged.get("as_of_time"),
                    "fallback_reason": merged.get("fallback_reason"),
                    "provenance_signal_source": merged.get("provenance_signal_source", "computed"),
                },
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
