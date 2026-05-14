from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.lineage_reader import LineageReader


@dataclass(frozen=True)
class ProvenanceSignals:
    parent_chain_depth: int
    source_diversity: float
    age_of_original_source: float
    chain_root_event_id: str | None
    chain_length: int
    distinct_source_classes: int
    computed_at: str
    as_of_time: str
    fallback_reason: str | None = None
    provenance_signal_source: str = "computed"

    def as_payload(self) -> dict[str, Any]:
        return {
            "provenance_signals": {
                "parent_chain_depth": float(self.parent_chain_depth),
                "source_diversity": float(self.source_diversity),
                "age_of_original_source": float(self.age_of_original_source),
            },
            "chain_root_event_id": self.chain_root_event_id,
            "chain_length": self.chain_length,
            "distinct_source_classes": self.distinct_source_classes,
            "computed_at": self.computed_at,
            "as_of_time": self.as_of_time,
            "fallback_reason": self.fallback_reason,
            "provenance_signal_source": self.provenance_signal_source,
        }


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _fallback(
    *,
    computed_at: str,
    as_of_time: str,
    reason: str,
    hours_stale: float = 0.0,
    partial_depth: int = 0,
) -> ProvenanceSignals:
    return ProvenanceSignals(
        parent_chain_depth=max(0, int(partial_depth)),
        source_diversity=0.0,
        age_of_original_source=max(0.0, float(hours_stale)),
        chain_root_event_id=None,
        chain_length=0,
        distinct_source_classes=0,
        computed_at=computed_at,
        as_of_time=as_of_time,
        fallback_reason=reason,
        provenance_signal_source="fallback",
    )


def compute_chain_signals(
    *,
    memory_id: str,
    stream_id: str,
    as_of_time: str,
    lineage_reader: LineageReader,
    computed_at: str,
    max_chain_depth: int = 64,
) -> ProvenanceSignals:
    # Per TAI_TIMEKEEPING spec §13 and the 2026-05-13 rating soft-spot #2:
    # `computed_at` must be a replay-derived TAI moment supplied by the caller.
    # No wall-clock fallback. Empty string is rejected so the signal is loud.
    if not computed_at:
        raise ValueError(
            "compute_chain_signals: computed_at is required (TAI from loop tick); "
            "wall-clock fallback removed per TAI_TIMEKEEPING spec"
        )
    now_iso = computed_at

    try:
        events = lineage_reader.query_memory_events(
            stream_id=stream_id,
            memory_id=memory_id,
            as_of_time=as_of_time,
        )
    except Exception:
        return _fallback(
            computed_at=now_iso,
            as_of_time=as_of_time,
            reason="lineage_query_failed",
        )

    if not events:
        return _fallback(
            computed_at=now_iso,
            as_of_time=as_of_time,
            reason="missing_chain",
        )

    by_id = {e.get("event_id", ""): e for e in events if e.get("event_id")}
    if not by_id:
        return _fallback(
            computed_at=now_iso,
            as_of_time=as_of_time,
            reason="missing_event_id",
        )

    latest_time = max(e.get("event_time", "") for e in by_id.values())
    latest_candidates = [e for e in by_id.values() if e.get("event_time", "") == latest_time]
    latest = min(latest_candidates, key=lambda e: e.get("event_id", ""))

    depth = 0
    chain_ids: list[str] = []
    cursor = latest
    seen: set[str] = set()
    while True:
        eid = cursor.get("event_id", "")
        if not eid:
            return _fallback(
                computed_at=now_iso,
                as_of_time=as_of_time,
                reason="missing_event_id",
            )
        if eid in seen:
            return _fallback(
                computed_at=now_iso,
                as_of_time=as_of_time,
                reason="cycle_detected",
                partial_depth=depth,
            )
        seen.add(eid)
        chain_ids.append(eid)

        parent_id = cursor.get("parent_event_id")
        if not parent_id:
            root = cursor
            break

        parent = by_id.get(parent_id)
        if parent is None:
            return _fallback(
                computed_at=now_iso,
                as_of_time=as_of_time,
                reason="broken_parent_link",
            )
        depth += 1
        if depth >= max(1, int(max_chain_depth)):
            return _fallback(
                computed_at=now_iso,
                as_of_time=as_of_time,
                reason="max_chain_depth_exceeded",
                partial_depth=depth,
            )
        cursor = parent

    chain_events = [by_id[eid] for eid in chain_ids if eid in by_id]
    chain_length = len(chain_events)
    if chain_length <= 0:
        return _fallback(computed_at=now_iso, as_of_time=as_of_time, reason="missing_chain")

    source_classes = [
        (e.get("source_class") or "unknown")
        for e in chain_events
    ]
    distinct_source_classes = len(set(source_classes))
    source_diversity = max(0.0, min(1.0, distinct_source_classes / chain_length))

    try:
        root_time = _parse_iso(root.get("event_time", ""))
        as_of_dt = _parse_iso(as_of_time)
        age_hours = max(0.0, (as_of_dt - root_time).total_seconds() / 3600.0)
    except Exception:
        age_hours = 0.0

    return ProvenanceSignals(
        parent_chain_depth=depth,
        source_diversity=source_diversity,
        age_of_original_source=age_hours,
        chain_root_event_id=root.get("event_id"),
        chain_length=chain_length,
        distinct_source_classes=distinct_source_classes,
        computed_at=now_iso,
        as_of_time=as_of_time,
        fallback_reason=None,
        provenance_signal_source="computed",
    )
