"""compute_recall_signals — lineage walker for `confidence_in_recall_process`.

Spec: specs/EPISTEMIC_TRIANGLE.md §6

Walks prior `recalled` events for the same `memory_id` and computes:

  - recall_count: total prior recalls within the bounded history
  - reconstruction_variance: payload-drift across last N recalls
  - time_since_last_recall_myr: solar_age_myr delta from last recall

Spec §6.1 admits the limitation: Jaccard distance over a canonical
projection measures PAYLOAD DRIFT, not recall-process integrity in
general. Adversarial recalls that keep the projection stable while
shifting semantic meaning will be undetected by v1. Phase 2
falsification hook 6c verifies that v1 does not detect such cases
and emits a limitation marker. v8 candidate: embedding-distance
variant.

Pure function, replay-deterministic. `as_of_time` and
`time_since_last_recall_myr` come from lineage `solar_age_myr` deltas;
no wall-clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from src.explicit_memory.signals import (
    NormalizedSignals,
    SignalMethod,
    SignalSource,
)


# Closed enum for recall signal fallback reasons (spec §6).
RECALL_FALLBACK_REASONS: frozenset[str] = frozenset({
    "first_recall",
    "single_recall",
    "walk_depth_exceeded",
    "assertion_kind_unset",
    "cross_scope_denied",
})


@dataclass(frozen=True)
class RecallSignals:
    recall_count: int
    reconstruction_variance: float
    time_since_last_recall_myr: float | None
    signal_source: SignalSource
    signal_method: SignalMethod
    fallback_reason: str | None
    # Hook 6c limitation marker — set when v1 cannot detect the
    # adversarial stable-projection-with-drifting-meaning case but
    # walker semantics are otherwise computed (not fallback).
    limitation_marker: str | None = None

    def as_normalized(self) -> NormalizedSignals:
        return NormalizedSignals(
            signal_source=self.signal_source,
            signal_method=self.signal_method,
            fallback_reason=self.fallback_reason,
            values={
                "recall_count": float(self.recall_count),
                "reconstruction_variance": float(self.reconstruction_variance),
                "time_since_last_recall_myr": (
                    float(self.time_since_last_recall_myr)
                    if self.time_since_last_recall_myr is not None
                    else 0.0
                ),
            },
        )

    def as_payload(self) -> dict[str, Any]:
        return {
            "recall_signals": {
                "recall_count": int(self.recall_count),
                "reconstruction_variance": float(self.reconstruction_variance),
                "time_since_last_recall_myr": self.time_since_last_recall_myr,
            },
            "signal_source": self.signal_source.value,
            "signal_method": self.signal_method.value,
            "fallback_reason": self.fallback_reason,
            "limitation_marker": self.limitation_marker,
        }


def _fallback(reason: str, *, recall_count: int = 0) -> RecallSignals:
    if reason not in RECALL_FALLBACK_REASONS:
        raise AssertionError(
            f"recall fallback reason '{reason}' not in closed enum {sorted(RECALL_FALLBACK_REASONS)}"
        )
    return RecallSignals(
        recall_count=recall_count,
        reconstruction_variance=0.0,
        time_since_last_recall_myr=None,
        signal_source=SignalSource.FALLBACK,
        signal_method=SignalMethod.RECALL_HISTORY,
        fallback_reason=reason,
    )


def _projection_set(payload: Mapping[str, Any], memory_id: str, assertion_kind: str | None) -> frozenset[str]:
    """Canonical projection over which Jaccard variance is computed.

    Spec §6.1: `{memory_id, assertion_kind, payload.claim, payload.evidence_ids}`.

    The projection is a frozenset of typed string tokens so order
    doesn't affect Jaccard. Unset fields contribute no token (rather
    than a sentinel), keeping the projection minimal when payloads
    are sparse.
    """
    tokens: set[str] = set()
    tokens.add(f"memory_id:{memory_id}")
    if assertion_kind is not None:
        tokens.add(f"assertion_kind:{assertion_kind}")
    claim_text = payload.get("claim")
    if isinstance(claim_text, str) and claim_text:
        tokens.add(f"claim:{claim_text}")
    evidence_ids = payload.get("evidence_ids")
    if isinstance(evidence_ids, (list, tuple)):
        for eid in evidence_ids:
            if isinstance(eid, str) and eid:
                tokens.add(f"evidence_id:{eid}")
    return frozenset(tokens)


def _jaccard_distance(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    intersection = a & b
    return 1.0 - (len(intersection) / len(union))


def _adversarial_drift_marker(
    *,
    target_payload: Mapping[str, Any],
    prior_payloads: list[Mapping[str, Any]],
    target_projection: frozenset[str],
    prior_projections: list[frozenset[str]],
) -> str | None:
    """Heuristic for hook 6c: when the canonical projection is
    stable across recalls but a richer payload field (e.g.
    `meaning`, `interpretation`, free-form `text`) diverges, emit a
    limitation marker so the failure case is visible in lineage.

    The marker does not change the signal value; it records that v1's
    Jaccard projection cannot detect the drift and a downstream
    auditor should be aware. v8's embedding variant is intended to
    close this.
    """
    # If projections are not stable, no adversarial case to flag.
    if any(target_projection != p for p in prior_projections):
        return None
    # Look for a meaning-bearing field that differs across recalls.
    drift_fields = ("meaning", "interpretation", "text")
    for field_name in drift_fields:
        target_value = target_payload.get(field_name)
        if target_value is None:
            continue
        for prior in prior_payloads:
            prior_value = prior.get(field_name)
            if prior_value is not None and prior_value != target_value:
                return "stable_projection_with_drifting_meaning"
    return None


def compute_recall_signals(
    *,
    target_event: Mapping[str, Any],
    prior_recall_events: Iterable[Mapping[str, Any]],
    as_of_time: str,
    max_history: int = 64,
    allow_cross_agent: bool = False,
) -> RecallSignals:
    """Compute recall signals for `target_event` from prior recalls.

    Inputs:
      - target_event: the `recalled` event being scored
      - prior_recall_events: iterable of prior `recalled` events for
        the SAME memory_id (Phase 3 sources via LineageReader)
      - as_of_time: explicit TAI moment, replay-deterministic
      - max_history: bounded window (spec default 64)
      - allow_cross_agent: spec — within-agent default

    Returns RecallSignals with appropriate signal_source.
    """
    memory_id = target_event.get("memory_id") or ""
    target_agent_id = target_event.get("agent_id")
    target_assertion = target_event.get("assertion_kind")

    # Filter prior recalls: same memory_id, within scope, before
    # target's pm_tai_iso (or as_of_time if earlier).
    target_pm = target_event.get("physical_moment") or {}
    target_tai = target_pm.get("tai_iso") or target_event.get("event_time") or ""
    cutoff = min(target_tai, as_of_time) if (target_tai and as_of_time) else (target_tai or as_of_time)

    cross_scope_seen = False
    history: list[Mapping[str, Any]] = []
    for ev in prior_recall_events:
        if ev.get("event_type") != "recalled":
            continue
        if ev.get("memory_id") != memory_id:
            continue
        if not allow_cross_agent and ev.get("agent_id") != target_agent_id:
            cross_scope_seen = True
            continue
        ev_pm = ev.get("physical_moment") or {}
        ev_tai = ev_pm.get("tai_iso") or ev.get("event_time") or ""
        if cutoff and ev_tai >= cutoff:
            continue
        history.append(ev)

    if len(history) > max_history:
        return _fallback("walk_depth_exceeded", recall_count=len(history))

    # Canonical ordering by (pm_tai_iso, pm_sequence_in_stream, event_id).
    def _ordering_key(e: Mapping[str, Any]) -> tuple:
        pm = e.get("physical_moment") or {}
        seq = pm.get("sequence_in_stream")
        if seq is None:
            seq = -1
        return (
            pm.get("tai_iso") or e.get("event_time") or "",
            int(seq),
            e.get("event_id") or "",
        )

    history_sorted = sorted(history, key=_ordering_key)

    if len(history_sorted) == 0:
        if cross_scope_seen and not history_sorted:
            return _fallback("cross_scope_denied")
        return _fallback("first_recall")
    if len(history_sorted) == 1:
        # We have one prior — variance needs at least two points
        # to form a meaningful pairwise distance series. Return
        # single_recall fallback but include the recall_count.
        last_pm = history_sorted[-1].get("physical_moment") or {}
        last_age = last_pm.get("solar_age_myr")
        target_age = target_pm.get("solar_age_myr")
        time_delta: float | None = None
        if isinstance(last_age, (int, float)) and isinstance(target_age, (int, float)):
            time_delta = max(0.0, float(target_age) - float(last_age))
        return RecallSignals(
            recall_count=len(history_sorted),
            reconstruction_variance=0.0,
            time_since_last_recall_myr=time_delta,
            signal_source=SignalSource.FALLBACK,
            signal_method=SignalMethod.RECALL_HISTORY,
            fallback_reason="single_recall",
        )

    # Build projections: target + last N prior recalls (already
    # length >= 2). Variance = mean pairwise Jaccard distance over
    # successive pairs PLUS distance from latest prior to target.
    target_projection = _projection_set(
        target_event.get("payload") or {},
        memory_id,
        target_assertion,
    )
    prior_projections: list[frozenset[str]] = []
    prior_payloads: list[Mapping[str, Any]] = []
    for prior in history_sorted:
        prior_payloads.append(prior.get("payload") or {})
        prior_projections.append(
            _projection_set(
                prior.get("payload") or {},
                memory_id,
                prior.get("assertion_kind"),
            )
        )

    distances: list[float] = []
    for prev, curr in zip(prior_projections, prior_projections[1:]):
        distances.append(_jaccard_distance(prev, curr))
    distances.append(_jaccard_distance(prior_projections[-1], target_projection))
    variance = sum(distances) / len(distances) if distances else 0.0

    # time_since_last_recall_myr from solar_age_myr deltas.
    last_pm = history_sorted[-1].get("physical_moment") or {}
    last_age = last_pm.get("solar_age_myr")
    target_age = target_pm.get("solar_age_myr")
    time_delta = None
    if isinstance(last_age, (int, float)) and isinstance(target_age, (int, float)):
        time_delta = max(0.0, float(target_age) - float(last_age))

    limitation_marker = _adversarial_drift_marker(
        target_payload=target_event.get("payload") or {},
        prior_payloads=prior_payloads,
        target_projection=target_projection,
        prior_projections=prior_projections,
    )

    return RecallSignals(
        recall_count=len(history_sorted),
        reconstruction_variance=max(0.0, min(1.0, variance)),
        time_since_last_recall_myr=time_delta,
        signal_source=SignalSource.COMPUTED,
        signal_method=SignalMethod.RECALL_HISTORY,
        fallback_reason=None,
        limitation_marker=limitation_marker,
    )
