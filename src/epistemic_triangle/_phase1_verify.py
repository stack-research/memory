"""Phase 1 self-test for EPISTEMIC_TRIANGLE primitives.

Spec: specs/EPISTEMIC_TRIANGLE.md (canonical, promoted 2026-05-14)

Phase 1 covers strictly additive primitives:

  - RecordKind, AssertionKind enums (kinds.py)
  - Static event_type mapping table (mapping.py)
  - Closed v7 quarantine reasons (quarantine.py)
  - SubjectClassification dataclass (subject.py)
  - Pure validate_event_v7() (validate.py)
  - Optional v7 fields on MemoryEvent / new_event()

This verifier proves the primitives behave correctly without
touching the live storage validator (which stays at v6 until
Phase 3). Run via:

  PYTHONPATH=. uv run --project stacks python -m src.epistemic_triangle._phase1_verify
"""

from __future__ import annotations

import sys
from typing import Any, Mapping

from src.epistemic_triangle import (
    ASSERTION_KIND_ENUM,
    EVENT_TYPE_MAPPING,
    RECORD_KIND_ENUM,
    AssertionKind,
    RecordKind,
    SubjectClassification,
    V7_QUARANTINE_REASONS,
    V7_SCHEMA_VERSION,
    ValidationFailure,
    lookup_event_type,
    validate_event_v7,
)
from src.epistemic_triangle.kinds import (
    RECORD_KINDS_REQUIRING_ASSERTION_KIND,
)
from src.heliotime import now as heliotime_now
from src.types import MemoryEvent, new_event


def test_kind_enums_are_closed() -> None:
    """RecordKind and AssertionKind are closed enums; their string
    values populate the validator's accept-set."""
    assert {rk.value for rk in RecordKind} == RECORD_KIND_ENUM
    assert {ak.value for ak in AssertionKind} == ASSERTION_KIND_ENUM
    # The five-term taxonomy from MEMORY_!=_REALITY.md.
    assert ASSERTION_KIND_ENUM == frozenset(
        {"belief", "claim", "memory", "evidence", "reality_observation"}
    )
    # The five record kinds from spec §3.1.
    assert RECORD_KIND_ENUM == frozenset(
        {"lineage_meta", "memory_event", "decision_event", "observation_event", "policy_event"}
    )


def test_record_kinds_requiring_assertion_kind() -> None:
    """memory_event and observation_event require assertion_kind per
    §3.2; the other three permit null."""
    assert RECORD_KINDS_REQUIRING_ASSERTION_KIND == frozenset(
        {"memory_event", "observation_event"}
    )


def test_mapping_table_covers_v6_event_types() -> None:
    """Every event_type the v6 codebase emits has a v7 mapping row.
    The list below is the union of types referenced in src/ and
    src/experiments/. Missing rows would force `unmapped_event_type`
    quarantine on legitimate events."""
    expected_types = frozenset({
        # Lineage meta
        "canonical_table_genesis",
        "time_context_declared",
        "canonical_batch_committed",
        "provenance_signals_computed",
        "provenance_signals_written_to_vector",
        "snapshotted",
        "evidence_link_declared",
        "event_type_declared",
        "probe",
        # Memory
        "stored",
        "recalled",
        "mutated",
        "procedure_decayed",
        "procedure_reinforced",
        # Decision
        "implicit_admitted",
        "implicit_rejected",
        "implicit_no_op",
        "implicit_trigger_evaluated",
        "implicit_trigger_fired",
        "implicit_trigger_deferred",
        "reflex_action_executed",
        "reflex_mode_entered",
        "reflex_mode_exited",
        "contamination_suspected",
        "contradicted",
        "rejected",
        "quarantined",
        "promoted",
        # Observation
        "observed",
        # Policy
        "policy_threshold_updated",
        "policy_procedure_superseded",
    })
    missing = expected_types - frozenset(EVENT_TYPE_MAPPING.keys())
    assert not missing, f"Mapping table missing event_types: {sorted(missing)}"


def test_mapping_decision_subjects_flagged_correctly() -> None:
    """implicit_admitted and implicit_rejected carry uncertainty
    triples and must require subject_assertion_kind. Other decision
    events do not."""
    assert lookup_event_type("implicit_admitted").requires_subject_assertion_kind is True
    assert lookup_event_type("implicit_rejected").requires_subject_assertion_kind is True
    assert lookup_event_type("implicit_trigger_evaluated").requires_subject_assertion_kind is False
    assert lookup_event_type("reflex_action_executed").requires_subject_assertion_kind is False


def test_mapping_observed_pins_reality_observation() -> None:
    """`observed` events are observation_event + reality_observation
    per the taxonomy: observations enter lineage, reality does not."""
    result = lookup_event_type("observed")
    assert result is not None
    assert result.record_kind == RecordKind.OBSERVATION_EVENT
    assert result.assertion_kind == AssertionKind.REALITY_OBSERVATION
    assert result.assertion_kind_per_payload is False


