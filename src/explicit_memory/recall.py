from __future__ import annotations

from src.embeddings import BedrockEmbeddings
from src.epistemic_triangle import memory_subject_placeholder
from src.explicit_memory.claim import compute_claim_signals
from src.explicit_memory.recall_signals import compute_recall_signals
from src.explicit_memory.signals import (
    NormalizedSignals,
    SignalMethod,
    SignalSource,
)
from src.lineage_engine import LineageEngine
from src.policy import RejectionReason, RetrievalPolicy, SuspicionTag, ThreatLabel
from src.time_engine import decay_score
from src.vectors import RecallVectors

from .conflict import contradiction_flag
from .eligibility import UncertaintyTriple, evaluate_uncertainty_gate, score_triple


# Fixed bootstrap moment for in-RecallEngine signal walkers when no
# tick TAI is plumbed in. Replay-deterministic; never wall-clock.
# Same anchor InMemoryLineageEngine uses by default.
_RECALL_TICK_TAI_ANCHOR = "2026-05-13T12:00:00.000"


def _build_v7_axis_signals(
    *,
    memory_id: str,
    agent_id: str,
    parent_chain_depth: float,
    source_diversity: float,
    age_of_original_source: float,
    as_of_time: str = _RECALL_TICK_TAI_ANCHOR,
):
    """Construct the three NormalizedSignals the v7 gate expects.

    Spec §11: `signal is None` is only allowed on `schema_version < 7.0`
    paths. Explicit recall is a v7 emit path, so signals MUST be
    supplied. Mirrors `ImplicitControllerLoop._build_v7_axis_signals`.

    - **Provenance**: caller-extracted scalars packaged as
      `signal_source = "computed"`.
    - **Claim** / **Recall**: walkers called with empty link/recall
      inputs. RecallEngine doesn't currently have a lineage reader
      in scope, so the walkers return fallback signals
      (`no_evidence_links`, `first_recall`). The gate applies the
      fallback multiplier and the per-axis markers surface in
      payload. Phase 5 plumbs real walkers when RecallEngine gains
      lineage-reader access.
    """
    claim_target = {
        "event_id": f"recall-target:{memory_id}",
        "agent_id": agent_id,
        "assertion_kind": "claim",
    }
    claim = compute_claim_signals(
        target_event=claim_target,
        link_events=[],
        evidence_events={},
        as_of_time=as_of_time,
    )
    recall_target = {
        "event_type": "recalled",
        "memory_id": memory_id,
        "agent_id": agent_id,
        "assertion_kind": "memory",
        "physical_moment": {"tai_iso": as_of_time, "solar_age_myr": 0.0},
        "payload": {},
    }
    recall = compute_recall_signals(
        target_event=recall_target,
        prior_recall_events=[],
        as_of_time=as_of_time,
    )
    prov = NormalizedSignals(
        signal_source=SignalSource.COMPUTED,
        signal_method=SignalMethod.PROVENANCE_CHAIN,
        fallback_reason=None,
        values={
            "parent_chain_depth": float(parent_chain_depth),
            "source_diversity": float(source_diversity),
            "age_of_original_source": float(age_of_original_source),
        },
    )
    return claim, recall, prov


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
                # v7 EPISTEMIC_TRIANGLE §3.3 + promotion-review
                # caution #3: decision events carrying uncertainty
                # triples require subject classification. We use the
                # documented deterministic placeholder pattern.
                subject = memory_subject_placeholder(memory_id)
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
                        "subject_kind_source": "v1_default",
                        # v7 §11.1: explicit recall is a v7 emit
                        # path; mark scoring_function so audits can
                        # verify score_candidate retirement.
                        "scoring_function": "score_triple",
                        **self.policy.audit_fields(),
                    },
                    **subject,
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
            age_of_original_source = float(
                metadata.get(
                    "age_of_original_source",
                    metadata.get("age_of_original_source_hours", metadata.get("hours_stale", 0.0)),
                )
            )
            # v7 EPISTEMIC_TRIANGLE §11: supply normalized axis
            # signals to score_triple. `signal is None` mode is
            # only allowed on pre-v7 paths; explicit recall is a
            # v7 emit path. With no in-scope lineage reader for
            # claim links or prior recalls, those axes return
            # fallback signals — visible per-axis in the payload.
            claim_signals, recall_signals, prov_signals = _build_v7_axis_signals(
                memory_id=memory_id,
                agent_id=agent_id,
                parent_chain_depth=parent_chain_depth,
                source_diversity=source_diversity,
                age_of_original_source=age_of_original_source,
            )
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
                claim_signals=claim_signals,
                recall_signals=recall_signals,
                provenance_signals=prov_signals,
            )
            # v7 EPISTEMIC_TRIANGLE §11.1: `score_candidate` is
            # retired on v7 event-emitting paths, including recall.
            # The gate score is triple.combined(); every v7 decision
            # payload carries `scoring_function: "score_triple"` so
            # audits can verify retirement at decision time, not
            # just by static check.
            s = triple.combined()
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
                # `recalled` is record_kind=memory_event; spec §3.3
                # does NOT require subject classification for
                # memory events (the event IS the subject). Validator
                # checks (decision_event + triple), not just triple.
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
                        "scoring_function": "score_triple",
                        # v7 §11 per-axis fallback visibility. With
                        # no in-scope lineage reader, claim/recall
                        # axes typically fall back here; the markers
                        # surface that to audits.
                        "axis_fallback_used": dict(triple.axis_fallback_used),
                        "axis_fallback_reasons": dict(triple.axis_fallback_reasons),
                        "policy_fallback_multiplier": triple.policy_fallback_multiplier,
                        **self.policy.audit_fields(),
                    },
                )
            else:
                reason = RejectionReason.ELIGIBILITY_BELOW_THRESHOLD.value
                rejected.append({"memory_id": memory_id, "score": s, "reason": reason})
                # `rejected` is record_kind=decision_event carrying
                # an uncertainty_triple. v7 §3.3 + promotion-review
                # caution #3 require subject classification via the
                # documented placeholder pattern.
                subject = memory_subject_placeholder(memory_id)
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
                        "scoring_function": "score_triple",
                        # v7 §11 per-axis fallback visibility. With
                        # no in-scope lineage reader, claim/recall
                        # axes typically fall back here; the markers
                        # surface that to audits.
                        "axis_fallback_used": dict(triple.axis_fallback_used),
                        "axis_fallback_reasons": dict(triple.axis_fallback_reasons),
                        "policy_fallback_multiplier": triple.policy_fallback_multiplier,
                        "reason": reason,
                        "subject_kind_source": "v1_default",
                        **self.policy.audit_fields(),
                    },
                    **subject,
                )

        return {"accepted": accepted, "rejected": rejected, "raw": response}


__all__ = ["RecallEngine"]
