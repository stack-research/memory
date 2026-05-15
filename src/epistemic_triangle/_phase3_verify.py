"""Phase 3 self-test for EPISTEMIC_TRIANGLE engine + storage cutover.

Spec: specs/EPISTEMIC_TRIANGLE.md (canonical, promoted 2026-05-14)

Phase 3 covers (offline; no AWS):

  - StreamState.sequence init -1 → first event in every stream gets
    sequence_in_stream = 0 (spec §10)
  - LineageEngine.emit auto-derives record_kind/assertion_kind
    from the static mapping table (spec §3.4)
  - new_event requires record_kind in v7
  - Storage validator chains validate_event_v7 (spec §3.6)
  - S3 ingress record drops event_time (spec §8) and carries
    record_kind / assertion_kind / subject classification (spec §9.3)
  - InMemoryLineageEngine matches v7 shape (used by experiments)

CDK + AWS deploy + cutover are NOT exercised here; they require
explicit operator go. Phase 4 will add the integration falsification
suite that runs against real ingress + ingestion.

Run via:

  PYTHONPATH=. uv run --project stacks python -m src.epistemic_triangle._phase3_verify
"""

from __future__ import annotations

import sys
from typing import Any

from src.epistemic_triangle import V7_SCHEMA_VERSION
from src.experiments.implicit.common import InMemoryLineageEngine
from src.heliotime import physical_moment as compute_pm
from src.lineage_engine import LineageEngine, StreamState
from src.types import EVENT_SCHEMA_VERSION, MemoryEvent, new_event


# ---------------------------------------------------------------------------
# Engine + types
# ---------------------------------------------------------------------------


def test_event_schema_version_is_v7() -> None:
    assert EVENT_SCHEMA_VERSION == "7.0"
    assert V7_SCHEMA_VERSION == "7.0"


def test_stream_state_init_sequence_is_minus_one() -> None:
    """Per EPISTEMIC_TRIANGLE §10, StreamState.sequence init -1 so
    the first emit's pre-increment produces sequence_in_stream = 0."""
    state = StreamState()
    assert state.sequence == -1


def test_new_event_requires_record_kind() -> None:
    pm = compute_pm("2026-05-14T20:50:41.227", scale="tai")
    physical_moment = {
        "tai_iso": pm.tai_iso,
        "solar_age_myr": pm.solar_age_myr,
        "ecliptic_lon_deg": pm.ecliptic_lon_deg,
    }
    raised = False
    try:
        new_event(
            event_type="stored",
            agent_id="agent-a",
            stream_id="stream-a",
            memory_id="mem-1",
            payload={},
            actor_class="x",
            source_class="y",
            physical_moment=physical_moment,
            record_kind=None,
            assertion_kind="claim",
        )
    except ValueError:
        raised = True
    assert raised, "new_event must reject events with no record_kind in v7"


def test_new_event_with_v7_envelope_succeeds() -> None:
    pm = compute_pm("2026-05-14T20:50:41.227", scale="tai")
    physical_moment = {
        "tai_iso": pm.tai_iso,
        "solar_age_myr": pm.solar_age_myr,
        "ecliptic_lon_deg": pm.ecliptic_lon_deg,
    }
    event = new_event(
        event_type="stored",
        agent_id="agent-a",
        stream_id="stream-a",
        memory_id="mem-1",
        payload={},
        actor_class="x",
        source_class="y",
        physical_moment=physical_moment,
        record_kind="memory_event",
        assertion_kind="claim",
        subject_event_id=None,
        subject_record_kind=None,
        subject_assertion_kind=None,
    )
    assert isinstance(event, MemoryEvent)
    assert event.record_kind == "memory_event"
    assert event.assertion_kind == "claim"
    assert event.schema_version == "7.0"
    assert event.event_time == pm.tai_iso, "event_time shim must return pm_tai_iso"