def test_mapping_stored_is_per_payload() -> None:
    """`stored` carries assertion_kind from payload, not the static
    table — the only per-payload row in v1."""
    result = lookup_event_type("stored")
    assert result is not None
    assert result.assertion_kind is None
    assert result.assertion_kind_per_payload is True


def test_quarantine_enum_is_closed_and_complete() -> None:
    """All v7 validation failure reasons are members of the closed
    enum. ValidationFailure enforces this at construction."""
    for reason in (
        "missing_record_kind",
        "invalid_record_kind",
        "missing_assertion_kind_for_record_kind",
        "reality_observation_outside_observation_event",
        "invalid_assertion_kind",
        "unmapped_event_type",
        "missing_subject_assertion_kind",
        "subject_kind_mismatch",
        "legacy_event_time_present",
    ):
        assert reason in V7_QUARANTINE_REASONS

    # Constructing with an invalid reason must raise.
    raised = False
    try:
        ValidationFailure(reason="not_a_real_reason", detail="x")
    except AssertionError:
        raised = True
    assert raised, "ValidationFailure must reject reasons outside the closed enum"


def test_subject_classification_envelope_serialization() -> None:
    """SubjectClassification serializes enums to their string values."""
    sc = SubjectClassification(
        subject_event_id="evt-abc",
        subject_record_kind=RecordKind.MEMORY_EVENT,
        subject_assertion_kind=AssertionKind.CLAIM,
    )
    env = sc.to_envelope()
    assert env == {
        "subject_event_id": "evt-abc",
        "subject_record_kind": "memory_event",
        "subject_assertion_kind": "claim",
    }
    empty = SubjectClassification(None, None, None)
    assert empty.is_empty()
    assert empty.to_envelope() == {
        "subject_event_id": None,
        "subject_record_kind": None,
        "subject_assertion_kind": None,
    }


def _v7_event_dict(**overrides: Any) -> dict[str, Any]:
    """A minimal v7-shaped event dict used for validator tests."""
    base: dict[str, Any] = {
        "event_id": "evt-1",
        "event_type": "stored",
        "agent_id": "agent-a",
        "stream_id": "stream-a",
        "memory_id": "mem-1",
        "schema_version": V7_SCHEMA_VERSION,
        "actor_class": "system_worker",
        "source_class": "internal_engine",
        "payload": {},
        "physical_moment": {"tai_iso": "2026-05-14T20:50:41.227"},
        "record_kind": "memory_event",
        "assertion_kind": "memory",
    }
    base.update(overrides)
    return base


def test_validator_accepts_well_formed_event() -> None:
    assert validate_event_v7(_v7_event_dict()) is None


def test_validator_rejects_missing_record_kind() -> None:
    failure = validate_event_v7(_v7_event_dict(record_kind=None))
    assert failure is not None
    assert failure.reason == "missing_record_kind"


def test_validator_rejects_invalid_record_kind() -> None:
    failure = validate_event_v7(_v7_event_dict(record_kind="totally_made_up"))
    assert failure is not None
    assert failure.reason == "invalid_record_kind"


def test_validator_rejects_invalid_assertion_kind() -> None:
    failure = validate_event_v7(_v7_event_dict(assertion_kind="reality"))
    # Note: "reality" is NOT in the enum — only "reality_observation" is.
    assert failure is not None
    assert failure.reason == "invalid_assertion_kind"


def test_validator_requires_assertion_kind_for_memory_event() -> None:
    failure = validate_event_v7(
        _v7_event_dict(
            event_type="recalled",
            record_kind="memory_event",
            assertion_kind=None,
        )
    )
    assert failure is not None
    assert failure.reason == "missing_assertion_kind_for_record_kind"


def test_validator_rejects_reality_observation_outside_observation_event() -> None:
    failure = validate_event_v7(
        _v7_event_dict(
            event_type="stored",
            record_kind="memory_event",
            assertion_kind="reality_observation",
        )
    )
    assert failure is not None
    assert failure.reason == "reality_observation_outside_observation_event"


def test_validator_accepts_reality_observation_on_observation_event() -> None:
    failure = validate_event_v7(
        _v7_event_dict(
            event_type="observed",
            record_kind="observation_event",
            assertion_kind="reality_observation",
        )
    )
    assert failure is None


def test_validator_rejects_unmapped_event_type() -> None:
    failure = validate_event_v7(
        _v7_event_dict(
            event_type="something_new",
            record_kind="lineage_meta",
            assertion_kind=None,
        )
    )
    assert failure is not None
    assert failure.reason == "unmapped_event_type"


def test_validator_rejects_record_kind_envelope_mapping_disagreement() -> None:
    """`recalled` is mapped to memory_event; calling it lineage_meta
    in the envelope is a disagreement."""
    failure = validate_event_v7(
        _v7_event_dict(
            event_type="recalled",
            record_kind="lineage_meta",
            assertion_kind=None,
        )
    )
    assert failure is not None
    assert failure.reason == "invalid_record_kind"


def test_validator_rejects_decision_event_missing_subject_assertion_kind() -> None:
    failure = validate_event_v7(
        _v7_event_dict(
            event_type="implicit_admitted",
            record_kind="decision_event",
            assertion_kind=None,
            payload={"uncertainty_triple": [0.5, 0.5, 0.5]},
            subject_event_id=None,
            subject_assertion_kind=None,
        )
    )
    assert failure is not None
    assert failure.reason == "missing_subject_assertion_kind"


