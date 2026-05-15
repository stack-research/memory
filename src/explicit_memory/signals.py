"""Normalized signal taxonomy across the three uncertainty axes.

Spec: specs/EPISTEMIC_TRIANGLE.md §7

All three axis-signal types share the common shape:

  signal_source: "computed" | "cache" | "fallback"
  signal_method: "provenance_chain" | "evidence_links" | "recall_history" | "none"
  fallback_reason: str | None  (closed per-axis enum)

`signal_source` semantics:
  - `computed` — derived from a live lineage walk at score time.
  - `cache` — derived from a previously-emitted canonical
    `*_signals_computed` lineage event still valid at as_of_time.
    Cache MUST be backed by canonical lineage, not S3 Vector
    metadata (per the v1.2 promotion-review caution #2).
  - `fallback` — signal could not be computed; default values used.

`signal_method` names which walker produced the signal.

The provenance writer (PROVENANCE_SIGNAL_WRITER) was implemented
before this taxonomy and uses `provenance_signal_source ∈ {computed,
cache, fallback}` already. The adapter `normalize_provenance_signals`
maps that into the common shape so `score_triple` and audits can
treat all three axes uniformly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SignalSource(str, Enum):
    COMPUTED = "computed"
    CACHE = "cache"
    FALLBACK = "fallback"


class SignalMethod(str, Enum):
    PROVENANCE_CHAIN = "provenance_chain"
    EVIDENCE_LINKS = "evidence_links"
    RECALL_HISTORY = "recall_history"
    NONE = "none"


SIGNAL_SOURCE_ENUM: frozenset[str] = frozenset(s.value for s in SignalSource)
SIGNAL_METHOD_ENUM: frozenset[str] = frozenset(m.value for m in SignalMethod)


@dataclass(frozen=True)
class NormalizedSignals:
    """Common shape across claim, recall, and provenance signal types.

    Per-axis dataclasses (`ClaimSignals`, `RecallSignals`,
    `ProvenanceSignals`) carry their axis-specific numeric outputs.
    `NormalizedSignals` is the projection used by `score_triple`'s
    fallback policy and by audit queries.
    """

    signal_source: SignalSource
    signal_method: SignalMethod
    fallback_reason: str | None
    # Axis-specific values forwarded as a flat dict so audits can
    # join uniformly. Per-axis types own the typed forms; this is the
    # cross-axis projection.
    values: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "signal_source": self.signal_source.value,
            "signal_method": self.signal_method.value,
            "fallback_reason": self.fallback_reason,
            "values": dict(self.values),
        }


def normalize_provenance_signals(provenance_signals: Any) -> NormalizedSignals:
    """Adapter from `ProvenanceSignals` (defined in provenance.py) to
    the common shape.

    Maps the existing `provenance_signal_source` enum
    {computed, cache, fallback} onto `SignalSource`. Missing or
    unrecognized values are mapped to `FALLBACK` with a reason of
    `unrecognized_signal_source` so the loss-of-information is loud,
    not silent.
    """
    raw_source = getattr(provenance_signals, "provenance_signal_source", None)
    fallback_reason = getattr(provenance_signals, "fallback_reason", None)
    if raw_source in SIGNAL_SOURCE_ENUM:
        source = SignalSource(raw_source)
    else:
        source = SignalSource.FALLBACK
        if fallback_reason is None:
            fallback_reason = "unrecognized_signal_source"

    values = {
        "parent_chain_depth": float(getattr(provenance_signals, "parent_chain_depth", 0)),
        "source_diversity": float(getattr(provenance_signals, "source_diversity", 0.0)),
        "age_of_original_source": float(
            getattr(provenance_signals, "age_of_original_source", 0.0)
        ),
        "chain_length": int(getattr(provenance_signals, "chain_length", 0)),
        "distinct_source_classes": int(
            getattr(provenance_signals, "distinct_source_classes", 0)
        ),
    }

    return NormalizedSignals(
        signal_source=source,
        signal_method=SignalMethod.PROVENANCE_CHAIN,
        fallback_reason=fallback_reason,
        values=values,
    )
