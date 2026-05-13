from __future__ import annotations

from statistics import mean

from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.lineage_engine import LineageEngine
from src.storage import LineageStorage
from src.vectors import RecallVectors



def run() -> None:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = LineageEngine(storage)

    agent_id = "lab-agent-1"
    stream_id = "exp-e5"
    vectors.set_lineage_context(lineage=lineage, agent_id=agent_id, stream_id=stream_id)

    episodic_ids = [
        "mem-e5-ep-1",
        "mem-e5-ep-2",
        "mem-e5-ep-3",
        "mem-e5-ep-4",
    ]
    episodic_claims = [
        "User repeatedly asks for automatic invoice reminders every month.",
        "User enabled reminder notifications after missing an invoice due date.",
        "User confirmed monthly reminders reduce late payment risk.",
        "User asked support to keep invoice reminders enabled by default.",
    ]

    for memory_id, claim in zip(episodic_ids, episodic_claims):
        vec = embedder.embed_text(claim)
        vectors.put_memory_vector(
            key=memory_id,
            vector=vec,
            metadata={
                "agent_id": agent_id,
                "stream_id": stream_id,
                "kind": "episodic",
                "status": "active",
                "source_trust": 0.78,
                "confidence": 0.72,
                "reinforcement": 1.4,
                "supports_cluster": "invoice-reminders",
            },
        )
        lineage.emit(
            event_type="observed",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            payload={"claim": claim, "kind": "episodic"},
        )

    # Sleep-like consolidation heuristic for v0 lab
    access_count = 12
    context_variance = 0.11
    promotion_threshold_k = 8
    promotion_threshold_epsilon = 0.2

    promote = access_count > promotion_threshold_k and context_variance < promotion_threshold_epsilon
    lineage.emit(
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="cluster-invoice-reminders",
        payload={
            "cluster": "invoice-reminders",
            "access_count": access_count,
            "context_variance": context_variance,
            "promotion_eligible": promote,
        },
    )

    if not promote:
        print({"promoted": False, "reason": "threshold_not_met"})
        return

    semantic_memory_id = "mem-e5-semantic-1"
    semantic_claim = "User prefers monthly invoice reminders to avoid late payments."
    semantic_vec = embedder.embed_text(semantic_claim)

    mean_trust = mean([0.78, 0.78, 0.78, 0.78])
    mean_confidence = mean([0.72, 0.72, 0.72, 0.72])

    vectors.put_memory_vector(
        key=semantic_memory_id,
        vector=semantic_vec,
        metadata={
            "agent_id": agent_id,
            "stream_id": stream_id,
            "kind": "semantic",
            "status": "active",
            "source_trust": mean_trust,
            "confidence": min(0.95, mean_confidence + 0.08),
            "reinforcement": 2.2,
            "derived_from_count": len(episodic_ids),
            "has_conflicts": False,
        },
    )

    promotion_event = lineage.emit(
        event_type="promoted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=semantic_memory_id,
        payload={
            "claim": semantic_claim,
            "kind": "semantic",
            "derived_from": episodic_ids,
            "access_count": access_count,
            "context_variance": context_variance,
        },
    )

    for episodic_id in episodic_ids:
        lineage.emit(
            event_type="mutated",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=episodic_id,
            parent_event_id=promotion_event.event_id,
            payload={
                "promotion_link": semantic_memory_id,
                "relation": "derived_from",
                "status_after": "active",
            },
        )

    print(
        {
            "promoted": True,
            "semantic_memory_id": semantic_memory_id,
            "derived_from": episodic_ids,
            "access_count": access_count,
            "context_variance": context_variance,
        }
    )


if __name__ == "__main__":
    run()
