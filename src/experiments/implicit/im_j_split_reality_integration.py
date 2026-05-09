from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, summarize
from src.implicit_memory.controller import ObservationSignals, process_observation


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-j"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    # 1) disagreeing sensors should defer and emit contamination
    s1 = ObservationSignals(
        prediction_error=0.7,
        goal_impact=0.6,
        risk_signal=0.8,
        repetition_signal=0.1,
        contradiction_pressure=0.2,
        explicit_directive=False,
        urgency=0.9,
        sensory_confidence=0.95,
        sensor_values=[0.1, 0.95, 0.2],
    )
    d1 = process_observation(
        lineage=lineage,
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="j-1",
        signals=s1,
    )

    # 2) agreeing sensors should evaluate and proceed
    s2 = ObservationSignals(
        prediction_error=0.7,
        goal_impact=0.6,
        risk_signal=0.8,
        repetition_signal=0.1,
        contradiction_pressure=0.2,
        explicit_directive=False,
        urgency=0.9,
        sensory_confidence=0.95,
        sensor_values=[0.8, 0.82, 0.85],
    )
    d2 = process_observation(
        lineage=lineage,
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="j-2",
        signals=s2,
    )

    split_events = [e for e in events if e.get("event_type") == "contamination_suspected" and e.get("payload", {}).get("reason") == "split_reality_detected"]
    deferred_split = [e for e in events if e.get("event_type") == "implicit_trigger_deferred" and e.get("payload", {}).get("reason") == "split_reality_detected"]
    fired = [e for e in events if e.get("event_type") == "implicit_trigger_fired"]

    summary = {
        "suite": "J",
        "d1_action": d1.action.value,
        "d2_action": d2.action.value,
        "split_events": len(split_events),
        "deferred_split": len(deferred_split),
        "fired_events": len(fired),
        "pass": d1.action.value == "defer" and len(split_events) >= 1 and len(deferred_split) >= 1 and len(fired) >= 1,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
