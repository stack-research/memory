from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from astropy.time import Time

from .epistemic_triangle import (
    AssertionKind,
    RecordKind,
    lookup_event_type,
)
from .heliotime import PhysicalMoment, physical_moment as compute_pm
from .storage import LineageStorage
from .timekeeping import HLC, BatchCommit
from .timekeeping.context import HLC_VARIANT_DEFAULT
from .types import MemoryEvent, new_event


TIER1B_NULL_REASON_ENUM: frozenset[str] = frozenset({
    "machine_origin",
    "observer_did_not_report",
    "ntp_unavailable",
    "tz_undeclared",
})

TIER2_NULL_REASON_ENUM: frozenset[str] = frozenset({
    "source_absent",
    "calculator_unavailable",
    "time_context_missing",
    "unsupported_scale",
    "ephemeris_unavailable",
})


@dataclass
class StreamState:
    # Per EPISTEMIC_TRIANGLE spec §10: initial value -1 so emit's
    # pre-increment produces sequence_in_stream=0 for the first
    # event in every stream (including __canonical_meta__ and every
    # application stream).
    sequence: int = -1
    hlc: HLC = field(default_factory=HLC)


class LineageEngine:
    """v6 lineage emitter.

    Per spec §5–§8, every emit produces a `physical_moment` block with:
      - Tier 1a non-nullable (tai_iso, solar_age_myr, ecliptic_lon_deg,
        sequence_in_stream, hlc_timestamp, time_context_id)
      - Tier 1b required-nullable (local_civil_time_observed,
        tz_offset_seconds, ntp_state) with closed reason enum
      - Tier 2 computed-or-null with closed reason enum
      - Tier 3 by reference (time_context_id)
      - Tier 4 logical (hlc_timestamp, kulkarni_2014 by default)

    The engine owns per-stream sequence and HLC state. Bootstrap is the
    caller's responsibility; see `src.timekeeping.events.BootstrapBatch`
    and the `bootstrap_v6` helper.
    """

    def __init__(
        self,
        storage: LineageStorage | None,
        *,
        time_context_id: str,
        hlc_variant: str = HLC_VARIANT_DEFAULT,
        default_tai_moment: PhysicalMoment | None = None,
    ) -> None:
        self.storage = storage
        self._time_context_id = time_context_id
        self._hlc_variant = hlc_variant
        self._streams: dict[str, StreamState] = {}
        # Optional caller-supplied bootstrap moment used by emit()
        # when no per-call tai_moment is passed. Never wall-clock —
        # always explicit. Useful for experiments that emit many
        # events from a single fixed bootstrap anchor.
        self._default_tai_moment = default_tai_moment

    @property
    def time_context_id(self) -> str:
        return self._time_context_id

    def stream_state(self, stream_id: str) -> StreamState:
        return self._streams.setdefault(stream_id, StreamState())

    def emit(
        self,
        *,
        event_type: str,
        agent_id: str,
        stream_id: str,
        memory_id: str,
        payload: dict[str, Any],
        tai_moment: PhysicalMoment | None = None,
        actor_class: str = "system_worker",
        source_class: str = "internal_engine",
        parent_event_id: str | None = None,
        local_civil_time_observed: str | None = None,
        tz_offset_seconds: int | None = None,
        ntp_state: str | None = None,
        tier1b_null_reasons: dict[str, str] | None = None,
        tier2: dict[str, Any] | None = None,
        tier2_null_reasons: dict[str, str] | None = None,
        bootstrap_self_reference: bool = False,
        # v7 EPISTEMIC_TRIANGLE envelope additions. record_kind and
        # assertion_kind are auto-derived from the static mapping
        # table when not supplied; callers may override (e.g.
        # `stored` events whose assertion_kind is per-payload). If
        # auto-derivation fails (unmapped event_type or per-payload
        # row without explicit assertion_kind), validation will
        # quarantine in Phase 3+ ingestion.
        record_kind: str | None = None,
        assertion_kind: str | None = None,
        subject_event_id: str | None = None,
        subject_record_kind: str | None = None,
        subject_assertion_kind: str | None = None,
    ) -> MemoryEvent:
        """Emit a canonical v6 event with a fully-populated physical_moment block.

        Caller supplies `tai_moment` (PhysicalMoment) — there is no wall-clock
        fallback. Civil-time witness data is optional but the field must be
        accompanied by a reason from the closed enum when null.

        `bootstrap_self_reference=True` is used only when emitting a
        `time_context_declared` event whose `time_context_id` self-references;
        in that case the engine's active time_context_id may equal the id
        being declared.
        """
        # Tier 1a — engine-owned state, no caller input.
        if tai_moment is None:
            if self._default_tai_moment is None:
                raise ValueError(
                    "tai_moment is required on emit() unless the engine "
                    "was constructed with default_tai_moment (no wall-clock fallback)"
                )
            tai_moment = self._default_tai_moment
        state = self.stream_state(stream_id)
        state.sequence += 1
        hlc_state = state.hlc.step(tai_moment.tai_iso)

        # Tier 1b — required-nullable with closed reason enum.
        tier1b = _build_tier1b(
            local_civil_time_observed=local_civil_time_observed,
            tz_offset_seconds=tz_offset_seconds,
            ntp_state=ntp_state,
            null_reasons=tier1b_null_reasons or {},
        )

        # Tier 2 — caller may supply computed values or null reasons.
        tier2_block, tier2_null_block = _build_tier2(
            values=tier2 or {},
            null_reasons=tier2_null_reasons or {},
            tai_iso=tai_moment.tai_iso,
        )

        physical_moment_block: dict[str, Any] = {
            # Tier 1a
            "tai_iso": tai_moment.tai_iso,
            "solar_age_myr": tai_moment.solar_age_myr,
            "ecliptic_lon_deg": tai_moment.ecliptic_lon_deg,
            "sequence_in_stream": state.sequence,
            "hlc_timestamp": f"{hlc_state.phys_ns}.{hlc_state.logical}",
            "hlc_signature_eligible": True,
            "time_context_id": self._time_context_id,
            # Tier 1b
            **tier1b,
            # Tier 2
            **tier2_block,
            **tier2_null_block,
        }

        # v7 envelope: derive record_kind / assertion_kind from the
        # mapping table when callers don't supply them. Per-payload
        # rows (like `stored`) need explicit assertion_kind from
        # callers; the validator catches missing values at ingest.
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

        event = new_event(
            event_type=event_type,
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            payload=payload,
            actor_class=actor_class,
            source_class=source_class,
            physical_moment=physical_moment_block,
            parent_event_id=parent_event_id,
            record_kind=record_kind,
            assertion_kind=assertion_kind,
            subject_event_id=subject_event_id,
            subject_record_kind=subject_record_kind,
            subject_assertion_kind=subject_assertion_kind,
        )

        if self.storage is not None:
            self.storage.append_event(event)
        return event


