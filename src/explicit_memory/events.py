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
        actor_class: str = "explicit_memory_controller",
        source_class: str = "internal_engine",
        parent_event_id: str | None = None,
        record_kind: str | None = None,
        assertion_kind: str | None = None,
        subject_event_id: str | None = None,
        subject_record_kind: str | None = None,
        subject_assertion_kind: str | None = None,
    ): ...


def emit_explicit_event(
    *,
    lineage: _LineageLike,
    event_type: str,
    agent_id: str,
    stream_id: str,
    memory_id: str,
    payload: dict[str, Any],
    actor_class: str = "explicit_memory_controller",
    source_class: str = "internal_engine",
    parent_event_id: str | None = None,
    record_kind: str | None = None,
    assertion_kind: str | None = None,
    subject_event_id: str | None = None,
    subject_record_kind: str | None = None,
    subject_assertion_kind: str | None = None,
) -> dict[str, Any]:
    event = lineage.emit(
        event_type=event_type,
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        actor_class=actor_class,
        source_class=source_class,
        payload=payload,
        parent_event_id=parent_event_id,
        record_kind=record_kind,
        assertion_kind=assertion_kind,
        subject_event_id=subject_event_id,
        subject_record_kind=subject_record_kind,
        subject_assertion_kind=subject_assertion_kind,
    )
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "memory_id": event.memory_id,
    }


def emit_observed(
    *,
    lineage: _LineageLike,
    agent_id: str,
    stream_id: str,
    memory_id: str,
    payload: dict[str, Any],
    parent_event_id: str | None = None,
) -> dict[str, Any]:
    return emit_explicit_event(
        lineage=lineage,
        event_type="observed",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload=payload,
        parent_event_id=parent_event_id,
    )


def emit_recalled(
    *,
    lineage: _LineageLike,
    agent_id: str,
    stream_id: str,
    memory_id: str,
    payload: dict[str, Any],
    parent_event_id: str | None = None,
) -> dict[str, Any]:
    return emit_explicit_event(
        lineage=lineage,
        event_type="recalled",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload=payload,
        parent_event_id=parent_event_id,
    )


def emit_rejected(
    *,
    lineage: _LineageLike,
    agent_id: str,
    stream_id: str,
    memory_id: str,
    payload: dict[str, Any],
    parent_event_id: str | None = None,
) -> dict[str, Any]:
    return emit_explicit_event(
        lineage=lineage,
        event_type="rejected",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload=payload,
        parent_event_id=parent_event_id,
    )


def emit_mutated(
    *,
    lineage: _LineageLike,
    agent_id: str,
    stream_id: str,
    memory_id: str,
    payload: dict[str, Any],
    parent_event_id: str | None = None,
) -> dict[str, Any]:
    return emit_explicit_event(
        lineage=lineage,
        event_type="mutated",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload=payload,
        parent_event_id=parent_event_id,
    )


def emit_promoted(
    *,
    lineage: _LineageLike,
    agent_id: str,
    stream_id: str,
    memory_id: str,
    payload: dict[str, Any],
    parent_event_id: str | None = None,
) -> dict[str, Any]:
    return emit_explicit_event(
        lineage=lineage,
        event_type="promoted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload=payload,
        parent_event_id=parent_event_id,
    )


__all__ = [
    "emit_explicit_event",
    "emit_observed",
    "emit_recalled",
    "emit_rejected",
    "emit_mutated",
    "emit_promoted",
]
