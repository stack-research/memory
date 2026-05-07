from __future__ import annotations

from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.lineage_engine import LineageEngine
from src.recall_engine import RecallEngine
from src.storage import LineageStorage
from src.vectors import RecallVectors



def run() -> None:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = LineageEngine(storage)
    recall = RecallEngine(vectors=vectors, embedder=embedder, lineage=lineage)

    agent_id = "lab-agent-1"
    stream_id = "exp-e4"

    claim_a_id = "mem-e4-claim-a"
    claim_b_id = "mem-e4-claim-b"

    claim_a = "Feature flag rollout reached 100 percent of users on Tuesday."
    claim_b = "Feature flag rollout was paused at 40 percent on Tuesday due to incident risk."

    vec_a = embedder.embed_text(claim_a)
    vec_b = embedder.embed_text(claim_b)

    vectors.put_memory_vector(
        key=claim_a_id,
        vector=vec_a,
        metadata={
            "source_trust": 0.82,
            "reinforcement": 1.1,
            "status": "active",
            "kind": "claim",
            "has_conflicts": True,
            "safety": 1.0,
            "agent_id": agent_id,
            "stream_id": stream_id,
        },
    )
    vectors.put_memory_vector(
        key=claim_b_id,
        vector=vec_b,
        metadata={
            "source_trust": 0.79,
            "reinforcement": 1.2,
            "status": "active",
            "kind": "claim",
            "has_conflicts": True,
            "safety": 1.0,
            "agent_id": agent_id,
            "stream_id": stream_id,
        },
    )

    e1 = lineage.emit(
        event_type="observed",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=claim_a_id,
        payload={"claim": claim_a, "source": "ops-dashboard"},
    )
    e2 = lineage.emit(
        event_type="observed",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=claim_b_id,
        payload={"claim": claim_b, "source": "incident-channel"},
    )
    lineage.emit(
        event_type="contradicted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=claim_a_id,
        parent_event_id=e1.event_id,
        payload={
            "conflict_with": claim_b_id,
            "relation": "contradicts",
            "confidence": 0.88,
            "evidence_event_id": e2.event_id,
        },
    )
    lineage.emit(
        event_type="contradicted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=claim_b_id,
        parent_event_id=e2.event_id,
        payload={
            "conflict_with": claim_a_id,
            "relation": "contradicts",
            "confidence": 0.88,
            "evidence_event_id": e1.event_id,
        },
    )

    queries = [
        "Did the rollout complete on Tuesday?",
        "Was the rollout paused before full release?",
        "Summarize rollout status under uncertainty.",
    ]

    for q in queries:
        result = recall.retrieve(agent_id=agent_id, stream_id=stream_id, query=q, top_k=5)
        print({"query": q, "accepted": result["accepted"], "rejected": result["rejected"]})


if __name__ == "__main__":
    run()
