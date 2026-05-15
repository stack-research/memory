"""Subject classification on decision events.

Spec: specs/EPISTEMIC_TRIANGLE.md §3.3

Decision events do not themselves carry `assertion_kind` (the
decision is not a claim). They decide ABOUT memory/claim/evidence
subjects. Subject classification makes
`axis_distribution_by_assertion_kind` audits queryable on the most
important axis-bearing decisions.

Required when a decision event carries an `uncertainty_triple` in
its payload. The decision event's own `assertion_kind` remains null;
subject classification is auditable separately.
"""

from __future__ import annotations

from dataclasses import dataclass

from .kinds import AssertionKind, RecordKind


@dataclass(frozen=True)
class SubjectClassification:
    subject_event_id: str | None
    subject_record_kind: RecordKind | None
    subject_assertion_kind: AssertionKind | None

    def is_empty(self) -> bool:
        return (
            self.subject_event_id is None
            and self.subject_record_kind is None
            and self.subject_assertion_kind is None
        )

    def to_envelope(self) -> dict[str, str | None]:
        """Serialize to envelope-shaped dict (string values for enums)."""
        return {
            "subject_event_id": self.subject_event_id,
            "subject_record_kind": (
                self.subject_record_kind.value if self.subject_record_kind else None
            ),
            "subject_assertion_kind": (
                self.subject_assertion_kind.value if self.subject_assertion_kind else None
            ),
        }


def memory_subject_placeholder(memory_id: str) -> dict[str, str]:
    """Deterministic placeholder pattern for decision events whose
    subject is a memory_id before any concrete `stored` event has
    been emitted. Per the v1.2 promotion-review caution #3.

    Returns envelope kwargs ready to pass to `lineage.emit(..., **placeholder)`:

        subject_event_id           = "memory_id_referenced:<memory_id>"
        subject_record_kind        = "memory_event"
        subject_assertion_kind     = "memory"

    The placeholder is replay-stable (same memory_id → same value)
    and identifiable in audits (`memory_id_referenced:` prefix).
    Callers should also set `subject_kind_source: "v1_default"` in
    the decision payload so audits distinguish defaulted from
    derived subject classification (no silent provider fill).
    """
    return {
        "subject_event_id": f"memory_id_referenced:{memory_id}",
        "subject_record_kind": RecordKind.MEMORY_EVENT.value,
        "subject_assertion_kind": AssertionKind.MEMORY.value,
    }
