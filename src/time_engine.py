from __future__ import annotations

import math


def decay_score(*, hours_since_last_reinforced: float, lambda_rate: float = 0.03) -> float:
    return math.exp(-lambda_rate * hours_since_last_reinforced)
