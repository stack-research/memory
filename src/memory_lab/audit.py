from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .contracts import MemoryState
from .lineage import EventLog
from .reducer import reduce_events
from .storage import read_json


def rebuild_state(log: EventLog) -> dict[str, MemoryState]:
    return reduce_events(log.list_events())


def verify_replay_determinism(live_state: dict[str, MemoryState], rebuilt_state: dict[str, MemoryState]) -> bool:
    def norm(state: dict[str, MemoryState]) -> dict:
        return {k: asdict(v) for k, v in sorted(state.items())}

    return norm(live_state) == norm(rebuilt_state)


class AuditAPI:
    """Function-level API surface matching the v0 audit endpoints."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.log = EventLog(root)

    def beliefs_current(self) -> dict:
        state = rebuild_state(self.log)
        return {memory_id: asdict(mem) for memory_id, mem in state.items()}

    def memory_lineage(self, memory_id: str) -> list[dict]:
        events = self.log.list_events()
        return [asdict(e) for e in events if e.memory_id == memory_id]

    def beliefs_at_sequence(self, sequence_by_memory: dict[str, int]) -> dict:
        events = []
        for event in self.log.list_events():
            cutoff = sequence_by_memory.get(event.memory_id, -1)
            if event.sequence <= cutoff:
                events.append(event)
        return {k: asdict(v) for k, v in reduce_events(events).items()}

    def diff(self, earlier: dict[str, int], later: dict[str, int]) -> dict:
        a = self.beliefs_at_sequence(earlier)
        b = self.beliefs_at_sequence(later)
        keys = sorted(set(a) | set(b))
        output: dict[str, dict] = {}
        for key in keys:
            if a.get(key) != b.get(key):
                output[key] = {"before": a.get(key), "after": b.get(key)}
        return output

    def latest_materialized_state(self) -> dict[str, dict]:
        state_root = self.root / "state"
        if not state_root.exists():
            return {}
        out = {}
        for path in sorted(state_root.glob("*/*.json")):
            out[path.stem] = read_json(path)
        return out
