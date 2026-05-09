from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.trigger_policy import evaluate_trigger


def _run_once() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-f"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    inputs = [
        ("f1", 0.8, 0.7, 0.3, 0.2, 0.4, False, 0.2, 0.8),
        ("f2", 0.2, 0.2, 0.9, 0.1, 0.1, False, 0.95, 0.95),
        ("f3", 0.1, 0.1, 0.1, 0.0, 0.0, True, 0.1, 0.8),
    ]

    for row in inputs:
        memory_id, pe, gi, risk, rep, cp, directive, urg, sensory = row
        trig = evaluate_trigger(
            prediction_error=pe,
            goal_impact=gi,
            risk_signal=risk,
            repetition_signal=rep,
            contradiction_pressure=cp,
            explicit_directive=directive,
            urgency=urg,
            sensory_confidence=sensory,
        )
        emit(
            lineage,
            event_type="implicit_trigger_evaluated",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            payload={"action": trig.action.value, "score": trig.score},
        )

    return summarize(events)


def run() -> dict:
    first = _run_once()
    second = _run_once()
    summary = {
        "suite": "F",
        "first_signature": first["decision_signature"],
        "second_signature": second["decision_signature"],
        "first_counts": first["event_type_counts"],
        "second_counts": second["event_type_counts"],
        "pass": first["decision_signature"] == second["decision_signature"] and first["event_type_counts"] == second["event_type_counts"],
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
