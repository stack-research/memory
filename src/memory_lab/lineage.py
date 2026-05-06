from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .contracts import Event
from .invariants import validate_event
from .storage import read_json, write_json


class EventLog:
    """Append-only event store with idempotent writes."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.events_root = root / "events" / "raw"
        self.index_root = root / "indexes"
        self.event_index_file = self.index_root / "event_ids.json"
        self.seq_index_file = self.index_root / "seq_by_memory.json"

    def _load_index(self, path: Path) -> dict:
        if not path.exists():
            return {}
        return read_json(path)

    def _save_index(self, path: Path, payload: dict) -> None:
        write_json(path, payload)

    def append(self, event: Event) -> bool:
        validate_event(event)
        event_ids = self._load_index(self.event_index_file)
        seq_map = self._load_index(self.seq_index_file)

        if event.event_id in event_ids:
            return False

        memory_seq = seq_map.get(event.memory_id, -1)
        if event.sequence <= memory_seq:
            raise ValueError(
                f"sequence must increase per memory_id ({event.sequence} <= {memory_seq})"
            )

        event_path = self.events_root / event.memory_id / f"{event.sequence:020d}-{event.event_id}.json"
        if event_path.exists():
            return False

        write_json(event_path, asdict(event))
        event_ids[event.event_id] = str(event_path.relative_to(self.root))
        seq_map[event.memory_id] = event.sequence
        self._save_index(self.event_index_file, event_ids)
        self._save_index(self.seq_index_file, seq_map)
        return True

    def list_events(self) -> list[Event]:
        if not self.events_root.exists():
            return []
        rows: list[Event] = []
        files = sorted(self.events_root.glob("*/*.json"))
        for path in files:
            raw = read_json(path)
            rows.append(Event(**raw))
        rows.sort(key=lambda e: (e.memory_id, e.sequence, e.event_id))
        return rows
