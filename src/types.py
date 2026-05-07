from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


EVENT_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class MemoryEvent:
    event_id: str
    event_type: str
    agent_id: str
    stream_id: str
    memory_id: str
    event_time: str
    payload: dict[str, Any]
    schema_version: str = EVENT_SCHEMA_VERSION
    parent_event_id: str | None = None



def new_event(
    *,
    event_type: str,
    agent_id: str,
    stream_id: str,
    memory_id: str,
    payload: dict[str, Any],
    parent_event_id: str | None = None,
) -> MemoryEvent:
    return MemoryEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        event_time=datetime.now(timezone.utc).isoformat(),
        payload=payload,
        schema_version=EVENT_SCHEMA_VERSION,
        parent_event_id=parent_event_id,
    )
