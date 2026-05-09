from __future__ import annotations

from typing import Any, Protocol


class _LineageLike(Protocol):
    def emit(
        self,
        *,
        event_type: str,
        agent_id: str,
        stream_id: str,
        memory_id: str,
        payload: dict,
        actor_class: str = "implicit_memory_controller",
        source_class: str = "internal_engine",
        parent_event_id: str | None = None,
    ): ...


def emit_implicit_event(
    *,
    lineage: _LineageLike,
    event_type: str,
    agent_id: str,
    stream_id: str,
    memory_id: str,
    payload: dict[str, Any],
    parent_event_id: str | None = None,
) -> dict[str, Any]:
    event = lineage.emit(
        event_type=event_type,
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        actor_class="implicit_memory_controller",
        source_class="internal_engine",
        payload=payload,
        parent_event_id=parent_event_id,
    )
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "memory_id": event.memory_id,
    }
