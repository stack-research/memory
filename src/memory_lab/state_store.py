from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .contracts import MemoryState
from .invariants import validate_state
from .storage import write_json


class StateStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.state_root = root / "state"

    def persist(self, states: dict[str, MemoryState]) -> None:
        for memory_id, state in states.items():
            validate_state(state)
            path = self.state_root / state.status / f"{memory_id}.json"
            write_json(path, asdict(state))
