from __future__ import annotations

from .contracts import Event, MemoryState, VectorRecord


def validate_event(event: Event) -> None:
    event.validate()


def validate_state(state: MemoryState) -> None:
    state.validate()


def validate_vector_record(record: VectorRecord) -> None:
    record.validate()


def assert_vector_traceability(record: VectorRecord, known_events: set[str]) -> None:
    if record.source_event_id and record.source_event_id in known_events:
        return
    if record.source_payload_hash:
        return
    raise ValueError("vector record is not traceable to known event or payload hash")


def assert_state_traceability(state: MemoryState, known_events: set[str]) -> None:
    if state.source_event_id and state.source_event_id in known_events:
        return
    if state.source_payload_hash:
        return
    raise ValueError("state is not traceable to known event or payload hash")


def assert_parquet_row_traceability(row: dict) -> None:
    if not row.get("source_event_id") and not row.get("source_payload_hash"):
        raise ValueError("parquet row must include source_event_id or source_payload_hash")
