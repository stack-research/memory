from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.epistemic_triangle import lookup_event_type
from src.heliotime import PhysicalMoment, physical_moment as compute_pm
from src.implicit_memory.lineage_events import emit_implicit_event
from src.implicit_memory.replay import rebuild_from_lineage
from src.lineage_engine import _build_tier1b, _build_tier2
from src.timekeeping import HLC
from src.timekeeping.context import HLC_VARIANT_DEFAULT


# Deterministic fixed bootstrap moment for in-memory experiment suites.
# Replay must be byte-stable across runs; no wall-clock allowed.
_EXPERIMENT_TAI_ANCHOR = "2026-05-13T12:00:00.000"
_EXPERIMENT_TIME_CONTEXT_ID = "exp-in-memory-bootstrap-v7"


@dataclass
class InMemoryLineageEngine:
    """In-memory v7 lineage emitter for the implicit experiment suites.

    Mirrors `LineageEngine` v7 semantics: per-stream sequence (init
    -1 so first event lands at seq=0 per EPISTEMIC_TRIANGLE §10) +
    HLC, full `physical_moment` block on every event,
    `record_kind`/`assertion_kind` auto-derived from the mapping
    table, no wall-clock reads.
    """

    events: list[dict[str, Any]]
    time_context_id: str = _EXPERIMENT_TIME_CONTEXT_ID
    hlc_variant: str = HLC_VARIANT_DEFAULT
    _seq_by_stream: dict[str, int] = field(default_factory=dict)
    _hlc_by_stream: dict[str, HLC] = field(default_factory=dict)
    _tick_offset: int = 0

    def emit(
        self,
        *,
        event_type: str,
        agent_id: str,
        stream_id: str,
        memory_id: str,
        payload: dict,
        actor_class: str = "implicit_memory_controller",
        source_class: str = "internal_engine",
        parent_event_id: str | None = None,
        tai_moment: PhysicalMoment | None = None,
        local_civil_time_observed: str | None = None,
        tz_offset_seconds: int | None = None,
        ntp_state: str | None = None,
        # v7 EPISTEMIC_TRIANGLE envelope additions; auto-derived
        # from the mapping table when not supplied.
        record_kind: str | None = None,
        assertion_kind: str | None = None,
        subject_event_id: str | None = None,
        subject_record_kind: str | None = None,
        subject_assertion_kind: str | None = None,
    ):
        event_id = f"evt-{len(self.events)+1:06d}"

        if tai_moment is None:
            # Deterministic tick from the fixed anchor — no wall-clock read.
            tai_moment = compute_pm(_EXPERIMENT_TAI_ANCHOR, scale="tai")
            self._tick_offset += 1

        # v7 §10: StreamState init -1; pre-increment so first event
        # in every stream gets sequence_in_stream=0.
        current = self._seq_by_stream.get(stream_id, -1)
        self._seq_by_stream[stream_id] = current + 1
        hlc = self._hlc_by_stream.setdefault(stream_id, HLC())
        hlc_state = hlc.step(tai_moment.tai_iso)

        tier1b = _build_tier1b(
            local_civil_time_observed=local_civil_time_observed,
            tz_offset_seconds=tz_offset_seconds,
            ntp_state=ntp_state,
            null_reasons={
                "local_civil_time_observed": "machine_origin",
                "tz_offset_seconds": "tz_undeclared",
                "ntp_state": "ntp_unavailable",
            },
        )
        tier2_block, tier2_nulls = _build_tier2(
            values={},
            null_reasons={
                "leap_second_pending": "calculator_unavailable",
                "gps_time": "source_absent",
                "tt_iso": "calculator_unavailable",
                "sidereal_time": "calculator_unavailable",
                "lunar_age_days": "calculator_unavailable",
                "day_of_year": "calculator_unavailable",
                "iso_week_date": "calculator_unavailable",
            },
            tai_iso=tai_moment.tai_iso,
        )

        physical_moment = {
            "tai_iso": tai_moment.tai_iso,
            "solar_age_myr": tai_moment.solar_age_myr,
            "ecliptic_lon_deg": tai_moment.ecliptic_lon_deg,
            "sequence_in_stream": self._seq_by_stream[stream_id],
            "hlc_timestamp": f"{hlc_state.phys_ns}.{hlc_state.logical}",
            "hlc_signature_eligible": True,
            "time_context_id": self.time_context_id,
            **tier1b,
            **tier2_block,
            **tier2_nulls,
        }

        # v7: auto-derive record_kind / assertion_kind from mapping
        # when caller hasn't supplied them.
        mapping = lookup_event_type(event_type)
        if mapping is not None:
            if record_kind is None:
                record_kind = mapping.record_kind.value
            if assertion_kind is None and not mapping.assertion_kind_per_payload:
                assertion_kind = (
                    mapping.assertion_kind.value
                    if mapping.assertion_kind is not None
                    else None
                )

        event = {
            "event_id": event_id,
            "event_type": event_type,
            "agent_id": agent_id,
            "stream_id": stream_id,
            "memory_id": memory_id,
            # v7: no event_time field. Consumers that need the
            # canonical anchor read physical_moment["tai_iso"].
            "schema_version": "7.0",
            "payload": payload,
            "actor_class": actor_class,
            "source_class": source_class,
            "parent_event_id": parent_event_id,
            "physical_moment": physical_moment,
            "record_kind": record_kind,
            "assertion_kind": assertion_kind,
            "subject_event_id": subject_event_id,
            "subject_record_kind": subject_record_kind,
            "subject_assertion_kind": subject_assertion_kind,
        }
        self.events.append(event)

        class E:
            pass

        out = E()
        out.event_id = event_id
        out.event_type = event_type
        out.memory_id = memory_id
        return out


def emit(lineage: InMemoryLineageEngine, *, event_type: str, agent_id: str, stream_id: str, memory_id: str, payload: dict, parent_event_id: str | None = None) -> dict[str, Any]:
    return emit_implicit_event(
        lineage=lineage,  # type: ignore[arg-type]
        event_type=event_type,
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload=payload,
        parent_event_id=parent_event_id,
    )


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    return rebuild_from_lineage(events)