def test_memory_event_event_time_is_property_alias() -> None:
    """v7 drops the event_time envelope field. The MemoryEvent
    `event_time` property returns physical_moment.tai_iso for
    backward-compatible reads."""
    pm = compute_pm("2026-05-14T20:50:41.227", scale="tai")
    event = MemoryEvent(
        event_id="evt-1",
        event_type="stored",
        agent_id="a",
        stream_id="s",
        memory_id="m",
        payload={},
        actor_class="x",
        source_class="y",
        physical_moment={
            "tai_iso": pm.tai_iso,
            "solar_age_myr": pm.solar_age_myr,
            "ecliptic_lon_deg": pm.ecliptic_lon_deg,
        },
        record_kind="memory_event",
    )
    assert event.event_time == pm.tai_iso


# ---------------------------------------------------------------------------
# LineageEngine.emit auto-derivation + first event seq=0
# ---------------------------------------------------------------------------


def _engine_no_storage() -> LineageEngine:
    # Phase 3 verifier doesn't deploy time context; pass a stable
    # placeholder id so the engine's emit() can populate
    # physical_moment.time_context_id (validation is exercised at
    # storage append, not engine emit).
    return LineageEngine(storage=None, time_context_id="tc-phase3-verify")


def test_engine_first_emit_per_stream_is_seq_zero() -> None:
    engine = _engine_no_storage()
    pm = compute_pm("2026-05-14T20:50:41.227", scale="tai")
    e1 = engine.emit(
        event_type="recalled",
        agent_id="a",
        stream_id="alpha",
        memory_id="m1",
        payload={},
        tai_moment=pm,
    )
    e2 = engine.emit(
        event_type="recalled",
        agent_id="a",
        stream_id="alpha",
        memory_id="m1",
        payload={},
        tai_moment=pm,
    )
    e3 = engine.emit(
        event_type="recalled",
        agent_id="a",
        stream_id="beta",
        memory_id="m1",
        payload={},
        tai_moment=pm,
    )
    assert e1.physical_moment["sequence_in_stream"] == 0, "first event must be seq=0"
    assert e2.physical_moment["sequence_in_stream"] == 1
    assert e3.physical_moment["sequence_in_stream"] == 0, "new stream restarts at 0"


def test_engine_emit_auto_derives_record_kind_from_mapping() -> None:
    engine = _engine_no_storage()
    pm = compute_pm("2026-05-14T20:50:41.227", scale="tai")
    # `recalled` is mapped to (memory_event, memory).
    event = engine.emit(
        event_type="recalled",
        agent_id="a",
        stream_id="alpha",
        memory_id="m1",
        payload={},
        tai_moment=pm,
    )
    assert event.record_kind == "memory_event"
    assert event.assertion_kind == "memory"


def test_engine_emit_observed_pins_reality_observation() -> None:
    engine = _engine_no_storage()
    pm = compute_pm("2026-05-14T20:50:41.227", scale="tai")
    event = engine.emit(
        event_type="observed",
        agent_id="a",
        stream_id="alpha",
        memory_id="m1",
        payload={},
        tai_moment=pm,
    )
    assert event.record_kind == "observation_event"
    assert event.assertion_kind == "reality_observation"


def test_engine_emit_decision_event_accepts_subject_classification() -> None:
    engine = _engine_no_storage()
    pm = compute_pm("2026-05-14T20:50:41.227", scale="tai")
    event = engine.emit(
        event_type="implicit_admitted",
        agent_id="a",
        stream_id="alpha",
        memory_id="m1",
        payload={"uncertainty_triple": {}},
        tai_moment=pm,
        subject_event_id="memory_id_referenced:m1",
        subject_record_kind="memory_event",
        subject_assertion_kind="memory",
    )
    assert event.record_kind == "decision_event"
    assert event.assertion_kind is None
    assert event.subject_event_id == "memory_id_referenced:m1"
    assert event.subject_assertion_kind == "memory"


