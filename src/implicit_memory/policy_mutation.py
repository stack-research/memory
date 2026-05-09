from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PolicyState:
    threshold_map: dict[str, float]
    procedure_map: dict[str, str]


def validate_threshold(value: float) -> bool:
    return 0.0 <= value <= 1.0


def update_threshold(
    state: PolicyState,
    *,
    name: str,
    new_value: float,
    reason: str,
) -> tuple[PolicyState, dict]:
    if name not in state.threshold_map:
        raise ValueError(f"unknown threshold '{name}'")
    if not validate_threshold(new_value):
        raise ValueError(f"invalid threshold value '{new_value}'")

    old_value = state.threshold_map[name]
    state.threshold_map[name] = new_value
    payload = {
        "mutation_type": "threshold_update",
        "target": name,
        "old_value": old_value,
        "new_value": new_value,
        "reason": reason,
    }
    return state, payload


def supersede_procedure(
    state: PolicyState,
    *,
    slot: str,
    new_procedure_id: str,
    reason: str,
) -> tuple[PolicyState, dict]:
    old_procedure_id = state.procedure_map.get(slot)
    state.procedure_map[slot] = new_procedure_id
    payload = {
        "mutation_type": "procedure_supersession",
        "slot": slot,
        "old_procedure_id": old_procedure_id,
        "new_procedure_id": new_procedure_id,
        "reason": reason,
    }
    return state, payload
