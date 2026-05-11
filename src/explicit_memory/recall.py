from __future__ import annotations

from src.embeddings import BedrockEmbeddings
from src.lineage_engine import LineageEngine
from src.policy import RejectionReason, RetrievalPolicy, SuspicionTag, ThreatLabel
from src.time_engine import decay_score
from src.vectors import RecallVectors

from .conflict import contradiction_flag
from .eligibility import UncertaintyTriple, evaluate_uncertainty_gate, score_candidate, score_triple


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
                zero_triple = UncertaintyTriple(
                    confidence_in_claim=0.0,
                    confidence_in_recall_process=0.0,
                    confidence_in_provenance_chain=0.0,
                )
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
                        "uncertainty_triple": {
                            "confidence_in_claim": zero_triple.confidence_in_claim,
                            "confidence_in_recall_process": zero_triple.confidence_in_recall_process,
                            "confidence_in_provenance_chain": zero_triple.confidence_in_provenance_chain,
                        },
                        "combined_score": zero_triple.combined(),
                        "dominant_axis": zero_triple.dominant_axis(),
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

            parent_chain_depth = float(metadata.get("parent_chain_depth", 0.0))
            source_diversity = float(metadata.get("source_diversity", 1.0))
            age_of_original_source = float(metadata.get("age_of_original_source", metadata.get("hours_stale", 0.0)))
            triple = score_triple(
                relevance=relevance,
                trust=trust,
                recency=recency,
                reinforcement=reinforcement,
                consistency=consistency,
                safety=safety,
                parent_chain_depth=parent_chain_depth,
                source_diversity=source_diversity,
                age_of_original_source=age_of_original_source,
            )
            s = score_candidate(
                relevance=relevance,
                trust=trust,
                recency=recency,
                reinforcement=reinforcement,
                consistency=consistency,
                safety=safety,
            )
            eligible, gate_mode = evaluate_uncertainty_gate(
                legacy_score=s,
                triple=triple,
                safety=safety,
                gate_mode=self.policy.uncertainty_gate_mode,
                threshold=self.policy.eligibility_threshold,
                combined_threshold=self.policy.uncertainty_combined_threshold,
                claim_threshold=self.policy.uncertainty_claim_threshold,
                recall_process_threshold=self.policy.uncertainty_recall_process_threshold,
                provenance_chain_threshold=self.policy.uncertainty_provenance_chain_threshold,
                safety_floor=self.policy.uncertainty_safety_floor,
            )

            if eligible:
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
                        "uncertainty_triple": {
                            "confidence_in_claim": triple.confidence_in_claim,
                            "confidence_in_recall_process": triple.confidence_in_recall_process,
                            "confidence_in_provenance_chain": triple.confidence_in_provenance_chain,
                        },
                        "combined_score": triple.combined(),
                        "dominant_axis": triple.dominant_axis(),
                        "provenance_signals": {
                            "parent_chain_depth": parent_chain_depth,
                            "source_diversity": source_diversity,
                            "age_of_original_source": age_of_original_source,
                        },
                        "uncertainty_gate_mode": gate_mode,
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
                        "uncertainty_triple": {
                            "confidence_in_claim": triple.confidence_in_claim,
                            "confidence_in_recall_process": triple.confidence_in_recall_process,
                            "confidence_in_provenance_chain": triple.confidence_in_provenance_chain,
                        },
                        "combined_score": triple.combined(),
                        "dominant_axis": triple.dominant_axis(),
                        "provenance_signals": {
                            "parent_chain_depth": parent_chain_depth,
                            "source_diversity": source_diversity,
                            "age_of_original_source": age_of_original_source,
                        },
                        "uncertainty_gate_mode": gate_mode,
                        "reason": reason,
                        **self.policy.audit_fields(),
                    },
                )

        return {"accepted": accepted, "rejected": rejected, "raw": response}


__all__ = ["RecallEngine"]