def _build_tier1b(
    *,
    local_civil_time_observed: str | None,
    tz_offset_seconds: int | None,
    ntp_state: str | None,
    null_reasons: dict[str, str],
) -> dict[str, Any]:
    """Build the Tier 1b block, enforcing closed reason enum for nulls."""
    fields = {
        "local_civil_time_observed": local_civil_time_observed,
        "tz_offset_seconds": tz_offset_seconds,
        "ntp_state": ntp_state,
    }
    out: dict[str, Any] = {}
    reasons: dict[str, str] = {}
    for name, value in fields.items():
        out[name] = value
        if value is None:
            reason = null_reasons.get(name, "observer_did_not_report")
            if reason not in TIER1B_NULL_REASON_ENUM:
                raise ValueError(
                    f"Tier 1b null reason '{reason}' for '{name}' not in closed enum"
                )
            reasons[name] = reason
    out["tier1b_null_reasons"] = reasons
    return out


def _build_tier2(
    *,
    values: dict[str, Any],
    null_reasons: dict[str, str],
    tai_iso: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build Tier 2 fields. Engine computes utc_iso by default (UTC-derived
    by §5.2). Other Tier 2 fields are caller-supplied or null+reason.
    """
    block: dict[str, Any] = {}
    null_block: dict[str, str] = {}

    defaults_computed = {"utc_iso": _utc_iso_from_tai(tai_iso)}

    field_names = (
        "utc_iso",
        "leap_second_pending",
        "gps_time",
        "tt_iso",
        "sidereal_time",
        "lunar_age_days",
        "day_of_year",
        "iso_week_date",
    )
    for name in field_names:
        if name in values:
            block[name] = values[name]
        elif name in defaults_computed:
            block[name] = defaults_computed[name]
        else:
            reason = null_reasons.get(name, "source_absent")
            if reason not in TIER2_NULL_REASON_ENUM:
                raise ValueError(
                    f"Tier 2 null reason '{reason}' for '{name}' not in closed enum"
                )
            block[name] = None
            null_block[name] = reason

    return block, {"tier2_null_reasons": null_block}


def _utc_iso_from_tai(tai_iso: str) -> str:
    """Convert a TAI ISO string to UTC ISO via astropy.

    Format auto-detection: astropy's `Time` accepts both `T` and space
    separators; pinning `format="isot"` rejects trailing-zero-stripped
    inputs that astropy itself emits via `.isot`. Let astropy infer.
    """
    t = Time(tai_iso, scale="tai")
    return t.utc.isot
