from __future__ import annotations

import math
from statistics import median

from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.lineage_engine import LineageEngine
from src.storage import LineageStorage
from src.vectors import RecallVectors


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _mutate_claim(*, current_claim: str, context: str, step: int) -> str:
    return f"{current_claim} [context={context}; reconsolidation_step={step}]"


def run() -> dict:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = LineageEngine(storage)

    agent_id = "lab-agent-1"
    stream_id = "exp-e10"
    memory_id = "mem-e10-core"

    contexts = [
        "neutral_summary",
        "incident_urgency",
        "blameless_postmortem",
        "executive_brief",
        "customer_support_rephrase",
        "retrospective",
    ]

    base_claim = "Customer experienced duplicate billing after payment retry race condition."
    base_embedding = embedder.embed_text(base_claim)

    lineage.emit(
        event_type="observed",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload={"claim": base_claim, "kind": "episodic"},
    )

    current_claim = base_claim
    current_embedding = base_embedding
    cosine_prev_series: list[float] = []
    cosine_base_series: list[float] = []

    for step, context in enumerate(contexts, start=1):
        recalled_event = lineage.emit(
            event_type="recalled",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            payload={
                "context": context,
                "claim_before": current_claim,
                **cfg.retrieval_policy.audit_fields(),
            },
        )

        mutated_claim = _mutate_claim(current_claim=current_claim, context=context, step=step)
        mutated_embedding = embedder.embed_text(mutated_claim)

        cosine_prev = _cosine_similarity(current_embedding, mutated_embedding)
        cosine_base = _cosine_similarity(base_embedding, mutated_embedding)
        cosine_prev_series.append(cosine_prev)
        cosine_base_series.append(cosine_base)

        lineage.emit(
            event_type="mutated",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            parent_event_id=recalled_event.event_id,
            payload={
                "context": context,
                "step": step,
                "claim_before": current_claim,
                "claim_after": mutated_claim,
                "drift": {
                    "cosine_similarity_to_previous": cosine_prev,
                    "cosine_similarity_to_base": cosine_base,
                },
            },
        )

        vectors.put_memory_vector(
            key=memory_id,
            vector=mutated_embedding,
            metadata={
                "agent_id": agent_id,
                "stream_id": stream_id,
                "kind": "episodic",
                "status": "active",
                "source_trust": 0.72,
                "reinforcement": 1.0 + (step * 0.15),
                "stability_step": step,
            },
        )

        current_claim = mutated_claim
        current_embedding = mutated_embedding

    median_cosine_prev = median(cosine_prev_series) if cosine_prev_series else 0.0
    final_cosine_base = cosine_base_series[-1] if cosine_base_series else 0.0

    summary = {
        "stream_id": stream_id,
        "memory_id": memory_id,
        "steps": len(contexts),
        "median_cosine_to_previous": median_cosine_prev,
        "final_cosine_to_base": final_cosine_base,
        "pass_median_prev": median_cosine_prev >= 0.85,
        "pass_final_base": final_cosine_base >= 0.60,
        "pass": (median_cosine_prev >= 0.85) and (final_cosine_base >= 0.60),
    }

    lineage.emit(
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="e10-summary",
        payload={
            "snapshot_type": "reconsolidation_stability",
            "snapshot_stage": "final",
            **summary,
            **cfg.retrieval_policy.audit_fields(),
        },
    )

    print(summary)
    return summary


if __name__ == "__main__":
    run()
