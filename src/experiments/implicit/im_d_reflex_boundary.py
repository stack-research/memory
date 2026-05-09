from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.reflex_mode import ReflexController
from src.implicit_memory.trigger_policy import TriggerAction, evaluate_trigger


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-d"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    controller = ReflexController(max_actions=2, cooldown_steps=3)

    # includes valid reflex spikes and spoof/noise attempts
    steps = [
        {"id": "d1", "risk": 0.9, "urgency": 0.95, "sensory": 0.95},  # reflex expected
        {"id": "d2", "risk": 0.95, "urgency": 0.95, "sensory": 0.95},  # blocked by cooldown
        {"id": "d3", "risk": 0.95, "urgency": 0.95, "sensory": 0.95},  # blocked by cooldown
        {"id": "d4", "risk": 0.2, "urgency": 0.8, "sensory": 0.3},    # spoof/noise
        {"id": "d5", "risk": 0.9, "urgency": 0.95, "sensory": 0.95},  # may re-enter after cooldown
    ]

    reflex_entries = 0
    reflex_actions = 0
    blocked_entries = 0

    for step in steps:
        trig = evaluate_trigger(
            prediction_error=0.2,
            goal_impact=0.2,
            risk_signal=step["risk"],
            repetition_signal=0.1,
            contradiction_pressure=0.1,
            explicit_directive=False,
            urgency=step["urgency"],
            sensory_confidence=step["sensory"],
        )
        emit(
            lineage,
            event_type="implicit_trigger_evaluated",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=step["id"],
            payload={"action": trig.action.value, "score": trig.score},
        )

        if trig.action == TriggerAction.REFLEX_EXECUTE:
            if controller.enter():
                reflex_entries += 1
                emit(
                    lineage,
                    event_type="reflex_mode_entered",
                    agent_id=agent_id,
                    stream_id=stream_id,
                    memory_id=step["id"],
                    payload={"actions_taken": controller.actions_taken},
                )
                controller.record_action()
                reflex_actions += 1
                emit(
                    lineage,
                    event_type="reflex_action_executed",
                    agent_id=agent_id,
                    stream_id=stream_id,
                    memory_id=step["id"],
                    payload={"actions_taken": controller.actions_taken},
                )
                # End reflex cycle immediately; cooldown enforces bounded operation.
                controller.exit()
                emit(
                    lineage,
                    event_type="reflex_mode_exited",
                    agent_id=agent_id,
                    stream_id=stream_id,
                    memory_id=step["id"],
                    payload={"reason": "cycle_complete"},
                )
            else:
                blocked_entries += 1
                emit(
                    lineage,
                    event_type="implicit_trigger_deferred",
                    agent_id=agent_id,
                    stream_id=stream_id,
                    memory_id=step["id"],
                    payload={"reason": "reflex_cooldown_or_budget"},
                )
        else:
            emit(
                lineage,
                event_type="implicit_no_op",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=step["id"],
                payload={"reason": "not_reflex"},
            )

        controller.tick()

    summary = {
        "suite": "D",
        "reflex_entries": reflex_entries,
        "reflex_actions": reflex_actions,
        "blocked_entries": blocked_entries,
        "pass": reflex_entries >= 1 and blocked_entries >= 1,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
