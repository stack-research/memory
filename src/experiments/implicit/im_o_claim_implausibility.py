from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.eligibility import eligibility_gate


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-o"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    plausible = eligibility_gate(
        relevance=0.9,
        trust=0.9,
        recency=0.9,
        reinforcement=0.9,
        consistency=0.9,
        safety=0.9,
        threshold=0.3,
        gate_mode="per_axis",
        claim_threshold=0.4,
        recall_process_threshold=0.35,
        provenance_chain_threshold=0.25,
        parent_chain_depth=1.0,
        source_diversity=0.8,
        age_of_original_source=3.0,
    )
    implausible = eligibility_gate(
        relevance=0.45,
        trust=1.0,
        recency=0.9,
        reinforcement=0.9,
        consistency=0.2,
        safety=0.9,
        threshold=0.3,
        gate_mode="per_axis",
        claim_threshold=0.4,
        recall_process_threshold=0.35,
        provenance_chain_threshold=0.25,
        parent_chain_depth=0.0,
        source_diversity=1.0,
        age_of_original_source=0.0,
    )

    emit(
        lineage,
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="o-plausible",
        payload={
            "snapshot_type": "axis_stress_claim_implausibility",
            "allow_influence": plausible.allow_influence,
            "uncertainty_triple": {
                "confidence_in_claim": plausible.uncertainty_triple.confidence_in_claim,
                "confidence_in_recall_process": plausible.uncertainty_triple.confidence_in_recall_process,
                "confidence_in_provenance_chain": plausible.uncertainty_triple.confidence_in_provenance_chain,
            },
            "dominant_axis": plausible.dominant_axis,
        },
    )
    emit(
        lineage,
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="o-implausible",
        payload={
            "snapshot_type": "axis_stress_claim_implausibility",
            "allow_influence": implausible.allow_influence,
            "uncertainty_triple": {
                "confidence_in_claim": implausible.uncertainty_triple.confidence_in_claim,
                "confidence_in_recall_process": implausible.uncertainty_triple.confidence_in_recall_process,
                "confidence_in_provenance_chain": implausible.uncertainty_triple.confidence_in_provenance_chain,
            },
            "dominant_axis": implausible.dominant_axis,
        },
    )

    pass_case = plausible.allow_influence and (not implausible.allow_influence) and implausible.dominant_axis == "claim"
    summary = {
        "suite": "O",
        "plausible_allow": plausible.allow_influence,
        "implausible_allow": implausible.allow_influence,
        "implausible_dominant_axis": implausible.dominant_axis,
        "pass": pass_case,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
