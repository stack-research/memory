from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4


# v7 per EPISTEMIC_TRIANGLE spec §9. The legacy `event_time`
# envelope field is dropped; `physical_moment.tai_iso` is the
# canonical anchor.
EVENT_SCHEMA_VERSION = "7.0"


@dataclass(frozen=True)
class MemoryEvent:
    event_id: str
    event_type: str
    agent_id: str
    stream_id: str
    memory_id: str
    payload: dict[str, Any]
    actor_class: str
    source_class: str
    physical_moment: dict[str, Any]
    record_kind: str
    schema_version: str = EVENT_SCHEMA_VERSION
    parent_event_id: str | None = None
    assertion_kind: str | None = None
    subject_event_id: str | None = None
    subject_record_kind: str | None = None
    subject_assertion_kind: str | None = None

    @property
    def event_time(self) -> str:
        """Backward-compatibility shim for v6 readers.

        Returns physical_moment.tai_iso. v7 events do not carry the
        legacy `event_time` envelope field; spec §8 mandates removal
        repo-wide. Pre-v7 readers that still reference `event_time`
        get the same string they would have read in v6 (since v6
        already enforced `event_time == physical_moment.tai_iso`).

        New code should reference `physical_moment["tai_iso"]`
        directly.
        """
        return str(self.physical_moment.get("tai_iso", ""))


def new_event(
    *,
    event_type: str,
    agent_id: str,
    stream_id: str,
    memory_id: str,
    payload: dict[str, Any],
    actor_class: str,
    source_class: str,
    physical_moment: dict[str, Any],
    parent_event_id: str | None = None,
    record_kind: str | None = None,
    assertion_kind: str | None = None,
    subject_event_id: str | None = None,
    subject_record_kind: str | None = None,
    subject_assertion_kind: str | None = None,
) -> MemoryEvent:
    if "tai_iso" not in physical_moment or not physical_moment["tai_iso"]:
        raise ValueError("physical_moment.tai_iso is required (no wall-clock fallback)")
    if not record_kind:
        raise ValueError(
            "v7 events require record_kind in the envelope; "
            "see EPISTEMIC_TRIANGLE spec §3.1. LineageEngine.emit "
            "auto-derives this from the mapping table when caller does not provide it."
        )
    return MemoryEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload=payload,
        actor_class=actor_class,
        source_class=source_class,
        physical_moment=physical_moment,
        schema_version=EVENT_SCHEMA_VERSION,
        parent_event_id=parent_event_id,
        record_kind=record_kind,
        assertion_kind=assertion_kind,
        subject_event_id=subject_event_id,
        subject_record_kind=subject_record_kind,
        subject_assertion_kind=subject_assertion_kind,
    )
