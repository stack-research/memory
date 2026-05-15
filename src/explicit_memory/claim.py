"""compute_claim_signals — lineage walker for `confidence_in_claim`.

Spec: specs/EPISTEMIC_TRIANGLE.md §5

Walks `evidence_link_declared` lineage events to derive lineage-grounded
support/refutation counts and source diversity for a target claim
(or belief) event. Walker semantics use latest-state selection per
`link_id` (spec §4.3) so an `invalid` event after a prior `resolved`
correctly invalidates the link.

Pure function: takes pre-resolved event dicts. Phase 3 wires this to
a real `LineageReader` query for `evidence_link_declared` events
referencing the target claim.

Replay-deterministic: no wall-clock reads. `as_of_time` is supplied
explicitly by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from src.epistemic_triangle.kinds import AssertionKind
from src.epistemic_triangle.links import (
    LinkType,
    select_latest_link_states,
)
from src.explicit_memory.signals import (
    NormalizedSignals,
    SignalMethod,
    SignalSource,
)


# Closed enum for claim signal fallback reasons (spec §5).
CLAIM_FALLBACK_REASONS: frozenset[str] = frozenset({
    "no_evidence_links",
    "not_claim_kind",
    "walk_depth_exceeded",
    "assertion_kind_unset",
    "cross_scope_denied",
})


@dataclass(frozen=True)
class ClaimSignals:
    evidence_support_count: int
    refutation_count: int
    evidence_diversity: float
    signal_source: SignalSource
    signal_method: SignalMethod
    fallback_reason: str | None

    def as_normalized(self) -> NormalizedSignals:
        return NormalizedSignals(
            signal_source=self.signal_source,
            signal_method=self.signal_method,
            fallback_reason=self.fallback_reason,
            values={
                "evidence_support_count": float(self.evidence_support_count),
                "refutation_count": float(self.refutation_count),
                "evidence_diversity": float(self.evidence_diversity),
            },
        )

    def as_payload(self) -> dict[str, Any]:
        return {
            "claim_signals": {
                "evidence_support_count": int(self.evidence_support_count),
                "refutation_count": int(self.refutation_count),
                "evidence_diversity": float(self.evidence_diversity),
            },
            "signal_source": self.signal_source.value,
            "signal_method": self.signal_method.value,
            "fallback_reason": self.fallback_reason,
        }


def _fallback(reason: str) -> ClaimSignals:
    if reason not in CLAIM_FALLBACK_REASONS:
        raise AssertionError(
            f"claim fallback reason '{reason}' not in closed enum {sorted(CLAIM_FALLBACK_REASONS)}"
        )
    return ClaimSignals(
        evidence_support_count=0,
        refutation_count=0,
        evidence_diversity=0.0,
        signal_source=SignalSource.FALLBACK,
        signal_method=SignalMethod.EVIDENCE_LINKS,
        fallback_reason=reason,
    )


_CLAIM_KINDS: frozenset[str] = frozenset(
    {AssertionKind.CLAIM.value, AssertionKind.BELIEF.value}
)
_EVIDENCE_KINDS: frozenset[str] = frozenset(
    {AssertionKind.EVIDENCE.value, AssertionKind.REALITY_OBSERVATION.value}
)


def compute_claim_signals(
    *,
    target_event: Mapping[str, Any],
    link_events: Iterable[Mapping[str, Any]],
    evidence_events: Mapping[str, Mapping[str, Any]],
    as_of_time: str,
    max_depth: int = 64,
    allow_cross_agent: bool = False,
) -> ClaimSignals:
    """Compute claim signals for `target_event` from lineage.

    Inputs:
      - target_event: the claim/belief event being scored
      - link_events: iterable of `evidence_link_declared` events that
        reference this target's `event_id` (Phase 3 will source these
        from a LineageReader query; Phase 2 accepts them directly)
      - evidence_events: mapping from evidence event_id to the
        evidence event dict (used to verify assertion_kind and
        compute source diversity)
      - as_of_time: explicit TAI moment for replay determinism
      - max_depth: bounded walk (spec default 64)
      - allow_cross_agent: spec §4.5 — within-agent default; cross-agent
        requires explicit policy flag

    Returns ClaimSignals with `signal_source ∈ {computed, fallback}`.
    """
    # 1. Target must be a claim/belief and have assertion_kind set.
    target_assertion = target_event.get("assertion_kind")
    if target_assertion is None:
        return _fallback("assertion_kind_unset")
    if target_assertion not in _CLAIM_KINDS:
        return _fallback("not_claim_kind")

    target_event_id = target_event.get("event_id")
    target_agent_id = target_event.get("agent_id")

    # 2. Filter link_events to only those that reference this target,
    #    use latest-state selection, and apply scope policy.
    candidate_links = []
    for link_event in link_events:
        payload = link_event.get("payload") or {}
        if payload.get("claim_event_id") != target_event_id:
            continue
        # Cross-agent scope check on the link event itself.
        if not allow_cross_agent and link_event.get("agent_id") != target_agent_id:
            continue
        candidate_links.append(link_event)

    if not candidate_links:
        return _fallback("no_evidence_links")

    # Bounded walk — depth cap on the candidate set before resolution.
    if len(candidate_links) > max_depth:
        return _fallback("walk_depth_exceeded")

    resolved_by_link_id = select_latest_link_states(
        candidate_links, as_of_time=as_of_time
    )
    if not resolved_by_link_id:
        return _fallback("no_evidence_links")

    # 3. Validate each resolved link's evidence event by
    #    assertion_kind, compute counts and diversity.
    support_evidence_ids: list[str] = []
    refutation_evidence_ids: list[str] = []
    cross_scope_seen = False

    for link_id, link_event in resolved_by_link_id.items():
        payload = link_event.get("payload") or {}
        link_type = payload.get("link_type")
        evidence_event_id = payload.get("evidence_event_id")
        if not isinstance(evidence_event_id, str):
            continue

        evidence_event = evidence_events.get(evidence_event_id)
        if evidence_event is None:
            continue

        evidence_assertion = evidence_event.get("assertion_kind")
        if evidence_assertion not in _EVIDENCE_KINDS:
            continue

        if not allow_cross_agent and evidence_event.get("agent_id") != target_agent_id:
            cross_scope_seen = True
            continue

        if link_type == LinkType.SUPPORTS.value:
            support_evidence_ids.append(evidence_event_id)
        elif link_type == LinkType.REFUTES.value:
            refutation_evidence_ids.append(evidence_event_id)

    if not support_evidence_ids and not refutation_evidence_ids:
        if cross_scope_seen:
            return _fallback("cross_scope_denied")
        return _fallback("no_evidence_links")

    # Source diversity from supports only (refutations diversity is a
    # separate concept; v1 keeps the metric scoped to supports).
    distinct_sources: set[str] = set()
    for evidence_id in support_evidence_ids:
        ev = evidence_events.get(evidence_id) or {}
        source = ev.get("source_class") or "unknown"
        distinct_sources.add(source)

    if support_evidence_ids:
        diversity = max(
            0.0, min(1.0, len(distinct_sources) / len(support_evidence_ids))
        )
    else:
        diversity = 0.0

    return ClaimSignals(
        evidence_support_count=len(support_evidence_ids),
        refutation_count=len(refutation_evidence_ids),
        evidence_diversity=diversity,
        signal_source=SignalSource.COMPUTED,
        signal_method=SignalMethod.EVIDENCE_LINKS,
        fallback_reason=None,
    )
