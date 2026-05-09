from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.admission import admission_score
from src.implicit_memory.trigger_policy import TriggerAction, evaluate_trigger


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-a"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    observations = [
        {"id": "obs-1", "prediction_error": 0.1, "goal_impact": 0.1, "risk": 0.1, "repetition": 0.2, "contradiction": 0.0, "directive": False, "urgency": 0.1, "sensory": 0.8},
        {"id": "obs-2", "prediction_error": 0.7, "goal_impact": 0.6, "risk": 0.4, "repetition": 0.4, "contradiction": 0.2, "directive": False, "urgency": 0.2, "sensory": 0.8},
        {"id": "obs-3", "prediction_error": 0.05, "goal_impact": 0.05, "risk": 0.0, "repetition": 0.0, "contradiction": 0.0, "directive": False, "urgency": 0.1, "sensory": 0.8},
        {"id": "obs-4", "prediction_error": 0.2, "goal_impact": 0.2, "risk": 0.2, "repetition": 0.3, "contradiction": 0.6, "directive": False, "urgency": 0.1, "sensory": 0.8},
    ]

    high_significance = 0
    high_triggered = 0
    low_triggered = 0
    low_total = 0

    for obs in observations:
        trig = evaluate_trigger(
            prediction_error=obs["prediction_error"],
            goal_impact=obs["goal_impact"],
            risk_signal=obs["risk"],
            repetition_signal=obs["repetition"],
            contradiction_pressure=obs["contradiction"],
            explicit_directive=obs["directive"],
            urgency=obs["urgency"],
            sensory_confidence=obs["sensory"],
        )
        emit(
            lineage,
            event_type="implicit_trigger_evaluated",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=obs["id"],
            payload={"action": trig.action.value, "score": trig.score, "reasons": trig.reasons},
        )

        sig = admission_score(
            significance=(obs["prediction_error"] + obs["goal_impact"] + obs["risk"] + obs["contradiction"]) / 4.0,
            source_trust=0.6,
            novelty=1.0 - obs["repetition"],
            risk_signal=obs["risk"],
        )
        is_high = sig >= 0.45
        if is_high:
            high_significance += 1
        else:
            low_total += 1

        fired = trig.action in {TriggerAction.INVOKE_ENCODE, TriggerAction.INVOKE_RECALL, TriggerAction.REFLEX_EXECUTE}
        if fired and is_high:
            high_triggered += 1
        if fired and not is_high:
            low_triggered += 1

        emit(
            lineage,
            event_type="implicit_trigger_fired" if fired else "implicit_trigger_deferred",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=obs["id"],
            payload={"admission_score": sig, "high_significance": is_high},
        )

    high_trigger_rate = high_triggered / max(1, high_significance)
    low_false_trigger_rate = low_triggered / max(1, low_total)
    summary = {
        "suite": "A",
        "high_significance": high_significance,
        "high_triggered": high_triggered,
        "high_trigger_rate": high_trigger_rate,
        "low_total": low_total,
        "low_triggered": low_triggered,
        "low_false_trigger_rate": low_false_trigger_rate,
        "pass": high_trigger_rate >= 0.8 and low_false_trigger_rate <= 0.5,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
