from __future__ import annotations

from dataclasses import dataclass

from src.eligibility_engine import is_eligible, score_candidate


@dataclass(frozen=True)
class EligibilityDecision:
    allow_influence: bool
    score: float
    reason: str


def eligibility_gate(
    *,
    relevance: float,
    trust: float,
    recency: float,
    reinforcement: float,
    consistency: float,
    safety: float,
    threshold: float,
) -> EligibilityDecision:
    score = score_candidate(
        relevance=relevance,
        trust=trust,
        recency=recency,
        reinforcement=reinforcement,
        consistency=consistency,
        safety=safety,
    )
    ok = is_eligible(score, threshold=threshold)
    return EligibilityDecision(
        allow_influence=ok,
        score=score,
        reason="eligible" if ok else "eligibility_below_threshold",
    )
