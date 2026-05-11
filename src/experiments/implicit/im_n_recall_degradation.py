from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.eligibility import eligibility_gate


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-n"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    healthy = eligibility_gate(
        relevance=0.9,
        trust=0.8,
        recency=0.95,
        reinforcement=0.9,
        consistency=0.85,
        safety=0.9,
        threshold=0.3,
        gate_mode="per_axis",
        claim_threshold=0.4,
        recall_process_threshold=0.4,
        provenance_chain_threshold=0.2,
        parent_chain_depth=1.0,
        source_diversity=0.8,
        age_of_original_source=4.0,
    )
    degraded = eligibility_gate(
        relevance=0.9,
        trust=0.8,
        recency=0.15,
        reinforcement=0.2,
        consistency=0.5,
        safety=0.9,
        threshold=0.3,
        gate_mode="per_axis",
        claim_threshold=0.4,
        recall_process_threshold=0.4,
        provenance_chain_threshold=0.2,
        parent_chain_depth=1.0,
        source_diversity=0.8,
        age_of_original_source=4.0,
    )

    emit(
        lineage,
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="n-healthy",
        payload={
            "snapshot_type": "axis_stress_recall_degradation",
            "allow_influence": healthy.allow_influence,
            "uncertainty_triple": {
                "confidence_in_claim": healthy.uncertainty_triple.confidence_in_claim,
                "confidence_in_recall_process": healthy.uncertainty_triple.confidence_in_recall_process,
                "confidence_in_provenance_chain": healthy.uncertainty_triple.confidence_in_provenance_chain,
            },
            "dominant_axis": healthy.dominant_axis,
        },
    )
    emit(
        lineage,
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="n-degraded",
        payload={
            "snapshot_type": "axis_stress_recall_degradation",
            "allow_influence": degraded.allow_influence,
            "uncertainty_triple": {
                "confidence_in_claim": degraded.uncertainty_triple.confidence_in_claim,
                "confidence_in_recall_process": degraded.uncertainty_triple.confidence_in_recall_process,
                "confidence_in_provenance_chain": degraded.uncertainty_triple.confidence_in_provenance_chain,
            },
            "dominant_axis": degraded.dominant_axis,
        },
    )

    pass_case = healthy.allow_influence and (not degraded.allow_influence) and degraded.dominant_axis == "recall_process"
    summary = {
        "suite": "N",
        "healthy_allow": healthy.allow_influence,
        "degraded_allow": degraded.allow_influence,
        "degraded_dominant_axis": degraded.dominant_axis,
        "pass": pass_case,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
