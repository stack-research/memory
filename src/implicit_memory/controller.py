from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .contamination import split_reality_detected
from .reasons import ImplicitReason
from .trigger_policy import TriggerAction, TriggerDecision, evaluate_trigger


class _LineageLike(Protocol):
    def emit(
        self,
        *,
        event_type: str,
        agent_id: str,
        stream_id: str,
        memory_id: str,
        payload: dict,
        actor_class: str = "implicit_memory_controller",
        source_class: str = "internal_engine",
        parent_event_id: str | None = None,
    ): ...


@dataclass(frozen=True)
class ObservationSignals:
    prediction_error: float
    goal_impact: float
    risk_signal: float
    repetition_signal: float
    contradiction_pressure: float
    explicit_directive: bool
    urgency: float
    sensory_confidence: float
    sensor_values: list[float]


def process_observation(
    *,
    lineage: _LineageLike,
    agent_id: str,
    stream_id: str,
    memory_id: str,
    signals: ObservationSignals,
) -> TriggerDecision:
    disagreement = split_reality_detected(sensor_values=signals.sensor_values)

    if disagreement:
        lineage.emit(
            event_type="contamination_suspected",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            actor_class="implicit_memory_controller",
            source_class="sensor_fusion",
            payload={
                "reason": ImplicitReason.SPLIT_REALITY_DETECTED.value,
                "sensor_values": signals.sensor_values,
                "urgency": signals.urgency,
                "risk_signal": signals.risk_signal,
            },
        )
        lineage.emit(
            event_type="implicit_trigger_deferred",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            actor_class="implicit_memory_controller",
            source_class="sensor_fusion",
            payload={"reason": ImplicitReason.SPLIT_REALITY_DETECTED.value},
        )
        return TriggerDecision(
            action=TriggerAction.DEFER,
            score=0.0,
            reasons=[ImplicitReason.SPLIT_REALITY_DETECTED.value],
        )

    trig = evaluate_trigger(
        prediction_error=signals.prediction_error,
        goal_impact=signals.goal_impact,
        risk_signal=signals.risk_signal,
        repetition_signal=signals.repetition_signal,
        contradiction_pressure=signals.contradiction_pressure,
        explicit_directive=signals.explicit_directive,
        urgency=signals.urgency,
        sensory_confidence=signals.sensory_confidence,
    )

    lineage.emit(
        event_type="implicit_trigger_evaluated",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        actor_class="implicit_memory_controller",
        source_class="internal_engine",
        payload={"action": trig.action.value, "score": trig.score, "reasons": trig.reasons},
    )

    if trig.action in {TriggerAction.DEFER, TriggerAction.NO_OP}:
        lineage.emit(
            event_type="implicit_trigger_deferred" if trig.action == TriggerAction.DEFER else "implicit_no_op",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            actor_class="implicit_memory_controller",
            source_class="internal_engine",
            payload={"reason": ",".join(trig.reasons)},
        )
    else:
        lineage.emit(
            event_type="implicit_trigger_fired",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            actor_class="implicit_memory_controller",
            source_class="internal_engine",
            payload={"action": trig.action.value, "score": trig.score},
        )

    return trig
