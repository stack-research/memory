from __future__ import annotations


def admission_score(
    *,
    significance: float,
    source_trust: float,
    novelty: float,
    risk_signal: float,
) -> float:
    base = 0.5 * significance + 0.2 * source_trust + 0.15 * novelty + 0.15 * risk_signal
    return max(0.0, min(1.0, base))
