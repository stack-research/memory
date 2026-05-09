from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.procedure_lifecycle import (
    ProcedureState,
    apply_urgency_trust_decay,
    decay_procedure,
    reinforce_procedure,
)


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-h"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    state = ProcedureState(procedure_id="proc-reflex-triage", strength=1.0, trust=1.0)

    # Reinforcement phase
    for i in range(2):
        state = reinforce_procedure(state, reward=0.12)
        emit(
            lineage,
            event_type="procedure_reinforced",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=state.procedure_id,
            payload={"step": i + 1, "strength": state.strength, "trust": state.trust},
        )

    # Decay phase
    state = decay_procedure(state, decay=0.08)
    emit(
        lineage,
        event_type="procedure_decayed",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=state.procedure_id,
        payload={"strength": state.strength, "trust": state.trust, "reason": "idle_decay"},
    )

    # Prolonged high urgency -> trust decay
    urgencies = [0.9, 0.92, 0.95, 0.93]
    trust_decay_events = 0
    for u in urgencies:
        state, decayed = apply_urgency_trust_decay(state, urgency=u)
        if decayed:
            trust_decay_events += 1
            emit(
                lineage,
                event_type="policy_threshold_updated",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=state.procedure_id,
                payload={
                    "reason": "prolonged_high_urgency_trust_decay",
                    "urgency": u,
                    "high_urgency_streak": state.high_urgency_streak,
                    "trust": state.trust,
                },
            )

    pass_flag = trust_decay_events >= 1 and state.trust < 1.0
    summary = {
        "suite": "H",
        "procedure_id": state.procedure_id,
        "strength": state.strength,
        "trust": state.trust,
        "trust_decay_events": trust_decay_events,
        "pass": pass_flag,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
