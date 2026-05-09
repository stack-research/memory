from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TriggerAction(StrEnum):
    INVOKE_ENCODE = "invoke_encode"
    INVOKE_RECALL = "invoke_recall"
    REFLEX_EXECUTE = "reflex_execute"
    DEFER = "defer"
    NO_OP = "no_op"


@dataclass(frozen=True)
class TriggerDecision:
    action: TriggerAction
    score: float
    reasons: list[str]


def evaluate_trigger(
    *,
    prediction_error: float,
    goal_impact: float,
    risk_signal: float,
    repetition_signal: float,
    contradiction_pressure: float,
    explicit_directive: bool,
    urgency: float,
    sensory_confidence: float,
    encode_threshold: float = 0.45,
    recall_threshold: float = 0.35,
    reflex_threshold: float = 0.75,
) -> TriggerDecision:
    if explicit_directive:
        return TriggerDecision(
            action=TriggerAction.INVOKE_RECALL,
            score=1.0,
            reasons=["explicit_directive"],
        )

    score = (
        0.25 * prediction_error
        + 0.20 * goal_impact
        + 0.25 * risk_signal
        + 0.10 * repetition_signal
        + 0.20 * contradiction_pressure
    )

    reflex_score = urgency * risk_signal * sensory_confidence
    if reflex_score >= reflex_threshold:
        return TriggerDecision(
            action=TriggerAction.REFLEX_EXECUTE,
            score=reflex_score,
            reasons=["urgency_risk_sensory"],
        )

    if score >= encode_threshold:
        return TriggerDecision(
            action=TriggerAction.INVOKE_ENCODE,
            score=score,
            reasons=["high_significance"],
        )

    if contradiction_pressure >= recall_threshold:
        return TriggerDecision(
            action=TriggerAction.INVOKE_RECALL,
            score=contradiction_pressure,
            reasons=["contradiction_pressure"],
        )

    if score > 0:
        return TriggerDecision(action=TriggerAction.DEFER, score=score, reasons=["below_threshold"])

    return TriggerDecision(action=TriggerAction.NO_OP, score=0.0, reasons=["no_signal"])
