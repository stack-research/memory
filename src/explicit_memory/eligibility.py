from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Default conservative fallback multiplier per EPISTEMIC_TRIANGLE
# spec §11. When a signal walker returns signal_source = "fallback",
# the corresponding axis is multiplied by this value rather than
# silently using a default. Emitted in lineage as
# `policy_fallback_multiplier` so audits can tune it.
V7_FALLBACK_MULTIPLIER_DEFAULT: float = 0.5


@dataclass(frozen=True)
class UncertaintyTriple:
    confidence_in_claim: float
    confidence_in_recall_process: float
    confidence_in_provenance_chain: float
    # v7 EPISTEMIC_TRIANGLE §11 — per-axis fallback visibility.
    # `axis_fallback_used` is a per-axis boolean dict; non-empty
    # `axis_fallback_reasons` names the closed-enum reason per axis.
    # `policy_fallback_multiplier` records the multiplier the gate
    # actually applied so the choice is replayable from lineage.
    axis_fallback_used: dict[str, bool] = field(default_factory=dict)
    axis_fallback_reasons: dict[str, str | None] = field(default_factory=dict)
    policy_fallback_multiplier: float = V7_FALLBACK_MULTIPLIER_DEFAULT

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


def _apply_axis(
    base: float,
    signal: Any,
    *,
    fallback_multiplier: float,
) -> tuple[float, bool, str | None]:
    """Spec §11 axis-application rule.

    Returns (axis_score, fallback_used, fallback_reason).

    - When `signal` is None: legacy compatibility — pass `base`
      through unchanged. Pre-v7 callers will route this branch.
    - When signal_source is "computed" or "cache": no multiplier
      adjustment; the v1 axis formula's output (already baked into
      `base` by the caller) is returned.
    - When signal_source is "fallback": apply
      `base * fallback_multiplier`; surface `axis_fallback_used=True`
      and the closed-enum `fallback_reason`.
    """
    if signal is None:
        return _clamp01(base), False, None
    # Duck-type around NormalizedSignals vs the per-axis signal
    # dataclasses (ClaimSignals, RecallSignals, normalized
    # ProvenanceSignals); they all expose `signal_source`.
    source = getattr(signal, "signal_source", None)
    source_value = getattr(source, "value", source)  # enum or str
    reason = getattr(signal, "fallback_reason", None)
    if source_value == "fallback":
        return _clamp01(base * float(fallback_multiplier)), True, reason
    # computed / cache pass through.
    return _clamp01(base), False, None


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
    # v7 EPISTEMIC_TRIANGLE §11: optional axis signals. When None,
    # legacy v6 compute path applies (only `schema_version < 7.0`
    # callers should pass None). When supplied, fallback visibility
    # is recorded on the returned triple.
    claim_signals: Any | None = None,
    recall_signals: Any | None = None,
    provenance_signals: Any | None = None,
    fallback_multiplier: float = V7_FALLBACK_MULTIPLIER_DEFAULT,
) -> UncertaintyTriple:
    claim_consistency = _clamp01(consistency)
    claim_base = _clamp01(relevance) * (0.7 + 0.3 * claim_consistency)

    recall_consistency = _clamp01(consistency)
    recall_base = _clamp01(recency) * _clamp01(reinforcement) * (0.5 + 0.5 * recall_consistency)

    depth_penalty = 1.0 / (1.0 + max(0.0, float(parent_chain_depth)))
    diversity_factor = _clamp01(source_diversity)
    age_penalty = 1.0 / (1.0 + max(0.0, float(age_of_original_source)) / 24.0)
    provenance_base = _clamp01(trust) * depth_penalty * diversity_factor * age_penalty

    # Safety is enforced as a hard gate in policy paths and is not an axis.
    _ = _clamp01(safety)

    claim_score, claim_fb, claim_reason = _apply_axis(claim_base, claim_signals, fallback_multiplier=fallback_multiplier)
    recall_score, recall_fb, recall_reason = _apply_axis(recall_base, recall_signals, fallback_multiplier=fallback_multiplier)
    prov_score, prov_fb, prov_reason = _apply_axis(provenance_base, provenance_signals, fallback_multiplier=fallback_multiplier)

    return UncertaintyTriple(
        confidence_in_claim=claim_score,
        confidence_in_recall_process=recall_score,
        confidence_in_provenance_chain=prov_score,
        axis_fallback_used={
            "claim": claim_fb,
            "recall_process": recall_fb,
            "provenance_chain": prov_fb,
        },
        axis_fallback_reasons={
            "claim": claim_reason,
            "recall_process": recall_reason,
            "provenance_chain": prov_reason,
        },
        policy_fallback_multiplier=float(fallback_multiplier),
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
