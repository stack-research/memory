from __future__ import annotations

from collections import Counter, defaultdict

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.reasons import ImplicitReason
from src.implicit_memory.settings import load_implicit_test_settings


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-g"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    cfg = load_implicit_test_settings()
    flood_threshold = cfg.event_flood_threshold
    window_events = 12

    counts_by_source: dict[str, int] = defaultdict(int)
    flood_detected = 0
    quarantined = 0
    admitted = 0

    for i in range(window_events):
        source_id = "src-flood" if i < 10 else "src-normal"
        memory_id = f"g-{i+1}"
        counts_by_source[source_id] += 1

        emit(
            lineage,
            event_type="implicit_trigger_evaluated",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            payload={"source_id": source_id, "index": i + 1},
        )

        is_flood = counts_by_source[source_id] > flood_threshold
        if is_flood:
            flood_detected += 1
            emit(
                lineage,
                event_type="contamination_suspected",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=memory_id,
                payload={"reason": ImplicitReason.EVENT_FLOOD_SUSPECTED.value, "source_id": source_id, "count": counts_by_source[source_id]},
            )
            emit(
                lineage,
                event_type="implicit_rejected",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=memory_id,
                payload={
                    "reason": ImplicitReason.EVENT_FLOOD_SUSPECTED.value,
                    "source_id": source_id,
                    "eligibility_score": 0.0,
                    "uncertainty_triple": {
                        "confidence_in_claim": 0.0,
                        "confidence_in_recall_process": 0.0,
                        "confidence_in_provenance_chain": 0.0,
                    },
                    "combined_score": 0.0,
                    "dominant_axis": "claim",
                },
            )
            quarantined += 1
        else:
            emit(
                lineage,
                event_type="implicit_admitted",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=memory_id,
                payload={
                    "source_id": source_id,
                    "count": counts_by_source[source_id],
                    "eligibility_score": 1.0,
                    "uncertainty_triple": {
                        "confidence_in_claim": 1.0,
                        "confidence_in_recall_process": 1.0,
                        "confidence_in_provenance_chain": 1.0,
                    },
                    "combined_score": 1.0,
                    "dominant_axis": "claim",
                },
            )
            admitted += 1

    type_counts = Counter(e.get("event_type") for e in events)
    summary = {
        "suite": "G",
        "window_events": window_events,
        "flood_threshold": flood_threshold,
        "flood_detected": flood_detected,
        "quarantined": quarantined,
        "admitted": admitted,
        "event_type_counts": dict(type_counts),
        "pass": flood_detected >= 1 and quarantined >= 1 and type_counts.get("contamination_suspected", 0) == quarantined,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
