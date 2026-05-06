from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .lineage import EventLog
from .storage import write_jsonl


def compact_events_to_parquet_layout(root: Path) -> list[Path]:
    """
    Write compacted data into parquet-like partition layout.
    Uses JSONL payload files as scaffold unless pyarrow is added later.
    """
    log = EventLog(root)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for event in log.list_events():
        ts = event.timestamp
        dt = ts[:10]
        hour = ts[11:13] if len(ts) >= 13 else "00"
        grouped[(dt, hour)].append(
            {
                "event_id": event.event_id,
                "memory_id": event.memory_id,
                "event_type": event.event_type,
                "sequence": event.sequence,
                "source": event.source,
                "timestamp": event.timestamp,
                "source_event_id": event.event_id,
                "source_payload_hash": json.dumps(event.payload, sort_keys=True),
                "payload": event.payload,
            }
        )

    paths: list[Path] = []
    for (dt, hour), rows in grouped.items():
        out = root / "events" / "parquet" / f"dt={dt}" / f"hour={hour}" / "events.parquet.jsonl"
        write_jsonl(out, rows)
        paths.append(out)
    return paths


def glue_bootstrap_schema() -> dict:
    return {
        "table": "memory_events",
        "partitions": ["dt", "hour"],
        "columns": [
            ("event_id", "string"),
            ("memory_id", "string"),
            ("event_type", "string"),
            ("sequence", "bigint"),
            ("source", "string"),
            ("timestamp", "string"),
            ("source_event_id", "string"),
            ("source_payload_hash", "string"),
            ("payload", "string"),
        ],
    }