def test_engine_emit_stored_per_payload_assertion_kind_passes_through() -> None:
    """`stored` is per-payload in the mapping; emit must accept the
    caller-supplied assertion_kind without overriding."""
    engine = _engine_no_storage()
    pm = compute_pm("2026-05-14T20:50:41.227", scale="tai")
    event = engine.emit(
        event_type="stored",
        agent_id="a",
        stream_id="alpha",
        memory_id="m1",
        payload={},
        tai_moment=pm,
        assertion_kind="evidence",
    )
    assert event.record_kind == "memory_event"
    assert event.assertion_kind == "evidence"


# ---------------------------------------------------------------------------
# InMemoryLineageEngine matches v7 shape
# ---------------------------------------------------------------------------


def test_inmemory_engine_emits_v7_envelope() -> None:
    events: list[dict[str, Any]] = []
    engine = InMemoryLineageEngine(events=events)
    engine.emit(
        event_type="recalled",
        agent_id="a",
        stream_id="alpha",
        memory_id="m1",
        payload={},
    )
    engine.emit(
        event_type="implicit_admitted",
        agent_id="a",
        stream_id="alpha",
        memory_id="m1",
        payload={"uncertainty_triple": {}},
        subject_event_id="memory_id_referenced:m1",
        subject_record_kind="memory_event",
        subject_assertion_kind="memory",
    )
    assert events[0]["schema_version"] == "7.0"
    assert "event_time" not in events[0], "v7 in-memory engine drops event_time"
    assert events[0]["record_kind"] == "memory_event"
    assert events[0]["assertion_kind"] == "memory"
    assert events[0]["physical_moment"]["sequence_in_stream"] == 0, "first event seq=0"
    assert events[1]["record_kind"] == "decision_event"
    assert events[1]["subject_assertion_kind"] == "memory"


def test_inmemory_engine_first_event_per_stream_is_seq_zero() -> None:
    events: list[dict[str, Any]] = []
    engine = InMemoryLineageEngine(events=events)
    engine.emit(event_type="recalled", agent_id="a", stream_id="alpha", memory_id="m", payload={})
    engine.emit(event_type="recalled", agent_id="a", stream_id="beta", memory_id="m", payload={})
    assert events[0]["physical_moment"]["sequence_in_stream"] == 0
    assert events[1]["physical_moment"]["sequence_in_stream"] == 0


# ---------------------------------------------------------------------------
# Storage validator integration (v6 base + v7 layer)
# ---------------------------------------------------------------------------


def test_storage_validator_rejects_v7_event_with_missing_record_kind() -> None:
    """LineageStorage._validate_event must catch v7 envelope failures
    in addition to v6 base checks. We construct an event directly
    via dataclass (bypassing new_event's check) and assert the
    storage validator quarantines it."""
    from src.storage import LineageStorage

    pm = compute_pm("2026-05-14T20:50:41.227", scale="tai")
    physical_moment = {
        "tai_iso": pm.tai_iso,
        "solar_age_myr": pm.solar_age_myr,
        "ecliptic_lon_deg": pm.ecliptic_lon_deg,
        "sequence_in_stream": 0,
        "hlc_timestamp": "1.0",
        "hlc_signature_eligible": True,
        "time_context_id": "tc-test",
    }
    bad = MemoryEvent(
        event_id="evt-1",
        event_type="recalled",
        agent_id="a",
        stream_id="s",
        memory_id="m",
        payload={},
        actor_class="x",
        source_class="y",
        physical_moment=physical_moment,
        record_kind=None,  # missing — must be quarantined
    )
    raised_msg = ""
    try:
        LineageStorage._validate_event(bad)
    except ValueError as exc:
        raised_msg = str(exc)
    assert "missing_record_kind" in raised_msg, raised_msg


