from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.explicit_memory.eligibility import (
    UncertaintyTriple,
    evaluate_uncertainty_gate,
    score_candidate,
    score_triple,
)
from src.implicit_memory.reasons import ImplicitReason


@dataclass(frozen=True)
class EligibilityDecision:
    allow_influence: bool
    score: float
    combined_score: float
    dominant_axis: str
    uncertainty_triple: UncertaintyTriple
    gate_mode: str
    reason: str


# Additive observer hook used by im_q traffic-evidence harness. When set, every
# eligibility_gate call also reports (inputs, decision) so a parallel harness
# can recompute the alternate-mode decision over real traffic. The observer
# never alters the decision returned to callers. Default behavior unchanged.
#
# _in_observer is a reentrancy guard: when an observer calls eligibility_gate
# again (e.g. to compute the alternate-mode decision), we must not re-trigger
# the observer or we recurse and pollute the sample.
_observer: Callable[[dict, "EligibilityDecision"], None] | None = None
_in_observer: bool = False


def set_eligibility_observer(observer: Callable[[dict, "EligibilityDecision"], None] | None) -> None:
    global _observer
    _observer = observer


def eligibility_gate(
    *,
    relevance: float,
    trust: float,
    recency: float,
    reinforcement: float,
    consistency: float,
    safety: float,
    threshold: float,
    parent_chain_depth: float = 0.0,
    source_diversity: float = 1.0,
    age_of_original_source: float = 0.0,
    gate_mode: str = "combined",
    combined_threshold: float | None = None,
    claim_threshold: float = 0.3,
    recall_process_threshold: float = 0.3,
    provenance_chain_threshold: float = 0.3,
    safety_floor: float = 0.1,
) -> EligibilityDecision:
    triple = score_triple(
        relevance=relevance,
        trust=trust,
        recency=recency,
        reinforcement=reinforcement,
        consistency=consistency,
        safety=safety,
        parent_chain_depth=parent_chain_depth,
        source_diversity=source_diversity,
        age_of_original_source=age_of_original_source,
    )
    combined_score = triple.combined()
    legacy_score = score_candidate(
        relevance=relevance,
        trust=trust,
        recency=recency,
        reinforcement=reinforcement,
        consistency=consistency,
        safety=safety,
    )

    ok, mode = evaluate_uncertainty_gate(
        legacy_score=legacy_score,
        triple=triple,
        safety=safety,
        gate_mode=gate_mode,
        threshold=threshold,
        combined_threshold=combined_threshold,
        claim_threshold=claim_threshold,
        recall_process_threshold=recall_process_threshold,
        provenance_chain_threshold=provenance_chain_threshold,
        safety_floor=safety_floor,
    )

    decision = EligibilityDecision(
        allow_influence=ok,
        score=legacy_score,
        combined_score=combined_score,
        dominant_axis=triple.dominant_axis(),
        uncertainty_triple=triple,
        gate_mode=mode,
        reason=(ImplicitReason.ELIGIBLE.value if ok else ImplicitReason.ELIGIBILITY_BELOW_THRESHOLD.value),
    )

    global _in_observer
    if _observer is not None and not _in_observer:
        _in_observer = True
        try:
            _observer(
                {
                    "relevance": relevance,
                    "trust": trust,
                    "recency": recency,
                    "reinforcement": reinforcement,
                    "consistency": consistency,
                    "safety": safety,
                    "threshold": threshold,
                    "parent_chain_depth": parent_chain_depth,
                    "source_diversity": source_diversity,
                    "age_of_original_source": age_of_original_source,
                    "gate_mode": gate_mode,
                    "combined_threshold": combined_threshold,
                    "claim_threshold": claim_threshold,
                    "recall_process_threshold": recall_process_threshold,
                    "provenance_chain_threshold": provenance_chain_threshold,
                    "safety_floor": safety_floor,
                },
                decision,
            )
        except Exception:
            pass
        finally:
            _in_observer = False

    return decision
