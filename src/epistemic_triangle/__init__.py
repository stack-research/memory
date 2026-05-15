"""epistemic_triangle — v7 envelope primitives.

Spec: specs/EPISTEMIC_TRIANGLE.md (canonical, promoted 2026-05-14)

Phase 1 surface: enums, mapping table, closed quarantine reasons,
subject-classification dataclass, and a pure `validate_event_v7()`
function. Phase 1 is strictly additive — `MemoryEvent` gains optional
v7 fields, but storage/engine validation stays at v6 until Phase 3.

The five things this package holds apart at the schema edge:

  belief / claim / memory / evidence / reality_observation

`reality_observation` is the act of observing reality, never reality
itself. Reality remains unknowable; only observations enter lineage.
See notes/MEMORY_!=_REALITY.md.
"""

from __future__ import annotations

from .kinds import (
    ASSERTION_KIND_ENUM,
    RECORD_KIND_ENUM,
    AssertionKind,
    RecordKind,
)
from .links import (
    LINK_INVALID_REASONS,
    LINK_PENDING_REASONS,
    LINK_TYPE_ENUM,
    RESOLUTION_STATE_ENUM,
    EvidenceLinkPayload,
    LinkType,
    ResolutionState,
    compute_link_id,
    select_latest_link_states,
    validate_evidence_link_payload,
)
from .mapping import (
    EVENT_TYPE_MAPPING,
    MappingLookupResult,
    lookup_event_type,
)
from .quarantine import V7_QUARANTINE_REASONS
from .subject import SubjectClassification, memory_subject_placeholder
from .validate import V7_SCHEMA_VERSION, ValidationFailure, validate_event_v7

__all__ = [
    "ASSERTION_KIND_ENUM",
    "AssertionKind",
    "EVENT_TYPE_MAPPING",
    "EvidenceLinkPayload",
    "LINK_INVALID_REASONS",
    "LINK_PENDING_REASONS",
    "LINK_TYPE_ENUM",
    "LinkType",
    "MappingLookupResult",
    "RECORD_KIND_ENUM",
    "RESOLUTION_STATE_ENUM",
    "RecordKind",
    "ResolutionState",
    "SubjectClassification",
    "V7_QUARANTINE_REASONS",
    "V7_SCHEMA_VERSION",
    "ValidationFailure",
    "compute_link_id",
    "lookup_event_type",
    "memory_subject_placeholder",
    "select_latest_link_states",
    "validate_event_v7",
    "validate_evidence_link_payload",
]
