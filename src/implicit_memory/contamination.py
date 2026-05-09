from __future__ import annotations


def split_reality_detected(*, sensor_values: list[float], disagreement_threshold: float = 0.35) -> bool:
    if len(sensor_values) < 2:
        return False
    spread = max(sensor_values) - min(sensor_values)
    return spread >= disagreement_threshold


def contamination_risk(
    *,
    source_trust: float,
    cross_source_support: float,
    conflict_pressure: float,
    anomaly_signal: float,
) -> float:
    # Trust is prior, not truth: high trust + low support + high conflict remains risky.
    risk = (
        0.35 * (1.0 - cross_source_support)
        + 0.30 * conflict_pressure
        + 0.25 * anomaly_signal
        + 0.10 * source_trust
    )
    return max(0.0, min(1.0, risk))
