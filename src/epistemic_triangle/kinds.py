"""Closed enums for v7 envelope kinds.

Spec: specs/EPISTEMIC_TRIANGLE.md §3.1, §3.2

`record_kind` (required, non-nullable) — what the event *is* in
lineage terms.

`assertion_kind` (required when record_kind ∈ {memory_event,
observation_event}; nullable otherwise) — what epistemic kind the
payload asserts.

Reality remains unknowable; only observations enter lineage.
`reality_observation` is permitted only when record_kind ==
observation_event.
"""

from __future__ import annotations

from enum import Enum


class RecordKind(str, Enum):
    LINEAGE_META = "lineage_meta"
    MEMORY_EVENT = "memory_event"
    DECISION_EVENT = "decision_event"
    OBSERVATION_EVENT = "observation_event"
    POLICY_EVENT = "policy_event"


class AssertionKind(str, Enum):
    BELIEF = "belief"
    CLAIM = "claim"
    MEMORY = "memory"
    EVIDENCE = "evidence"
    REALITY_OBSERVATION = "reality_observation"


RECORD_KIND_ENUM: frozenset[str] = frozenset(rk.value for rk in RecordKind)
ASSERTION_KIND_ENUM: frozenset[str] = frozenset(ak.value for ak in AssertionKind)

# Record kinds that REQUIRE assertion_kind to be present and non-null
# per spec §3.2.
RECORD_KINDS_REQUIRING_ASSERTION_KIND: frozenset[str] = frozenset({
    RecordKind.MEMORY_EVENT.value,
    RecordKind.OBSERVATION_EVENT.value,
})

# Reality observation may appear only on observation events. Spec §3.2
# pins reality as unknowable; the observation enters lineage, reality
# itself does not.
ASSERTION_KIND_REALITY_OBSERVATION: str = AssertionKind.REALITY_OBSERVATION.value
RECORD_KIND_OBSERVATION_EVENT: str = RecordKind.OBSERVATION_EVENT.value
