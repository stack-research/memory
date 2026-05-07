from __future__ import annotations

import json
import time
from typing import Any

from src.aws_session import make_session
from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.ingestion.athena_ingestion import AthenaLineageIngestionJob
from src.lineage_engine import LineageEngine
from src.storage import LineageStorage
from src.vectors import RecallVectors



def _wait_for_query(athena: Any, query_execution_id: str) -> str:
    while True:
        resp = athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = resp["QueryExecution"]["Status"]["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return state
        time.sleep(1)


def _query_events(athena: Any, *, target_table_fqn: str, stream_id: str) -> list[dict[str, Any]]:
    sql = (
        "SELECT memory_id, event_type, payload, event_time "
        f"FROM {target_table_fqn} "
        f"WHERE stream_id = '{stream_id}' "
        "ORDER BY event_time"
    )
    start = athena.start_query_execution(
        QueryString=sql,
        WorkGroup="memory-lab",
        QueryExecutionContext={"Database": "memory_lab", "Catalog": "AwsDataCatalog"},
    )
    qid = start["QueryExecutionId"]
    state = _wait_for_query(athena, qid)
    if state != "SUCCEEDED":
        raise RuntimeError(f"Athena query failed: {qid} state={state}")

    rows: list[dict[str, Any]] = []
    paginator = athena.get_paginator("get_query_results")
    for page in paginator.paginate(QueryExecutionId=qid):
        for row in page["ResultSet"]["Rows"]:
            data = row.get("Data", [])
            if len(data) < 4:
                continue
            # skip header row
            if data[0].get("VarCharValue") == "memory_id":
                continue
            payload_raw = data[2].get("VarCharValue", "{}")
            rows.append(
                {
                    "memory_id": data[0].get("VarCharValue", ""),
                    "event_type": data[1].get("VarCharValue", ""),
                    "payload": json.loads(payload_raw) if payload_raw else {},
                    "event_time": data[3].get("VarCharValue", ""),
                }
            )
    return rows


def run() -> None:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = LineageEngine(storage)
    ingestion = AthenaLineageIngestionJob(cfg)
    athena = make_session(cfg).client("athena")

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
    events = _query_events(
        athena,
        target_table_fqn=cfg.athena_target_table_fqn,
        stream_id=stream_id,
    )
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
        },
    )

    print({"replay_equal": equal, "rebuilt": rebuilt, "expected": expected})


if __name__ == "__main__":
    run()