def test_validator_accepts_decision_event_with_subject_classification() -> None:
    failure = validate_event_v7(
        _v7_event_dict(
            event_type="implicit_admitted",
            record_kind="decision_event",
            assertion_kind=None,
            payload={"uncertainty_triple": [0.5, 0.5, 0.5]},
            subject_event_id="evt-claim-7",
            subject_record_kind="memory_event",
            subject_assertion_kind="claim",
        )
    )
    assert failure is None


def test_validator_rejects_legacy_event_time_in_v7_event() -> None:
    failure = validate_event_v7(
        _v7_event_dict(event_time="2026-05-14T20:50:41.227")
    )
    assert failure is not None
    assert failure.reason == "legacy_event_time_present"


def test_memory_event_carries_v7_envelope_fields() -> None:
    """v7 (Phase 3) requires record_kind on every event. new_event
    accepts the full v7 envelope; verify the fields are carried
    through and that omission of record_kind raises."""
    pm = heliotime_now()
    physical_moment = {
        "tai_iso": pm.tai_iso,
        "solar_age_myr": pm.solar_age_myr,
        "ecliptic_lon_deg": pm.ecliptic_lon_deg,
    }
    enriched = new_event(
        event_type="stored",
        agent_id="agent-a",
        stream_id="stream-a",
        memory_id="mem-1",
        payload={},
        actor_class="system_worker",
        source_class="internal_engine",
        physical_moment=physical_moment,
        record_kind="memory_event",
        assertion_kind="claim",
    )
    assert enriched.record_kind == "memory_event"
    assert enriched.assertion_kind == "claim"
    assert enriched.schema_version == "7.0"

    # Phase 3: omitting record_kind must raise.
    raised = False
    try:
        new_event(
            event_type="stored",
            agent_id="agent-a",
            stream_id="stream-a",
            memory_id="mem-1",
            payload={},
            actor_class="system_worker",
            source_class="internal_engine",
            physical_moment=physical_moment,
        )
    except ValueError:
        raised = True
    assert raised, "v7 requires record_kind in the envelope"


def test_validator_is_pure_no_wall_clock() -> None:
    """validate_event_v7 must not call the wall-clock. Two
    invocations on the same dict produce the same result regardless
    of timing."""
    ev = _v7_event_dict()
    a = validate_event_v7(ev)
    b = validate_event_v7(ev)
    assert a == b


TESTS = [
    ("kind_enums_are_closed", test_kind_enums_are_closed),
    ("record_kinds_requiring_assertion_kind", test_record_kinds_requiring_assertion_kind),
    ("mapping_table_covers_v6_event_types", test_mapping_table_covers_v6_event_types),
    ("mapping_decision_subjects_flagged_correctly", test_mapping_decision_subjects_flagged_correctly),
    ("mapping_observed_pins_reality_observation", test_mapping_observed_pins_reality_observation),
    ("mapping_stored_is_per_payload", test_mapping_stored_is_per_payload),
    ("quarantine_enum_is_closed_and_complete", test_quarantine_enum_is_closed_and_complete),
    ("subject_classification_envelope_serialization", test_subject_classification_envelope_serialization),
    ("validator_accepts_well_formed_event", test_validator_accepts_well_formed_event),
    ("validator_rejects_missing_record_kind", test_validator_rejects_missing_record_kind),
    ("validator_rejects_invalid_record_kind", test_validator_rejects_invalid_record_kind),
    ("validator_rejects_invalid_assertion_kind", test_validator_rejects_invalid_assertion_kind),
    ("validator_requires_assertion_kind_for_memory_event", test_validator_requires_assertion_kind_for_memory_event),
    ("validator_rejects_reality_observation_outside_observation_event", test_validator_rejects_reality_observation_outside_observation_event),
    ("validator_accepts_reality_observation_on_observation_event", test_validator_accepts_reality_observation_on_observation_event),
    ("validator_rejects_unmapped_event_type", test_validator_rejects_unmapped_event_type),
    ("validator_rejects_record_kind_envelope_mapping_disagreement", test_validator_rejects_record_kind_envelope_mapping_disagreement),
    ("validator_rejects_decision_event_missing_subject_assertion_kind", test_validator_rejects_decision_event_missing_subject_assertion_kind),
    ("validator_accepts_decision_event_with_subject_classification", test_validator_accepts_decision_event_with_subject_classification),
    ("validator_rejects_legacy_event_time_in_v7_event", test_validator_rejects_legacy_event_time_in_v7_event),
    ("memory_event_carries_v7_envelope_fields", test_memory_event_carries_v7_envelope_fields),
    ("validator_is_pure_no_wall_clock", test_validator_is_pure_no_wall_clock),
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
        print(f"Phase 1 verifier: FAILED {len(failures)}/{len(TESTS)}")
        return 1
    print(f"Phase 1 verifier: PASSED {len(TESTS)}/{len(TESTS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
