from __future__ import annotations

from src.embeddings import BedrockEmbeddings
from src.lineage_engine import LineageEngine
from src.policy import RejectionReason, RetrievalPolicy, SuspicionTag, ThreatLabel
from src.time_engine import decay_score
from src.vectors import RecallVectors

from .conflict import contradiction_flag
from .eligibility import is_eligible, score_candidate


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
        )

        accepted: list[dict] = []
        rejected: list[dict] = []

        for hit in response.get("vectors", []):
            metadata = hit.get("metadata", {})
            metadata_agent_id = metadata.get("agent_id")
            metadata_stream_id = metadata.get("stream_id")
            memory_id = hit.get("key", "unknown")

            if metadata_agent_id not in {None, agent_id} or metadata_stream_id not in {None, stream_id}:
                reason = RejectionReason.CROSS_SCOPE_REFERENCE_ATTEMPT.value
                rejected.append({"memory_id": memory_id, "score": 0.0, "reason": reason})
                self.lineage.emit(
                    event_type="rejected",
                    agent_id=agent_id,
                    stream_id=stream_id,
                    memory_id=memory_id,
                    actor_class="retrieval_engine",
                    source_class="vector_index",
                    payload={
                        "query": query,
                        "eligibility_score": 0.0,
                        "reason": reason,
                        "candidate_agent_id": metadata_agent_id,
                        "candidate_stream_id": metadata_stream_id,
                        "suspicion_tags": [SuspicionTag.CROSS_SCOPE_INFLUENCE_ATTEMPT.value],
                        "threat_labels": [ThreatLabel.SCOPE_ESCAPE_ATTEMPT.value],
                        **self.policy.audit_fields(),
                    },
                )
                continue

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
            if is_eligible(s, threshold=self.policy.eligibility_threshold):
                accepted.append({"memory_id": memory_id, "score": s})
                self.lineage.emit(
                    event_type="recalled",
                    agent_id=agent_id,
                    stream_id=stream_id,
                    memory_id=memory_id,
                    actor_class="retrieval_engine",
                    source_class="vector_index",
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
                    actor_class="retrieval_engine",
                    source_class="vector_index",
                    payload={
                        "query": query,
                        "eligibility_score": s,
                        "reason": reason,
                        **self.policy.audit_fields(),
                    },
                )

        return {"accepted": accepted, "rejected": rejected, "raw": response}


__all__ = ["RecallEngine"]
