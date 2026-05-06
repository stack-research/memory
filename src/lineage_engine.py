from __future__ import annotations

from .storage import LineageStorage
from .types import MemoryEvent, new_event


class LineageEngine:
    def __init__(self, storage: LineageStorage) -> None:
        self.storage = storage

    def emit(
        self,
        *,
        event_type: str,
        agent_id: str,
        stream_id: str,
        memory_id: str,
        payload: dict,
        parent_event_id: str | None = None,
    ) -> MemoryEvent:
        event = new_event(
            event_type=event_type,
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            payload=payload,
            parent_event_id=parent_event_id,
        )
        self.storage.append_event(event)
        return event
