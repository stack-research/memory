"""
Phase 2 self-test: physical_moment block on canonical v6 events.

Contracts verified:
  - MemoryEvent requires physical_moment with Tier 1a non-nullable.
  - new_event refuses a missing/empty tai_iso (no wall-clock fallback).
  - LineageEngine.emit produces a full physical_moment block:
      Tier 1a (engine-owned): tai_iso, solar_age_myr, ecliptic_lon_deg,
                              sequence_in_stream, hlc_timestamp,
                              hlc_signature_eligible, time_context_id
      Tier 1b (caller / nullable+reason): local_civil_time_observed,
                                          tz_offset_seconds, ntp_state
      Tier 2 (computed/null+reason): utc_iso always computed; others
                                     null with reason from closed enum
  - sequence_in_stream and HLC are per-stream and monotonic.
  - Replay determinism: same inputs => same physical_moment.
  - Wall-clock leak in compute_chain_signals.computed_at is closed.
  - InMemoryLineageEngine carries the same v6 envelope.

Run:
  PYTHONPATH=. uv run --project stacks python -m src.timekeeping._phase2_verify
"""

from __future__ import annotations

import sys
from typing import Callable

from src.experiments.implicit.common import InMemoryLineageEngine
from src.explicit_memory.provenance import compute_chain_signals
from src.heliotime import PhysicalMoment, physical_moment
from src.lineage_engine import LineageEngine
from src.types import EVENT_SCHEMA_VERSION, MemoryEvent, new_event


CTX_ID = "test-time-context-v6"
ANCHOR_TAI = "2026-05-13T12:00:00.000"


def _engine() -> LineageEngine:
    return LineageEngine(storage=None, time_context_id=CTX_ID)


def _moment(tai_iso: str = ANCHOR_TAI) -> PhysicalMoment:
    return physical_moment(tai_iso, scale="tai")


# --- contract checks --------------------------------------------------------


def test_schema_version_is_v6() -> None:
    assert EVENT_SCHEMA_VERSION == "6.0", f"expected 6.0, got {EVENT_SCHEMA_VERSION}"


def test_new_event_requires_physical_moment_tai_iso() -> None:
    try:
        new_event(
            event_type="probe",
            agent_id="a",
            stream_id="s",
            memory_id="m",
            payload={},
            actor_class="t",
            source_class="t",
            physical_moment={},
        )
    except ValueError as exc:
        assert "tai_iso" in str(exc)
        return
    raise AssertionError("new_event with empty physical_moment was accepted")


def test_engine_emit_tier1a_fields() -> None:
    eng = _engine()
    moment = _moment()
    evt = eng.emit(
        event_type="probe",
        agent_id="a",
        stream_id="s1",
        memory_id="m1",
        payload={"k": "v"},
        tai_moment=moment,
    )
    pm = evt.physical_moment
    for f in (
        "tai_iso",
        "solar_age_myr",
        "ecliptic_lon_deg",
        "sequence_in_stream",
        "hlc_timestamp",
        "time_context_id",
    ):
        assert pm.get(f) is not None, f"Tier 1a {f} missing/null"
    assert pm["hlc_signature_eligible"] is True
    assert pm["time_context_id"] == CTX_ID
    assert pm["tai_iso"] == moment.tai_iso
    assert evt.event_time == moment.tai_iso
    assert evt.schema_version == "6.0"


def test_sequence_increments_per_stream() -> None:
    eng = _engine()
    moment = _moment()
    e1 = eng.emit(event_type="x", agent_id="a", stream_id="alpha", memory_id="m", payload={}, tai_moment=moment)
    e2 = eng.emit(event_type="x", agent_id="a", stream_id="alpha", memory_id="m", payload={}, tai_moment=moment)
    e3 = eng.emit(event_type="x", agent_id="a", stream_id="beta", memory_id="m", payload={}, tai_moment=moment)
    assert e1.physical_moment["sequence_in_stream"] == 1
    assert e2.physical_moment["sequence_in_stream"] == 2
    assert e3.physical_moment["sequence_in_stream"] == 1, "beta stream must start at 1"


def test_hlc_steps_per_stream() -> None:
    eng = _engine()
    moment = _moment()
    e1 = eng.emit(event_type="x", agent_id="a", stream_id="s", memory_id="m", payload={}, tai_moment=moment)
    e2 = eng.emit(event_type="x", agent_id="a", stream_id="s", memory_id="m", payload={}, tai_moment=moment)
    h1 = e1.physical_moment["hlc_timestamp"]
    h2 = e2.physical_moment["hlc_timestamp"]
    # Same TAI input: phys_ns equal, logical bumps by 1.
    p1, l1 = (int(x) for x in h1.split("."))
    p2, l2 = (int(x) for x in h2.split("."))
    assert p1 == p2, f"phys_ns should match: {h1}, {h2}"
    assert l2 == l1 + 1, f"logical should bump on collision: {h1}, {h2}"


def test_tier1b_machine_origin_reasons() -> None:
    eng = _engine()
    evt = eng.emit(
        event_type="x",
        agent_id="a",
        stream_id="s",
        memory_id="m",
        payload={},
        tai_moment=_moment(),
        tier1b_null_reasons={
            "local_civil_time_observed": "machine_origin",
            "tz_offset_seconds": "tz_undeclared",
            "ntp_state": "ntp_unavailable",
        },
    )
    pm = evt.physical_moment
    assert pm["local_civil_time_observed"] is None
    assert pm["tz_offset_seconds"] is None
    assert pm["ntp_state"] is None
    reasons = pm["tier1b_null_reasons"]
    assert reasons["local_civil_time_observed"] == "machine_origin"
    assert reasons["tz_offset_seconds"] == "tz_undeclared"
    assert reasons["ntp_state"] == "ntp_unavailable"


