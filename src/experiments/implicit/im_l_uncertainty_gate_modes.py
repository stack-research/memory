from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.eligibility import eligibility_gate


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-l"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    candidates = [
        {
            "memory_id": "l-1",
            "relevance": 0.92,
            "trust": 0.75,
            "recency": 0.95,
            "reinforcement": 0.9,
            "consistency": 0.85,
            "safety": 0.9,
            "parent_chain_depth": 0.0,
            "source_diversity": 0.9,
            "age_of_original_source": 2.0,
        },
        {
            "memory_id": "l-2",
            "relevance": 0.88,
            "trust": 0.9,
            "recency": 0.9,
            "reinforcement": 0.95,
            "consistency": 0.9,
            "safety": 0.9,
            "parent_chain_depth": 6.0,
            "source_diversity": 0.2,
            "age_of_original_source": 240.0,
        },
        {
            "memory_id": "l-3",
            "relevance": 0.7,
            "trust": 0.75,
            "recency": 0.7,
            "reinforcement": 0.8,
            "consistency": 0.7,
            "safety": 0.05,
            "parent_chain_depth": 1.0,
            "source_diversity": 0.8,
            "age_of_original_source": 8.0,
        },
    ]

    decisions: list[dict] = []
    for c in candidates:
        combined_dec = eligibility_gate(
            relevance=c["relevance"],
            trust=c["trust"],
            recency=c["recency"],
            reinforcement=c["reinforcement"],
            consistency=c["consistency"],
            safety=c["safety"],
            threshold=0.3,
            parent_chain_depth=c["parent_chain_depth"],
            source_diversity=c["source_diversity"],
            age_of_original_source=c["age_of_original_source"],
            gate_mode="combined",
            combined_threshold=0.3,
            safety_floor=0.1,
        )
        per_axis_dec = eligibility_gate(
            relevance=c["relevance"],
            trust=c["trust"],
            recency=c["recency"],
            reinforcement=c["reinforcement"],
            consistency=c["consistency"],
            safety=c["safety"],
            threshold=0.3,
            parent_chain_depth=c["parent_chain_depth"],
            source_diversity=c["source_diversity"],
            age_of_original_source=c["age_of_original_source"],
            gate_mode="per_axis",
            claim_threshold=0.4,
            recall_process_threshold=0.4,
            provenance_chain_threshold=0.25,
            safety_floor=0.1,
        )

        emit(
            lineage,
            event_type="snapshotted",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=c["memory_id"],
            payload={
                "snapshot_type": "uncertainty_gate_mode_comparison",
                "candidate": c,
                "combined": {
                    "allow_influence": combined_dec.allow_influence,
                    "score": combined_dec.score,
                    "combined_score": combined_dec.combined_score,
                    "dominant_axis": combined_dec.dominant_axis,
                },
                "per_axis": {
                    "allow_influence": per_axis_dec.allow_influence,
                    "score": per_axis_dec.score,
                    "combined_score": per_axis_dec.combined_score,
                    "dominant_axis": per_axis_dec.dominant_axis,
                },
            },
        )

        decisions.append(
            {
                "memory_id": c["memory_id"],
                "combined_allow": combined_dec.allow_influence,
                "per_axis_allow": per_axis_dec.allow_influence,
            }
        )

    divergence_count = sum(1 for d in decisions if d["combined_allow"] != d["per_axis_allow"])
    summary = {
        "suite": "L",
        "candidate_count": len(candidates),
        "divergence_count": divergence_count,
        "decisions": decisions,
        "pass": divergence_count >= 1,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
