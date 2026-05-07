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


def _top_keys(result: dict[str, Any], k: int = 3) -> list[str]:
    return [r.get("key", "") for r in result.get("vectors", [])[:k]]


def run() -> None:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = LineageEngine(storage)
    ingestion = AthenaLineageIngestionJob(cfg)
    athena = make_session(cfg).client("athena")

    agent_id = "lab-agent-1"
    stream_id = "exp-e8"

    seeds = [
        ("mem-e8-1", "Customer wants weekly summary email at 9 AM Monday."),
        ("mem-e8-2", "Customer disables weekend push notifications."),
        ("mem-e8-3", "Customer prefers monthly invoice reminders."),
    ]

    for memory_id, claim in seeds:
        vectors.put_memory_vector(
            key=memory_id,
            vector=embedder.embed_text(claim),
            metadata={
                "agent_id": agent_id,
                "stream_id": stream_id,
                "kind": "claim",
                "status": "active",
                "source_trust": 0.74,
                "confidence": 0.7,
                "reinforcement": 1.1,
            },
        )
        lineage.emit(
            event_type="observed",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=memory_id,
            payload={"claim": claim, "status": "active", "confidence": 0.7},
        )

    ingestion.run_once()

    query_text = "What communication preferences does the customer have?"
    query_vec = embedder.embed_text(query_text)

    before = vectors.query(vector=query_vec, top_k=5, agent_id=agent_id, stream_id=stream_id)
    before_top = _top_keys(before, k=3)

    # simulate rebuild: delete this experiment's vectors only, then rebuild from canonical lineage
    vector_keys = [memory_id for memory_id, _ in seeds]
    vectors.delete_memory_vectors(vector_keys)

    events = _query_events(
        athena,
        target_table_fqn=cfg.athena_target_table_fqn,
        stream_id=stream_id,
    )
    rebuilt_claims: dict[str, str] = {}
    for event in events:
        if event.get("event_type") not in {"observed", "mutated"}:
            continue
        mid = event["memory_id"]
        if mid not in vector_keys:
            continue
        claim = event.get("payload", {}).get("claim")
        if claim:
            rebuilt_claims[mid] = claim

    for memory_id, claim in rebuilt_claims.items():
        vectors.put_memory_vector(
            key=memory_id,
            vector=embedder.embed_text(claim),
            metadata={
                "agent_id": agent_id,
                "stream_id": stream_id,
                "kind": "rebuilt",
                "status": "active",
                "source_trust": 0.74,
                "confidence": 0.7,
                "reinforcement": 1.1,
            },
        )

    after = vectors.query(vector=query_vec, top_k=5, agent_id=agent_id, stream_id=stream_id)
    after_top = _top_keys(after, k=3)

    overlap = len(set(before_top).intersection(set(after_top)))
    equivalent_within_tolerance = overlap >= 2

    lineage.emit(
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="vector-rebuild-e8",
        payload={
            "query": query_text,
            "before_top3": before_top,
            "after_top3": after_top,
            "top3_overlap": overlap,
            "equivalent_within_tolerance": equivalent_within_tolerance,
        },
    )

    print(
        {
            "equivalent_within_tolerance": equivalent_within_tolerance,
            "top3_overlap": overlap,
            "before_top3": before_top,
            "after_top3": after_top,
        }
    )


if __name__ == "__main__":
    run()
