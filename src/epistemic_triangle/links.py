"""evidence_link_declared event type — schema, identity, walker.

Spec: specs/EPISTEMIC_TRIANGLE.md §4

A claim/evidence link is a `lineage_meta` event connecting a claim
event to an evidence (or reality_observation) event. Links are
append-only state machines: an emitted `pending` may later be
followed by `resolved` or `invalid`; later emissions do not mutate
earlier ones. Walkers select the LATEST state per `link_id` at
`as_of_time`.

`link_id` is deterministic over `(claim_event_id, evidence_event_id,
link_type)` so the same logical link produces the same id across
processes and replays.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


class LinkType(str, Enum):
    SUPPORTS = "supports"
    REFUTES = "refutes"


class ResolutionState(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    INVALID = "invalid"


LINK_TYPE_ENUM: frozenset[str] = frozenset(lt.value for lt in LinkType)
RESOLUTION_STATE_ENUM: frozenset[str] = frozenset(rs.value for rs in ResolutionState)


# Closed enums for resolution_reason per state. Required when state
# is in {pending, invalid}; null when state is resolved.
LINK_PENDING_REASONS: frozenset[str] = frozenset({
    "claim_not_yet_emitted",
    "evidence_not_yet_emitted",
    "both_unresolved",
})

LINK_INVALID_REASONS: frozenset[str] = frozenset({
    "claim_assertion_kind_mismatch",
    "evidence_assertion_kind_mismatch",
    "dangling_after_grace_period",
})


def compute_link_id(
    *,
    claim_event_id: str,
    evidence_event_id: str,
    link_type: str,
) -> str:
    """Deterministic SHA-256 hex over canonical JSON of the link's content fields.

    Spec §4.2: same `(claim, evidence, link_type)` triple → same `link_id`
    across processes and replays. The hash preimage excludes
    `resolution_state` and `resolution_reason` (those are state, not
    identity).

    Validators reject events whose payload `link_id` does not match
    this recomputed hash (`invalid_link_id` quarantine).
    """
    if link_type not in LINK_TYPE_ENUM:
        raise ValueError(
            f"link_type '{link_type}' not in closed enum {sorted(LINK_TYPE_ENUM)}"
        )
    preimage = json.dumps(
        {
            "claim_event_id": claim_event_id,
            "evidence_event_id": evidence_event_id,
            "link_type": link_type,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(preimage).hexdigest()


@dataclass(frozen=True)
class EvidenceLinkPayload:
    """Canonical payload shape for `evidence_link_declared` events.

    The engine helper that emits these (Phase 3) constructs this and
    serializes via `to_dict`. Phase 2 keeps the type pure and
    test-fixturable.
    """

    claim_event_id: str
    evidence_event_id: str
    link_type: LinkType
    resolution_state: ResolutionState
    resolution_reason: str | None = None

    @property
    def link_id(self) -> str:
        return compute_link_id(
            claim_event_id=self.claim_event_id,
            evidence_event_id=self.evidence_event_id,
            link_type=self.link_type.value,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "link_type": self.link_type.value,
            "claim_event_id": self.claim_event_id,
            "evidence_event_id": self.evidence_event_id,
            "resolution_state": self.resolution_state.value,
            "resolution_reason": self.resolution_reason,
        }


def validate_evidence_link_payload(payload: Mapping[str, Any]) -> str | None:
    """Validate an `evidence_link_declared` payload dict.

    Returns None on success, or a closed-enum quarantine reason
    string. Reasons are members of:
      - "invalid_link_id"
      - "evidence_link_claim_kind_mismatch" (caller-detected; not from this fn)
      - "evidence_link_evidence_kind_mismatch" (caller-detected)
      - "evidence_link_dangling_after_grace_period" (caller-detected)
      - plus shape errors that surface as None-result + ValueError

    This function only verifies shape and closed-enum membership.
    Cross-event resolution (assertion_kind on referenced events) is
    a runtime resolver concern in Phase 3.
    """
    required_str_fields = ("link_id", "claim_event_id", "evidence_event_id")
    for field_name in required_str_fields:
        value = payload.get(field_name)
        if not isinstance(value, str) or not value:
            return "invalid_link_id"

    link_type = payload.get("link_type")
    if link_type not in LINK_TYPE_ENUM:
        return "invalid_link_id"

    state = payload.get("resolution_state")
    if state not in RESOLUTION_STATE_ENUM:
        return "invalid_link_id"

    reason = payload.get("resolution_reason")
    if state == ResolutionState.RESOLVED.value:
        if reason is not None:
            return "invalid_link_id"
    elif state == ResolutionState.PENDING.value:
        if reason not in LINK_PENDING_REASONS:
            return "invalid_link_id"
    elif state == ResolutionState.INVALID.value:
        if reason not in LINK_INVALID_REASONS:
            return "invalid_link_id"

    expected_link_id = compute_link_id(
        claim_event_id=payload["claim_event_id"],
        evidence_event_id=payload["evidence_event_id"],
        link_type=payload["link_type"],
    )
    if payload["link_id"] != expected_link_id:
        return "invalid_link_id"

    return None


def _link_event_canonical_order_key(event: Mapping[str, Any]) -> tuple:
    """Cross-stream ordering key per spec §8.2:
    (pm_tai_iso, stream_id, pm_sequence_in_stream, event_id).

    Link events may live on any stream (claims often live on a
    different stream than their evidence). Using single-stream
    §8.1 ordering here would conflate streams when the same TAI
    appears on more than one. The cross-stream tuple is the safe
    default — within a single stream it degenerates to §8.1 because
    stream_id is constant.
    """
    pm = event.get("physical_moment") or {}
    tai_iso = pm.get("tai_iso") or event.get("event_time") or ""
    stream_id = event.get("stream_id") or ""
    seq = pm.get("sequence_in_stream")
    if seq is None:
        seq = -1
    event_id = event.get("event_id") or ""
    return (tai_iso, stream_id, int(seq), event_id)


def select_latest_link_states(
    link_events: Iterable[Mapping[str, Any]],
    *,
    as_of_time: str | None = None,
) -> dict[str, Mapping[str, Any]]:
    """Group events by `link_id`, select the latest state at `as_of_time`,
    return ONLY links whose latest state is `resolved`.

    Spec §4.3:
      - Group events by link_id.
      - Select latest state by canonical ordering at as_of_time.
      - Consume only links whose latest state is `resolved`.
      - If latest is `invalid`, the link does not contribute even if
        a prior `resolved` state exists for the same link_id.
      - Pending links do not contribute.

    Returns a dict mapping `link_id` → the latest `resolved` event
    dict.
    """
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for event in link_events:
        if event.get("event_type") != "evidence_link_declared":
            continue
        payload = event.get("payload") or {}
        link_id = payload.get("link_id")
        if not isinstance(link_id, str) or not link_id:
            continue
        if as_of_time is not None:
            pm = event.get("physical_moment") or {}
            tai = pm.get("tai_iso") or event.get("event_time") or ""
            if tai > as_of_time:
                continue
        grouped.setdefault(link_id, []).append(event)

    latest: dict[str, Mapping[str, Any]] = {}
    for link_id, events in grouped.items():
        events_sorted = sorted(events, key=_link_event_canonical_order_key)
        most_recent = events_sorted[-1]
        state = (most_recent.get("payload") or {}).get("resolution_state")
        if state == ResolutionState.RESOLVED.value:
            latest[link_id] = most_recent
    return latest
