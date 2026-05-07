from __future__ import annotations

import os
from typing import Any

from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.ingestion.athena_ingestion import AthenaLineageIngestionJob
from src.lineage_engine import LineageEngine
from src.lineage_reader import build_lineage_reader
from src.storage import LineageStorage
from src.vectors import RecallVectors



def run() -> None:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = LineageEngine(storage)
    ingestion = AthenaLineageIngestionJob(cfg)
    lineage_reader = build_lineage_reader(cfg)

    agent_id = "lab-agent-1"
    stream_id = "exp-e7"

    memories = [
        {
            "memory_id": "mem-e7-a",
            "claim": "Customer prefers weekly summary emails.",
            "confidence": 0.62,
        },
        {
            "memory_id": "mem-e7-b",
            "claim": "Customer disabled push notifications during weekends.",
            "confidence": 0.71,
        },
    ]

    expected: dict[str, dict[str, Any]] = {}

    for m in memories:
        lineage.emit(
            event_type="observed",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=m["memory_id"],
            payload={"claim": m["claim"], "status": "active", "confidence": m["confidence"]},
        )
        lineage.emit(
            event_type="mutated",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=m["memory_id"],
            payload={
                "claim": m["claim"] + " (reconfirmed)",
                "status": "active",
                "confidence": min(0.95, m["confidence"] + 0.09),
            },
        )
        expected[m["memory_id"]] = {
            "claim": m["claim"] + " (reconfirmed)",
            "status": "active",
            "confidence": min(0.95, m["confidence"] + 0.09),
        }

    ingest_result = ingestion.run_once()

    # simulate materialized state loss
    vectors.delete_memory_vectors([m["memory_id"] for m in memories])

    # replay from canonical lineage table
    events = lineage_reader.query_events(stream_id=stream_id)
    rebuilt: dict[str, dict[str, Any]] = {}
    source_memory_ids = {m["memory_id"] for m in memories}
    for event in events:
        memory_id = event["memory_id"]
        if memory_id not in source_memory_ids:
            continue
        if event.get("event_type") not in {"observed", "mutated"}:
            continue

        payload = event.get("payload", {})
        if memory_id not in rebuilt:
            rebuilt[memory_id] = {"status": "active"}
        for key in ["claim", "status", "confidence"]:
            if key in payload:
                rebuilt[memory_id][key] = payload[key]

    for memory_id, state in rebuilt.items():
        claim = state.get("claim", "")
        if not claim:
            continue
        vec = embedder.embed_text(claim)
        vectors.put_memory_vector(
            key=memory_id,
            vector=vec,
            metadata={
                "agent_id": agent_id,
                "stream_id": stream_id,
                "kind": "rebuilt",
                "status": state.get("status", "active"),
                "confidence": float(state.get("confidence", 0.5)),
                "source_trust": 0.7,
                "reinforcement": 1.0,
            },
        )

    equal = rebuilt == expected
    lineage.emit(
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="replay-e7",
        payload={
            "rebuilt_count": len(rebuilt),
            "expected_count": len(expected),
            "replay_equal": equal,
            "ingestion_state": ingest_result.get("state"),
            "lineage_reader_backend": os.environ.get("AWS_LINEAGE_READER_BACKEND", "s3tables"),
        },
    )

    print({"replay_equal": equal, "rebuilt": rebuilt, "expected": expected})


if __name__ == "__main__":
    run()
