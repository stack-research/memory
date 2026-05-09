from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ImplicitTestSettings:
    admission_threshold: float
    eligibility_threshold: float
    contamination_threshold: float
    reflex_max_actions: int
    reflex_cooldown_steps: int
    event_flood_threshold: int


def load_implicit_test_settings() -> ImplicitTestSettings:
    return ImplicitTestSettings(
        admission_threshold=float(os.environ.get("IMPLICIT_ADMISSION_THRESHOLD", "0.45")),
        eligibility_threshold=float(os.environ.get("IMPLICIT_ELIGIBILITY_THRESHOLD", "0.30")),
        contamination_threshold=float(os.environ.get("IMPLICIT_CONTAMINATION_THRESHOLD", "0.60")),
        reflex_max_actions=int(os.environ.get("IMPLICIT_REFLEX_MAX_ACTIONS", "2")),
        reflex_cooldown_steps=int(os.environ.get("IMPLICIT_REFLEX_COOLDOWN_STEPS", "3")),
        event_flood_threshold=int(os.environ.get("IMPLICIT_EVENT_FLOOD_THRESHOLD", "5")),
    )
