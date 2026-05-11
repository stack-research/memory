from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UncertaintyTriple:
    confidence_in_claim: float
    confidence_in_recall_process: float
    confidence_in_provenance_chain: float

    def combined(self) -> float:
        return (
            self.confidence_in_claim
            * self.confidence_in_recall_process
            * self.confidence_in_provenance_chain
        )

    def dominant_axis(self) -> str:
        axes = {
            "claim": self.confidence_in_claim,
            "recall_process": self.confidence_in_recall_process,
            "provenance_chain": self.confidence_in_provenance_chain,
        }
        return min(axes, key=axes.get)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def score_triple(
    *,
    relevance: float,
    trust: float,
    recency: float,
    reinforcement: float,
    consistency: float,
    safety: float,
    parent_chain_depth: float = 0.0,
    source_diversity: float = 1.0,
    age_of_original_source: float = 0.0,
) -> UncertaintyTriple:
    claim_consistency = _clamp01(consistency)
    claim = _clamp01(relevance) * (0.7 + 0.3 * claim_consistency)

    recall_consistency = _clamp01(consistency)
    recall_process = _clamp01(recency) * _clamp01(reinforcement) * (0.5 + 0.5 * recall_consistency)

    depth_penalty = 1.0 / (1.0 + max(0.0, float(parent_chain_depth)))
    diversity_factor = _clamp01(source_diversity)
    age_penalty = 1.0 / (1.0 + max(0.0, float(age_of_original_source)) / 24.0)
    provenance_chain = _clamp01(trust) * depth_penalty * diversity_factor * age_penalty

    # Safety is enforced as a hard gate in policy paths and is not an axis.
    _ = _clamp01(safety)

    return UncertaintyTriple(
        confidence_in_claim=_clamp01(claim),
        confidence_in_recall_process=_clamp01(recall_process),
        confidence_in_provenance_chain=_clamp01(provenance_chain),
    )


def score_candidate(
    *,
    relevance: float,
    trust: float,
    recency: float,
    reinforcement: float,
    consistency: float,
    safety: float,
) -> float:
    # Backward-compatible scalar path used by existing eligibility behavior.
    return relevance * trust * recency * reinforcement * consistency * safety


def is_eligible(score: float, *, threshold: float) -> bool:
    return score >= threshold


def evaluate_uncertainty_gate(
    *,
    legacy_score: float,
    triple: UncertaintyTriple,
    safety: float,
    gate_mode: str,
    threshold: float,
    combined_threshold: float | None,
    claim_threshold: float,
    recall_process_threshold: float,
    provenance_chain_threshold: float,
    safety_floor: float,
) -> tuple[bool, str]:
    mode = gate_mode.strip().lower()
    if mode not in {"combined", "per_axis"}:
        mode = "combined"

    safety_ok = float(safety) >= float(safety_floor)
    if mode == "per_axis":
        ok = (
            safety_ok
            and triple.confidence_in_claim >= float(claim_threshold)
            and triple.confidence_in_recall_process >= float(recall_process_threshold)
            and triple.confidence_in_provenance_chain >= float(provenance_chain_threshold)
        )
    else:
        active_threshold = float(combined_threshold) if combined_threshold is not None else float(threshold)
        ok = safety_ok and is_eligible(legacy_score, threshold=active_threshold)

    return ok, mode


__all__ = [
    "UncertaintyTriple",
    "score_triple",
    "score_candidate",
    "is_eligible",
    "evaluate_uncertainty_gate",
]
