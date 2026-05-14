from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


EVENT_SCHEMA_VERSION = "6.0"


@dataclass(frozen=True)
class MemoryEvent:
    event_id: str
    event_type: str
    agent_id: str
    stream_id: str
    memory_id: str
    event_time: str
    payload: dict[str, Any]
    actor_class: str
    source_class: str
    physical_moment: dict[str, Any]
    schema_version: str = EVENT_SCHEMA_VERSION
    parent_event_id: str | None = None


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
) -> MemoryEvent:
    if "tai_iso" not in physical_moment or not physical_moment["tai_iso"]:
        raise ValueError("physical_moment.tai_iso is required (no wall-clock fallback)")
    return MemoryEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        event_time=physical_moment["tai_iso"],
        payload=payload,
        actor_class=actor_class,
        source_class=source_class,
        physical_moment=physical_moment,
        schema_version=EVENT_SCHEMA_VERSION,
        parent_event_id=parent_event_id,
    )
