from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from .audit import rebuild_state, verify_replay_determinism
from .compaction import compact_events_to_parquet_layout
from .config import Settings
from .contracts import Event, utc_now_iso
from .lineage import EventLog
from .retrieval import VectorIndex, select_eligible_memories
from .state_store import StateStore


class MemoryLabService:
    """Small orchestration layer for API/workers and experiments."""

    def __init__(self, root: Path, settings: Settings | None = None) -> None:
        self.root = root
        self.settings = settings or Settings.from_env()
        self.log = EventLog(root)
        self.state_store = StateStore(root)
        self.vector_index = VectorIndex(root)

    def ingest_event(
        self,
        *,
        memory_id: str,
        sequence: int,
        event_type: str,
        payload: dict[str, Any],
        source: str,
    ) -> bool:
        event = Event(
            event_id=str(uuid4()),
            sequence=sequence,
            event_type=event_type,
            memory_id=memory_id,
            payload=payload,
            source=source,
            timestamp=utc_now_iso(),
        )
        inserted = self.log.append(event)
        if not inserted:
            return False
        self._materialize()
        return True

    def _materialize(self) -> None:
        state = rebuild_state(self.log)
        self.state_store.persist(state)
        for mem in state.values():
            self.vector_index.upsert_from_state(
                mem,
                agent_id=f"{self.settings.aws_vector_bucket_name}/{self.settings.aws_vector_index_name}",
            )

    def retrieve(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        state = rebuild_state(self.log)
        return select_eligible_memories(query, self.vector_index, state, top_k=top_k)

    def replay_verify(self) -> bool:
        live = rebuild_state(self.log)
        rebuilt = rebuild_state(self.log)
        return verify_replay_determinism(live, rebuilt)

    def compact(self) -> list[str]:
        return [str(p) for p in compact_events_to_parquet_layout(self.root)]

    def export_snapshot(self) -> dict[str, dict]:
        return {memory_id: asdict(mem) for memory_id, mem in rebuild_state(self.log).items()}
