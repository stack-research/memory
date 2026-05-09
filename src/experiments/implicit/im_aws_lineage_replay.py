from __future__ import annotations

import os
import time
from collections import Counter
from datetime import datetime, timezone

from src.bootstrap import ensure_lineage_bootstrap
from src.config import load_config
from src.ingestion.athena_ingestion import AthenaLineageIngestionJob
from src.lineage_engine import LineageEngine
from src.lineage_reader import build_lineage_reader
from src.storage import LineageStorage


def run() -> dict:
    cfg = load_config()
    storage = LineageStorage(cfg)
    ensure_lineage_bootstrap(storage)
    lineage = LineageEngine(storage)

    agent_id = "lab-agent-1"
    stream_id = f"im-aws-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    events = [
        ("implicit_trigger_evaluated", "aws-1", {"action": "invoke_encode", "score": 0.72}),
        ("implicit_trigger_fired", "aws-1", {"decision": "admitted"}),
        ("contamination_suspected", "aws-2", {"reason": "urgency_spoof_suspected"}),
        ("implicit_rejected", "aws-2", {"reason": "event_flood_suspected"}),
        ("reflex_mode_entered", "aws-3", {"budget": 2}),
        ("reflex_action_executed", "aws-3", {"step": 1}),
        ("reflex_mode_exited", "aws-3", {"reason": "cycle_complete"}),
    ]

    for event_type, memory_id, payload in events:
        lineage.emit(
            event_type=event_type,
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            actor_class="implicit_memory_controller",
            source_class="internal_engine",
            payload=payload,
        )

    if os.environ.get("IMPLICIT_RUN_INGESTION", "1") == "1":
        AthenaLineageIngestionJob(cfg).run_once()

    reader = build_lineage_reader(cfg)
    max_wait = int(os.environ.get("IMPLICIT_AWS_REPLAY_WAIT_SECONDS", "60"))
    deadline = time.time() + max_wait
    rows = []
    while time.time() < deadline:
        rows = reader.query_events(stream_id=stream_id)
        if len(rows) >= len(events):
            break
        time.sleep(3)

    counts = Counter(row.get("event_type", "") for row in rows)
    required = {name for name, _, _ in events}
    missing = sorted([name for name in required if counts.get(name, 0) == 0])

    summary = {
        "suite": "AWS",
        "stream_id": stream_id,
        "expected_events": len(events),
        "observed_events": len(rows),
        "event_type_counts": dict(counts),
        "missing_event_types": missing,
        "pass": len(missing) == 0 and len(rows) >= len(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