def test_tier1b_invalid_reason_rejected() -> None:
    eng = _engine()
    try:
        eng.emit(
            event_type="x",
            agent_id="a",
            stream_id="s",
            memory_id="m",
            payload={},
            tai_moment=_moment(),
            tier1b_null_reasons={"ntp_state": "freeform_excuse"},
        )
    except ValueError as exc:
        assert "Tier 1b" in str(exc)
        return
    raise AssertionError("Invalid Tier 1b reason was accepted")


def test_tier2_utc_is_default_computed() -> None:
    eng = _engine()
    evt = eng.emit(event_type="x", agent_id="a", stream_id="s", memory_id="m", payload={}, tai_moment=_moment())
    utc_iso = evt.physical_moment["utc_iso"]
    assert utc_iso is not None, "utc_iso should be computed by default"
    # 2026 has no leap second pending; UTC and TAI differ by ~37 seconds.
    assert utc_iso.startswith("2026-05-13T11:59")


def test_tier2_null_reasons_enforced() -> None:
    eng = _engine()
    evt = eng.emit(event_type="x", agent_id="a", stream_id="s", memory_id="m", payload={}, tai_moment=_moment())
    nulls = evt.physical_moment["tier2_null_reasons"]
    # gps_time, tt_iso, sidereal_time, lunar_age_days, day_of_year, iso_week_date, leap_second_pending all default to source_absent
    for name in ("gps_time", "tt_iso", "sidereal_time", "lunar_age_days", "day_of_year", "iso_week_date", "leap_second_pending"):
        assert nulls.get(name) == "source_absent", f"{name} expected null with source_absent reason"


def test_replay_determinism() -> None:
    a = _engine()
    b = _engine()
    moment = _moment()
    e_a = a.emit(event_type="x", agent_id="a", stream_id="s", memory_id="m", payload={"k": 1}, tai_moment=moment)
    e_b = b.emit(event_type="x", agent_id="a", stream_id="s", memory_id="m", payload={"k": 1}, tai_moment=moment)
    # Same engine state + same inputs -> identical physical_moment.
    assert e_a.physical_moment == e_b.physical_moment


def test_compute_chain_signals_requires_computed_at() -> None:
    """Soft-spot #2 from the 2026-05-13 rating: no wall-clock fallback."""

    class _Reader:
        def query_memory_events(self, **kw):
            return []

    try:
        compute_chain_signals(
            memory_id="m", stream_id="s", as_of_time="2026-05-13T12:00:00.000",
            lineage_reader=_Reader(),
            computed_at="",
        )
    except ValueError as exc:
        assert "computed_at" in str(exc)
        return
    raise AssertionError("compute_chain_signals accepted empty computed_at")


def test_inmemory_engine_emits_v6() -> None:
    events: list = []
    eng = InMemoryLineageEngine(events=events)
    eng.emit(event_type="probe", agent_id="a", stream_id="s", memory_id="m", payload={})
    assert events
    evt = events[0]
    assert evt["schema_version"] == "6.0"
    assert "physical_moment" in evt
    pm = evt["physical_moment"]
    for f in ("tai_iso", "solar_age_myr", "ecliptic_lon_deg", "sequence_in_stream", "hlc_timestamp", "time_context_id"):
        assert pm.get(f) is not None, f"InMemory: Tier 1a {f} missing"


def _check(name: str, fn: Callable[[], None]) -> tuple[str, bool, str]:
    try:
        fn()
        return name, True, ""
    except AssertionError as exc:
        return name, False, str(exc) or "assertion failed"
    except Exception as exc:
        return name, False, f"{type(exc).__name__}: {exc}"


CHECKS: list[tuple[str, Callable[[], None]]] = [
    ("schema_version_is_v6", test_schema_version_is_v6),
    ("new_event_requires_physical_moment_tai_iso", test_new_event_requires_physical_moment_tai_iso),
    ("engine_emit_tier1a_fields", test_engine_emit_tier1a_fields),
    ("sequence_increments_per_stream", test_sequence_increments_per_stream),
    ("hlc_steps_per_stream", test_hlc_steps_per_stream),
    ("tier1b_machine_origin_reasons", test_tier1b_machine_origin_reasons),
    ("tier1b_invalid_reason_rejected", test_tier1b_invalid_reason_rejected),
    ("tier2_utc_is_default_computed", test_tier2_utc_is_default_computed),
    ("tier2_null_reasons_enforced", test_tier2_null_reasons_enforced),
    ("replay_determinism", test_replay_determinism),
    ("compute_chain_signals_requires_computed_at", test_compute_chain_signals_requires_computed_at),
    ("inmemory_engine_emits_v6", test_inmemory_engine_emits_v6),
]


def main() -> int:
    results = [_check(name, fn) for name, fn in CHECKS]
    width = max(len(name) for name, _, _ in results)
    failures = 0
    for name, ok, reason in results:
        status = "PASS" if ok else "FAIL"
        line = f"{status:4}  {name:<{width}}"
        if not ok:
            line += f"  -- {reason}"
            failures += 1
        print(line)
    print()
    print(f"Phase 2 verify: {len(results) - failures}/{len(results)} passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
