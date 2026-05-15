"""Pure v7 envelope validation.

Spec: specs/EPISTEMIC_TRIANGLE.md §3.6, §12

`validate_event_v7(event_dict)` returns `None` on success or a
`ValidationFailure` describing the failure deterministically. The
function is pure: it operates on a dict view of an event and never
reads wall-clock or external state. Phase 3 will wire this into
`storage._validate_event` and Athena ingestion.

Phase 1 keeps this strictly additive: it does NOT replace the
existing v6 validators in `storage.py`. It is callable by tests and
by the Phase-1 verifier.

A v7-shaped event dict is expected to include:

  - all v6 fields (event_id, event_type, ..., physical_moment Tier 1a)
  - record_kind: str (closed enum)
  - assertion_kind: str | None (closed enum or None)
  - subject_event_id, subject_record_kind, subject_assertion_kind:
    optional; required when payload carries `uncertainty_triple` and
    record_kind == decision_event

`event_time` must be ABSENT in v7 events (legacy field dropped per
§8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .kinds import (
    ASSERTION_KIND_ENUM,
    ASSERTION_KIND_REALITY_OBSERVATION,
    RECORD_KIND_ENUM,
    RECORD_KIND_OBSERVATION_EVENT,
    RECORD_KINDS_REQUIRING_ASSERTION_KIND,
)
from .links import validate_evidence_link_payload
from .mapping import lookup_event_type
from .quarantine import V7_QUARANTINE_REASONS


V7_SCHEMA_VERSION: str = "7.0"


@dataclass(frozen=True)
class ValidationFailure:
    """A deterministic v7 validation failure.

    `reason` is a member of `V7_QUARANTINE_REASONS` for any v7-specific
    failure. Pre-v7 failures (missing required envelope, malformed
    physical_moment, etc.) reuse the existing storage validator's
    error messages — this validator focuses on v7 envelope rules.
    """

    reason: str
    detail: str

    def __post_init__(self) -> None:
        if self.reason not in V7_QUARANTINE_REASONS:
            raise AssertionError(
                f"ValidationFailure.reason '{self.reason}' is not in V7_QUARANTINE_REASONS; "
                "callers MUST use the closed enum"
            )


def validate_event_v7(event: Mapping[str, Any]) -> ValidationFailure | None:
    """Validate a v7-shaped event dict.

    Returns None on success, or a `ValidationFailure` with a closed
    `reason` and a free-form `detail` on failure. Failures stop at
    the first violation (deterministic ordering).

    Does NOT validate v6 envelope or physical_moment — those remain
    the responsibility of the v6 validator chain. This function
    layers v7-specific rules on top.
    """
    # 1. record_kind required and well-formed.
    if "record_kind" not in event:
        return ValidationFailure(
            reason="missing_record_kind",
            detail="v7 events must carry record_kind in the envelope",
        )
    record_kind = event["record_kind"]
    if not record_kind or not isinstance(record_kind, str):
        return ValidationFailure(
            reason="missing_record_kind",
            detail=f"record_kind must be a non-empty string; got {record_kind!r}",
        )
    if record_kind not in RECORD_KIND_ENUM:
        return ValidationFailure(
            reason="invalid_record_kind",
            detail=(
                f"record_kind '{record_kind}' not in closed enum "
                f"{sorted(RECORD_KIND_ENUM)}"
            ),
        )

    # 2. assertion_kind shape.
    assertion_kind = event.get("assertion_kind")
    if assertion_kind is not None:
        if not isinstance(assertion_kind, str) or assertion_kind not in ASSERTION_KIND_ENUM:
            return ValidationFailure(
                reason="invalid_assertion_kind",
                detail=(
                    f"assertion_kind '{assertion_kind}' not in closed enum "
                    f"{sorted(ASSERTION_KIND_ENUM)}"
                ),
            )
    if (
        record_kind in RECORD_KINDS_REQUIRING_ASSERTION_KIND
        and assertion_kind is None
    ):
        return ValidationFailure(
            reason="missing_assertion_kind_for_record_kind",
            detail=(
                f"record_kind='{record_kind}' requires non-null assertion_kind "
                f"per spec §3.2"
            ),
        )

    # 3. reality_observation only on observation_event.
    if (
        assertion_kind == ASSERTION_KIND_REALITY_OBSERVATION
        and record_kind != RECORD_KIND_OBSERVATION_EVENT
    ):
        return ValidationFailure(
            reason="reality_observation_outside_observation_event",
            detail=(
                f"assertion_kind='reality_observation' requires "
                f"record_kind='observation_event'; got '{record_kind}'"
            ),
        )

    # 4. event_type mapping (skip if event_type missing — v6 validator
    #    will catch that).
    event_type = event.get("event_type")
    if event_type:
        mapping = lookup_event_type(event_type)
        if mapping is None:
            return ValidationFailure(
                reason="unmapped_event_type",
                detail=(
                    f"event_type '{event_type}' not in static mapping table; "
                    "an event_type_declared lineage event must precede unmapped types"
                ),
            )
        # The mapping authoritative record_kind must agree with envelope.
        if mapping.record_kind.value != record_kind:
            return ValidationFailure(
                reason="invalid_record_kind",
                detail=(
                    f"envelope record_kind='{record_kind}' does not match mapping "
                    f"record_kind='{mapping.record_kind.value}' for event_type='{event_type}'"
                ),
            )
        # If the mapping pins assertion_kind (not per_payload, not
        # None), envelope must agree.
        if (
            mapping.assertion_kind is not None
            and not mapping.assertion_kind_per_payload
            and assertion_kind != mapping.assertion_kind.value
        ):
            return ValidationFailure(
                reason="invalid_assertion_kind",
                detail=(
                    f"envelope assertion_kind='{assertion_kind}' does not match mapping "
                    f"assertion_kind='{mapping.assertion_kind.value}' for "
                    f"event_type='{event_type}'"
                ),
            )

        # 5. Subject classification on DECISION events carrying
        #    uncertainty triples (spec §3.3). The trigger is the
        #    pair (record_kind == decision_event AND payload carries
        #    uncertainty_triple), OR the mapping table flag
        #    `requires_subject_assertion_kind` set on the
        #    event_type. Memory/observation events that happen to
        #    carry an uncertainty_triple in payload are NOT required
        #    to declare a subject — they are the subject (spec §3.3
        #    excludes them by limiting the requirement to decision
        #    events).
        payload = event.get("payload") or {}
        is_decision_event = record_kind == "decision_event"
        carries_triple = (
            isinstance(payload, Mapping) and "uncertainty_triple" in payload
        )
        if mapping.requires_subject_assertion_kind or (is_decision_event and carries_triple):
            subject_assertion_kind = event.get("subject_assertion_kind")
            if subject_assertion_kind is None:
                return ValidationFailure(
                    reason="missing_subject_assertion_kind",
                    detail=(
                        f"decision event '{event_type}' carries uncertainty_triple "
                        "and must include subject_assertion_kind per §3.3"
                    ),
                )
            if (
                not isinstance(subject_assertion_kind, str)
                or subject_assertion_kind not in ASSERTION_KIND_ENUM
            ):
                return ValidationFailure(
                    reason="subject_kind_mismatch",
                    detail=(
                        f"subject_assertion_kind '{subject_assertion_kind}' not in closed "
                        f"enum {sorted(ASSERTION_KIND_ENUM)}"
                    ),
                )

    # 6. Legacy event_time field must be absent in v7.
    if "event_time" in event and event.get("schema_version") == V7_SCHEMA_VERSION:
        return ValidationFailure(
            reason="legacy_event_time_present",
            detail=(
                "v7 events must not carry the legacy event_time field; "
                "use physical_moment.tai_iso instead"
            ),
        )

    # 7. evidence_link_declared payload validation chain.
    # Per spec §4.1 the payload itself must satisfy the closed-enum
    # state machine + link_id integrity. Without this, an event with
    # event_type="evidence_link_declared" could carry a payload that
    # the link walker would later reject; ingest-time enforcement
    # short-circuits that drift.
    if event_type == "evidence_link_declared":
        payload = event.get("payload") or {}
        link_reason = validate_evidence_link_payload(payload)
        if link_reason is not None:
            # validate_evidence_link_payload returns a v7 quarantine
            # reason string from the closed enum
            # ({invalid_link_id, evidence_link_*_mismatch, ...}).
            return ValidationFailure(
                reason=link_reason,
                detail=(
                    f"evidence_link_declared payload failed v7 link validation: {link_reason}"
                ),
            )

    return None
