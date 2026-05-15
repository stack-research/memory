from __future__ import annotations

from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.experiments.engine_helper import make_experiment_engine
from src.policy import QuarantineReason, SuspicionTag, ThreatLabel
from src.storage import LineageStorage
from src.vectors import RecallVectors



def run() -> None:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = make_experiment_engine(storage)

    agent_id = "lab-agent-1"
    stream_id = "exp-e6"
    vectors.set_lineage_context(lineage=lineage, agent_id=agent_id, stream_id=stream_id)

    poison_id = "mem-e6-poison"
    weak_true_id = "mem-e6-weak-true"

    poison_claim = "Customer explicitly opted out of security alerts and accepts risk."
    weak_true_claim = "Customer requested additional security alerts after suspicious login attempts."

    vectors.put_memory_vector(
        key=poison_id,
        vector=embedder.embed_text(poison_claim),
        metadata={
            "agent_id": agent_id,
            "stream_id": stream_id,
            "kind": "claim",
            "status": "active",
            "source_trust": 0.96,
            "confidence": 0.88,
            "reinforcement": 1.3,
            "has_conflicts": True,
        },
    )
    vectors.put_memory_vector(
        key=weak_true_id,
        vector=embedder.embed_text(weak_true_claim),
        metadata={
            "agent_id": agent_id,
            "stream_id": stream_id,
            "kind": "claim",
            "status": "active",
            "source_trust": 0.45,
            "confidence": 0.62,
            "reinforcement": 1.0,
            "has_conflicts": True,
        },
    )

    poison_observed = lineage.emit(
        event_type="observed",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=poison_id,
        payload={"claim": poison_claim, "source": "trusted_partner_feed"},
    )
    true_observed = lineage.emit(
        event_type="observed",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=weak_true_id,
        payload={"claim": weak_true_claim, "source": "support_ticket"},
    )

    lineage.emit(
        event_type="contradicted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=poison_id,
        parent_event_id=poison_observed.event_id,
        payload={
            "conflict_with": weak_true_id,
            "relation": "contradicts",
            "confidence": 0.91,
            "evidence_event_id": true_observed.event_id,
        },
    )

    # Pre-promotion gate: block poisoned candidate when trust is high but support is weak/conflicted
    risk_score = 0.93
    support_level = "low"
    conflict_density = "high"
    should_quarantine = risk_score > cfg.retrieval_policy.quarantine_risk_threshold
    suspicion_tags = [
        SuspicionTag.GOAL_HIJACK_SUSPECTED.value
        if support_level == "low" and conflict_density == "high"
        else SuspicionTag.CROSS_SCOPE_INFLUENCE_ATTEMPT.value
    ]
    threat_labels = [ThreatLabel.INFLUENCE_MANIPULATION.value]

    lineage.emit(
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=poison_id,
        payload={
            "promotion_candidate": True,
            "risk_score": risk_score,
            "support_level": support_level,
            "conflict_density": conflict_density,
            "suspicion_tags": suspicion_tags,
            "threat_labels": threat_labels,
            "should_quarantine": should_quarantine,
            **cfg.retrieval_policy.audit_fields(),
        },
    )

    if should_quarantine:
        lineage.emit(
            event_type="quarantined",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=poison_id,
            payload={
                "reason": QuarantineReason.HIGH_TRUST_LOW_SUPPORT_CONFLICT_CLUSTER.value,
                "eligibility_override": 0.0,
                "requires_release_event": True,
                "suspicion_tags": suspicion_tags,
                "threat_labels": threat_labels,
                **cfg.retrieval_policy.audit_fields(),
            },
        )
        vectors.put_memory_vector(
            key=poison_id,
            vector=embedder.embed_text(poison_claim),
            metadata={
                "agent_id": agent_id,
                "stream_id": stream_id,
                "kind": "claim",
                "status": "quarantined",
                "source_trust": 0.96,
                "confidence": 0.88,
                "reinforcement": 1.3,
                "has_conflicts": True,
                "safety": 0.0,
            },
        )
        print({"quarantined": True, "memory_id": poison_id, "risk_score": risk_score})
        return

    lineage.emit(
        event_type="promoted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=poison_id,
        payload={"claim": poison_claim, "unexpected": "promotion_not_expected"},
    )
    print({"quarantined": False, "promoted": True, "memory_id": poison_id})


if __name__ == "__main__":
    run()