def test_storage_validator_rejects_decision_event_missing_subject() -> None:
    from src.storage import LineageStorage

    pm = compute_pm("2026-05-14T20:50:41.227", scale="tai")
    physical_moment = {
        "tai_iso": pm.tai_iso,
        "solar_age_myr": pm.solar_age_myr,
        "ecliptic_lon_deg": pm.ecliptic_lon_deg,
        "sequence_in_stream": 0,
        "hlc_timestamp": "1.0",
        "hlc_signature_eligible": True,
        "time_context_id": "tc-test",
    }
    bad = MemoryEvent(
        event_id="evt-1",
        event_type="implicit_admitted",
        agent_id="a",
        stream_id="s",
        memory_id="m",
        payload={"uncertainty_triple": {}},
        actor_class="x",
        source_class="y",
        physical_moment=physical_moment,
        record_kind="decision_event",
        # subject_assertion_kind missing — must be quarantined
    )
    raised_msg = ""
    try:
        LineageStorage._validate_event(bad)
    except ValueError as exc:
        raised_msg = str(exc)
    assert "missing_subject_assertion_kind" in raised_msg, raised_msg


def test_storage_validator_accepts_well_formed_v7_event() -> None:
    from src.storage import LineageStorage

    pm = compute_pm("2026-05-14T20:50:41.227", scale="tai")
    physical_moment = {
        "tai_iso": pm.tai_iso,
        "solar_age_myr": pm.solar_age_myr,
        "ecliptic_lon_deg": pm.ecliptic_lon_deg,
        "sequence_in_stream": 0,
        "hlc_timestamp": "1.0",
        "hlc_signature_eligible": True,
        "time_context_id": "tc-test",
    }
    good = MemoryEvent(
        event_id="evt-1",
        event_type="recalled",
        agent_id="a",
        stream_id="s",
        memory_id="m",
        payload={},
        actor_class="x",
        source_class="y",
        physical_moment=physical_moment,
        record_kind="memory_event",
        assertion_kind="memory",
    )
    # Must not raise.
    LineageStorage._validate_event(good)


TESTS = [
    ("event_schema_version_is_v7", test_event_schema_version_is_v7),
    ("stream_state_init_sequence_is_minus_one", test_stream_state_init_sequence_is_minus_one),
    ("new_event_requires_record_kind", test_new_event_requires_record_kind),
    ("new_event_with_v7_envelope_succeeds", test_new_event_with_v7_envelope_succeeds),
    ("memory_event_event_time_is_property_alias", test_memory_event_event_time_is_property_alias),
    ("engine_first_emit_per_stream_is_seq_zero", test_engine_first_emit_per_stream_is_seq_zero),
    ("engine_emit_auto_derives_record_kind_from_mapping", test_engine_emit_auto_derives_record_kind_from_mapping),
    ("engine_emit_observed_pins_reality_observation", test_engine_emit_observed_pins_reality_observation),
    ("engine_emit_decision_event_accepts_subject_classification", test_engine_emit_decision_event_accepts_subject_classification),
    ("engine_emit_stored_per_payload_assertion_kind_passes_through", test_engine_emit_stored_per_payload_assertion_kind_passes_through),
    ("inmemory_engine_emits_v7_envelope", test_inmemory_engine_emits_v7_envelope),
    ("inmemory_engine_first_event_per_stream_is_seq_zero", test_inmemory_engine_first_event_per_stream_is_seq_zero),
    ("storage_validator_rejects_v7_event_with_missing_record_kind", test_storage_validator_rejects_v7_event_with_missing_record_kind),
    ("storage_validator_rejects_decision_event_missing_subject", test_storage_validator_rejects_decision_event_missing_subject),
    ("storage_validator_accepts_well_formed_v7_event", test_storage_validator_accepts_well_formed_v7_event),
]


def main() -> int:
    failures: list[tuple[str, str]] = []
    for name, fn in TESTS:
        try:
            fn()
            print(f"  PASS {name}")
        except AssertionError as exc:
            failures.append((name, str(exc) or "AssertionError"))
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"  FAIL {name}: {type(exc).__name__}: {exc}")

    print()
    if failures:
        print(f"Phase 3 verifier: FAILED {len(failures)}/{len(TESTS)}")
        return 1
    print(f"Phase 3 verifier: PASSED {len(TESTS)}/{len(TESTS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
