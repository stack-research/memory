from __future__ import annotations


def score_candidate(
    *,
    relevance: float,
    trust: float,
    recency: float,
    reinforcement: float,
    consistency: float,
    safety: float,
) -> float:
    return relevance * trust * recency * reinforcement * consistency * safety


def is_eligible(score: float, threshold: float = 0.2) -> bool:
    return score >= threshold
