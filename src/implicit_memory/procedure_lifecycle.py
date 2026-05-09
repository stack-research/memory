from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProcedureState:
    procedure_id: str
    strength: float = 1.0
    trust: float = 1.0
    high_urgency_streak: int = 0


def reinforce_procedure(state: ProcedureState, *, reward: float = 0.1) -> ProcedureState:
    state.strength = min(2.0, state.strength + max(0.0, reward))
    return state


def decay_procedure(state: ProcedureState, *, decay: float = 0.05) -> ProcedureState:
    state.strength = max(0.0, state.strength - max(0.0, decay))
    return state


def apply_urgency_trust_decay(
    state: ProcedureState,
    *,
    urgency: float,
    threshold: float = 0.85,
    streak_limit: int = 3,
    decay_step: float = 0.1,
) -> tuple[ProcedureState, bool]:
    if urgency >= threshold:
        state.high_urgency_streak += 1
    else:
        state.high_urgency_streak = 0

    decayed = False
    if state.high_urgency_streak >= streak_limit:
        state.trust = max(0.0, state.trust - decay_step)
        decayed = True
    return state, decayed
