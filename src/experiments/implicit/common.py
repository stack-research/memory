from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.implicit_memory.lineage_events import emit_implicit_event
from src.implicit_memory.replay import rebuild_from_lineage


@dataclass
class InMemoryLineageEngine:
    events: list[dict[str, Any]]

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
    ):
        event_id = f"evt-{len(self.events)+1:06d}"
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "agent_id": agent_id,
            "stream_id": stream_id,
            "memory_id": memory_id,
            "event_time": datetime.now(timezone.utc).isoformat(),
            "schema_version": "1.0",
            "payload": payload,
            "actor_class": actor_class,
            "source_class": source_class,
            "parent_event_id": parent_event_id,
        }
        self.events.append(event)

        class E:
            pass

        out = E()
        out.event_id = event_id
        out.event_type = event_type
        out.memory_id = memory_id
        return out


def emit(lineage: InMemoryLineageEngine, *, event_type: str, agent_id: str, stream_id: str, memory_id: str, payload: dict, parent_event_id: str | None = None) -> dict[str, Any]:
    return emit_implicit_event(
        lineage=lineage,  # type: ignore[arg-type]
        event_type=event_type,
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload=payload,
        parent_event_id=parent_event_id,
    )


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    return rebuild_from_lineage(events)
