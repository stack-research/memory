from __future__ import annotations

from pathlib import Path
from typing import Any

from memory_lab.audit import rebuild_state
from memory_lab.config import Settings, load_dotenv
from memory_lab.lineage import EventLog
from memory_lab.retrieval import VectorIndex
from memory_lab.service import MemoryLabService


def handler(_event: dict[str, Any], _context: Any) -> dict[str, Any]:
    load_dotenv()
    settings = Settings.from_env()
    root = Path(settings.memory_root)
    root.mkdir(parents=True, exist_ok=True)

    service = MemoryLabService(root, settings=settings)
    compact_outputs = service.compact()

    # Minimal sleep flow: replay and upsert vectors from rebuilt state.
    log = EventLog(root)
    state = rebuild_state(log)
    vector_index = VectorIndex(root)
    for mem in state.values():
        vector_index.upsert_from_state(
            mem,
            agent_id=f"{settings.aws_vector_bucket_name}/{settings.aws_vector_index_name}",
        )

    return {
        "ok": True,
        "compaction_outputs": compact_outputs,
        "memory_count": len(state),
    }
