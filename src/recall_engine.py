from __future__ import annotations

from .conflict_engine import contradiction_flag
from .eligibility_engine import is_eligible, score_candidate
from .embeddings import BedrockEmbeddings
from .lineage_engine import LineageEngine
from .policy import RejectionReason, RetrievalPolicy
from .time_engine import decay_score
from .vectors import RecallVectors


class RecallEngine:
    def __init__(
        self,
        *,
        vectors: RecallVectors,
        embedder: BedrockEmbeddings,
        lineage: LineageEngine,
        policy: RetrievalPolicy,
    ) -> None:
        self.vectors = vectors
        self.embedder = embedder
        self.lineage = lineage
        self.policy = policy

    def retrieve(self, *, agent_id: str, stream_id: str, query: str, top_k: int = 10) -> dict:
        query_vec = self.embedder.embed_text(query)
        response = self.vectors.query(
            vector=query_vec,
            top_k=top_k,
            agent_id=agent_id,
            stream_id=stream_id,
        )

        accepted: list[dict] = []
        rejected: list[dict] = []

        for hit in response.get("vectors", []):
            metadata = hit.get("metadata", {})
            relevance = 1.0 - float(hit.get("distance", 1.0))
            trust = float(metadata.get("source_trust", 0.5))
            recency = decay_score(hours_since_last_reinforced=float(metadata.get("hours_stale", 0.0)))
            reinforcement = float(metadata.get("reinforcement", 1.0))
            consistency = contradiction_flag(has_conflicts=bool(metadata.get("has_conflicts", False)))
            safety = float(metadata.get("safety", 1.0))

            s = score_candidate(
                relevance=relevance,
                trust=trust,
                recency=recency,
                reinforcement=reinforcement,
                consistency=consistency,
                safety=safety,
            )
            memory_id = hit.get("key", "unknown")

            if is_eligible(s, threshold=self.policy.eligibility_threshold):
                accepted.append({"memory_id": memory_id, "score": s})
                self.lineage.emit(
                    event_type="recalled",
                    agent_id=agent_id,
                    stream_id=stream_id,
                    memory_id=memory_id,
                    payload={
                        "query": query,
                        "eligibility_score": s,
                        **self.policy.audit_fields(),
                    },
                )
            else:
                reason = RejectionReason.ELIGIBILITY_BELOW_THRESHOLD.value
                rejected.append({"memory_id": memory_id, "score": s, "reason": reason})
                self.lineage.emit(
                    event_type="rejected",
                    agent_id=agent_id,
                    stream_id=stream_id,
                    memory_id=memory_id,
                    payload={
                        "query": query,
                        "eligibility_score": s,
                        "reason": reason,
                        **self.policy.audit_fields(),
                    },
                )

        return {"accepted": accepted, "rejected": rejected, "raw": response}
