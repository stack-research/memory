from __future__ import annotations

import math
from dataclasses import dataclass

from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.experiments.engine_helper import make_experiment_engine
from src.storage import LineageStorage
from src.vectors import RecallVectors


@dataclass
class RecallContext:
    label: str
    query: str
    pressure: str
    trust_delta: float
    confidence_delta: float


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _mutate_claim(*, current_claim: str, pressure: str, step: int) -> str:
    return f"{current_claim} [recalled under {pressure}; revision_step={step}]"


def run() -> None:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = make_experiment_engine(storage)

    agent_id = "lab-agent-1"
    stream_id = "exp-e2"
    vectors.set_lineage_context(lineage=lineage, agent_id=agent_id, stream_id=stream_id)
    memory_id = "mem-drift-e2"

    contexts = [
        RecallContext(
            label="baseline",
            query="What was the customer issue?",
            pressure="neutral_summary",
            trust_delta=0.0,
            confidence_delta=0.0,
        ),
        RecallContext(
            label="urgency",
            query="What urgent failure happened in production?",
            pressure="incident_escalation",
            trust_delta=-0.05,
            confidence_delta=0.03,
        ),
        RecallContext(
            label="blameless",
            query="How should we describe the same incident in a blameless postmortem?",
            pressure="blameless_postmortem",
            trust_delta=0.02,
            confidence_delta=-0.04,
        ),
        RecallContext(
            label="executive",
            query="Give the executive one-line reality of what happened.",
            pressure="executive_compression",
            trust_delta=-0.02,
            confidence_delta=0.01,
        ),
    ]

    base_claim = "Customer reported data loss after a failed sync in mobile app version 4.2."
    current_claim = base_claim
    current_trust = 0.72
    current_confidence = 0.66
    reinforcement = 1.0

    base_embedding = embedder.embed_text(base_claim)
    current_embedding = base_embedding

    vectors.put_memory_vector(
        key=memory_id,
        vector=current_embedding,
        metadata={
            "source_trust": current_trust,
            "confidence": current_confidence,
            "reinforcement": reinforcement,
            "status": "active",
            "kind": "episodic",
            "drift_step": 0,
            "agent_id": agent_id,
            "stream_id": stream_id,
        },
    )

    observed_event = lineage.emit(
        event_type="observed",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload={"claim": base_claim, "source": "incident_ticket"},
    )
    print(observed_event)

    parent_event_id = observed_event.event_id

    for step, ctx in enumerate(contexts, start=1):
        recall_query_embedding = embedder.embed_text(ctx.query)
        hits = vectors.query(
            vector=recall_query_embedding,
            top_k=3,
            agent_id=agent_id,
            stream_id=stream_id,
        )

        recalled_event = lineage.emit(
            event_type="recalled",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            parent_event_id=parent_event_id,
            payload={
                "context": ctx.label,
                "query": ctx.query,
                "top_hit": hits.get("vectors", [{}])[0],
                "claim_before_mutation": current_claim,
                "uncertainty_triple": {
                    "confidence_in_claim": 1.0,
                    "confidence_in_recall_process": 1.0,
                    "confidence_in_provenance_chain": 1.0,
                },
                "combined_score": 1.0,
                "dominant_axis": "claim",
                **cfg.retrieval_policy.audit_fields(),
            },
        )

        mutated_claim = _mutate_claim(current_claim=current_claim, pressure=ctx.pressure, step=step)
        mutated_embedding = embedder.embed_text(mutated_claim)

        current_trust = max(0.05, min(0.99, current_trust + ctx.trust_delta))
        current_confidence = max(0.05, min(0.99, current_confidence + ctx.confidence_delta))
        reinforcement += 0.25

        vectors.put_memory_vector(
            key=memory_id,
            vector=mutated_embedding,
            metadata={
                "source_trust": current_trust,
                "confidence": current_confidence,
                "reinforcement": reinforcement,
                "status": "active",
                "kind": "episodic",
                "drift_step": step,
                "context": ctx.label,
                "agent_id": agent_id,
                "stream_id": stream_id,
            },
        )

        sim_base = _cosine_similarity(base_embedding, mutated_embedding)
        sim_prev = _cosine_similarity(current_embedding, mutated_embedding)

        mutated_event = lineage.emit(
            event_type="mutated",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            parent_event_id=recalled_event.event_id,
            payload={
                "context": ctx.label,
                "pressure": ctx.pressure,
                "claim_before": current_claim,
                "claim_after": mutated_claim,
                "trust_after": current_trust,
                "confidence_after": current_confidence,
                "reinforcement_after": reinforcement,
                "drift": {
                    "cosine_similarity_to_base": sim_base,
                    "cosine_similarity_to_previous": sim_prev,
                },
            },
        )

        current_claim = mutated_claim
        current_embedding = mutated_embedding
        parent_event_id = mutated_event.event_id
        print(mutated_event)

    print(
        {
            "memory_id": memory_id,
            "final_claim": current_claim,
            "final_trust": current_trust,
            "final_confidence": current_confidence,
            "total_reinforcement": reinforcement,
            "drift_from_base": 1.0 - _cosine_similarity(base_embedding, current_embedding),
        }
    )


if __name__ == "__main__":
    run()
