from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.contamination import contamination_risk


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-c"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    scenarios = [
        {"memory_id": "c1", "source_trust": 0.95, "support": 0.2, "conflict": 0.9, "anomaly": 0.7},
        {"memory_id": "c2", "source_trust": 0.60, "support": 0.8, "conflict": 0.2, "anomaly": 0.1},
        {"memory_id": "c3", "source_trust": 0.90, "support": 0.1, "conflict": 0.8, "anomaly": 0.8},
    ]

    quarantined = 0
    promoted = 0
    for s in scenarios:
        risk = contamination_risk(
            source_trust=s["source_trust"],
            cross_source_support=s["support"],
            conflict_pressure=s["conflict"],
            anomaly_signal=s["anomaly"],
        )
        emit(
            lineage,
            event_type="contamination_suspected",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=s["memory_id"],
            payload={"risk": risk, **s},
        )
        if risk >= 0.60:
            quarantined += 1
            emit(
                lineage,
                event_type="implicit_rejected",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=s["memory_id"],
                payload={"reason": "contamination_risk_threshold", "risk": risk},
            )
        else:
            promoted += 1
            emit(
                lineage,
                event_type="implicit_admitted",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=s["memory_id"],
                payload={"risk": risk},
            )

    containment_rate = quarantined / max(1, len(scenarios))
    summary = {
        "suite": "C",
        "scenario_count": len(scenarios),
        "quarantined": quarantined,
        "promoted": promoted,
        "containment_rate": containment_rate,
        "pass": quarantined >= 2,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
