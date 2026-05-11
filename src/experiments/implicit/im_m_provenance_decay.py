from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.eligibility import eligibility_gate


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-m"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    baseline = eligibility_gate(
        relevance=0.9,
        trust=0.85,
        recency=0.9,
        reinforcement=0.9,
        consistency=0.9,
        safety=0.9,
        threshold=0.3,
        gate_mode="per_axis",
        claim_threshold=0.4,
        recall_process_threshold=0.4,
        provenance_chain_threshold=0.25,
        parent_chain_depth=0.0,
        source_diversity=0.9,
        age_of_original_source=2.0,
    )
    decayed = eligibility_gate(
        relevance=0.9,
        trust=0.85,
        recency=0.9,
        reinforcement=0.9,
        consistency=0.9,
        safety=0.9,
        threshold=0.3,
        gate_mode="per_axis",
        claim_threshold=0.4,
        recall_process_threshold=0.4,
        provenance_chain_threshold=0.25,
        parent_chain_depth=8.0,
        source_diversity=0.1,
        age_of_original_source=720.0,
    )

    emit(
        lineage,
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="m-baseline",
        payload={
            "snapshot_type": "axis_stress_provenance_decay",
            "allow_influence": baseline.allow_influence,
            "uncertainty_triple": {
                "confidence_in_claim": baseline.uncertainty_triple.confidence_in_claim,
                "confidence_in_recall_process": baseline.uncertainty_triple.confidence_in_recall_process,
                "confidence_in_provenance_chain": baseline.uncertainty_triple.confidence_in_provenance_chain,
            },
            "dominant_axis": baseline.dominant_axis,
        },
    )
    emit(
        lineage,
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="m-decayed",
        payload={
            "snapshot_type": "axis_stress_provenance_decay",
            "allow_influence": decayed.allow_influence,
            "uncertainty_triple": {
                "confidence_in_claim": decayed.uncertainty_triple.confidence_in_claim,
                "confidence_in_recall_process": decayed.uncertainty_triple.confidence_in_recall_process,
                "confidence_in_provenance_chain": decayed.uncertainty_triple.confidence_in_provenance_chain,
            },
            "dominant_axis": decayed.dominant_axis,
        },
    )

    pass_case = baseline.allow_influence and (not decayed.allow_influence) and decayed.dominant_axis == "provenance_chain"
    summary = {
        "suite": "M",
        "baseline_allow": baseline.allow_influence,
        "decayed_allow": decayed.allow_influence,
        "decayed_dominant_axis": decayed.dominant_axis,
        "pass": pass_case,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
