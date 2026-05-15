"""Static mapping table from event_type to (record_kind, assertion_kind).

Spec: specs/EPISTEMIC_TRIANGLE.md §3.4, §3.5

The closed table here is the v1 mapping. New event types enter
through both:

  1. Spec amendment adding a row to §3.4
  2. Runtime `event_type_declared` lineage event with a matching
     payload

`lookup_event_type` returns the static mapping result. At runtime,
audit walkers also consult any later `event_type_declared` events for
types not in this table; that resolution lives in Phase 2/3.

Per spec §3.4, `stored` events carry assertion_kind from payload —
the static row records `None` for that case to mean "per payload."
The mapping result includes a flag so callers can distinguish "not
applicable" (lineage_meta, decision_event) from "per payload"
(stored).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .kinds import AssertionKind, RecordKind


@dataclass(frozen=True)
class MappingLookupResult:
    record_kind: RecordKind
    # When `assertion_kind_per_payload` is True, the assertion_kind for
    # this event_type is determined by the payload at emit time, not
    # by the static table. Only used for `stored` today.
    assertion_kind: AssertionKind | None
    assertion_kind_per_payload: bool
    # When True, decision events of this type carry uncertainty triples
    # in their payload and MUST include subject_assertion_kind in the
    # envelope per spec §3.3.
    requires_subject_assertion_kind: bool


# Internal raw table. Tuple form: (record_kind, assertion_kind,
# assertion_kind_per_payload, requires_subject_assertion_kind).
_RAW: Mapping[str, tuple[RecordKind, AssertionKind | None, bool, bool]] = {
    # Lineage meta — system records about lineage itself.
    "canonical_table_genesis": (RecordKind.LINEAGE_META, None, False, False),
    "time_context_declared": (RecordKind.LINEAGE_META, None, False, False),
    "canonical_batch_committed": (RecordKind.LINEAGE_META, None, False, False),
    "provenance_signals_computed": (RecordKind.LINEAGE_META, None, False, False),
    "provenance_signals_written_to_vector": (RecordKind.LINEAGE_META, None, False, False),
    "snapshotted": (RecordKind.LINEAGE_META, None, False, False),
    "evidence_link_declared": (RecordKind.LINEAGE_META, None, False, False),
    "event_type_declared": (RecordKind.LINEAGE_META, None, False, False),
    # Memory events — store/retrieve/modify a memory trace.
    "stored": (RecordKind.MEMORY_EVENT, None, True, False),
    "recalled": (RecordKind.MEMORY_EVENT, AssertionKind.MEMORY, False, False),
    # `mutated` is uniformly a memory revision in active code; v1
    # auto-derives assertion_kind=memory. If a future caller wants
    # to mutate a claim/belief specifically, they can pass
    # assertion_kind explicitly to override.
    "mutated": (RecordKind.MEMORY_EVENT, AssertionKind.MEMORY, False, False),
    "procedure_decayed": (RecordKind.MEMORY_EVENT, AssertionKind.MEMORY, False, False),
    "procedure_reinforced": (RecordKind.MEMORY_EVENT, AssertionKind.MEMORY, False, False),
    # Decision events. Those carrying uncertainty triples (admitted,
    # rejected) require subject_assertion_kind per §3.3.
    "implicit_admitted": (RecordKind.DECISION_EVENT, None, False, True),
    "implicit_rejected": (RecordKind.DECISION_EVENT, None, False, True),
    "implicit_no_op": (RecordKind.DECISION_EVENT, None, False, False),
    "implicit_trigger_evaluated": (RecordKind.DECISION_EVENT, None, False, False),
    "implicit_trigger_fired": (RecordKind.DECISION_EVENT, None, False, False),
    "implicit_trigger_deferred": (RecordKind.DECISION_EVENT, None, False, False),
    "reflex_action_executed": (RecordKind.DECISION_EVENT, None, False, False),
    "reflex_mode_entered": (RecordKind.DECISION_EVENT, None, False, False),
    "reflex_mode_exited": (RecordKind.DECISION_EVENT, None, False, False),
    "contamination_suspected": (RecordKind.DECISION_EVENT, None, False, False),
    "contradicted": (RecordKind.DECISION_EVENT, None, False, False),
    "rejected": (RecordKind.DECISION_EVENT, None, False, True),
    "quarantined": (RecordKind.DECISION_EVENT, None, False, False),
    "promoted": (RecordKind.DECISION_EVENT, None, False, False),
    # Observation events — observer reads of external state.
    "observed": (RecordKind.OBSERVATION_EVENT, AssertionKind.REALITY_OBSERVATION, False, False),
    # Policy events.
    "policy_threshold_updated": (RecordKind.POLICY_EVENT, None, False, False),
    "policy_procedure_superseded": (RecordKind.POLICY_EVENT, None, False, False),
    # Test-only probes used by im_t falsification suite. Marked
    # lineage_meta so they don't pollute the epistemic axes.
    "probe": (RecordKind.LINEAGE_META, None, False, False),
}


EVENT_TYPE_MAPPING: Mapping[str, MappingLookupResult] = {
    event_type: MappingLookupResult(
        record_kind=record_kind,
        assertion_kind=assertion_kind,
        assertion_kind_per_payload=per_payload,
        requires_subject_assertion_kind=requires_subject,
    )
    for event_type, (record_kind, assertion_kind, per_payload, requires_subject) in _RAW.items()
}


def lookup_event_type(event_type: str) -> MappingLookupResult | None:
    """Return the static mapping for an event_type, or None if unknown.

    Unknown event types should be quarantined as `unmapped_event_type`
    at ingestion time unless an `event_type_declared` lineage event
    has previously declared the type (Phase 2/3 resolver).
    """
    return EVENT_TYPE_MAPPING.get(event_type)
