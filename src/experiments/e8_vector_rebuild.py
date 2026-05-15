from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.ingestion.athena_ingestion import AthenaLineageIngestionJob
from src.experiments.engine_helper import make_experiment_engine
from src.lineage_reader import build_lineage_reader
from src.storage import LineageStorage
from src.types import EVENT_SCHEMA_VERSION
from src.vectors import RecallVectors


def _top_keys(result: dict[str, Any], k: int = 3) -> list[str]:
    return [r.get("key", "") for r in result.get("vectors", [])[:k]]


def _top_signature(before_top: list[str], after_top: list[str]) -> str:
    stable = json.dumps({"before": before_top, "after": after_top}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def run() -> dict[str, Any]:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = make_experiment_engine(storage)
    ingestion = AthenaLineageIngestionJob(cfg)
    lineage_reader = build_lineage_reader(cfg)

    agent_id = "lab-agent-1"
    stream_id = "exp-e8"
    vectors.set_lineage_context(lineage=lineage, agent_id=agent_id, stream_id=stream_id)
    run_id = os.environ.get("MEMORY_LAB_REPLAY_RUN_ID", "phase5-default")
    reader_backend = os.environ.get("AWS_LINEAGE_READER_BACKEND", "s3tables")

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
            payload={"run_id": run_id, "claim": claim, "status": "active", "confidence": 0.7},
        )

    ingestion.run_once()

    query_text = "What communication preferences does the customer have?"
    query_vec = embedder.embed_text(query_text)

    before = vectors.query(vector=query_vec, top_k=5, agent_id=agent_id, stream_id=stream_id)
    before_top = _top_keys(before, k=3)

    vector_keys = [memory_id for memory_id, _ in seeds]
    vectors.delete_memory_vectors(vector_keys)

    events = lineage_reader.query_events(stream_id=stream_id)
    rebuilt_claims: dict[str, str] = {}
    for event in events:
        if event.get("event_type") not in {"observed", "mutated"}:
            continue
        mid = event["memory_id"]
        if mid not in vector_keys:
            continue
        payload = event.get("payload", {})
        if payload.get("run_id") != run_id:
            continue
        claim = payload.get("claim")
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
    tolerance = int(os.environ.get("MEMORY_E8_TOPK_OVERLAP_TOLERANCE", "2"))
    equivalent_within_tolerance = overlap >= tolerance
    ranking_signature = _top_signature(before_top, after_top)

    summary = {
        "stream_id": stream_id,
        "run_id": run_id,
        "equivalent_within_tolerance": equivalent_within_tolerance,
        "top3_overlap": overlap,
        "tolerance": tolerance,
        "before_top3": before_top,
        "after_top3": after_top,
        "ranking_signature": ranking_signature,
    }

    lineage.emit(
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="vector-rebuild-e8",
        payload={
            "snapshot_type": "vector_rebuild_equivalence",
            "snapshot_stage": "post_rebuild",
            "snapshot_cadence": "per_run",
            "stream_id": stream_id,
            "run_id": run_id,
            "query": query_text,
            "before_top3": before_top,
            "after_top3": after_top,
            "top3_overlap": overlap,
            "tolerance": tolerance,
            "equivalent_within_tolerance": equivalent_within_tolerance,
            "ranking_signature": ranking_signature,
            "lineage_reader_backend": reader_backend,
            "event_schema_version": EVENT_SCHEMA_VERSION,
            **cfg.retrieval_policy.audit_fields(),
        },
    )
    ingestion.run_once()

    print(summary)
    return summary


if __name__ == "__main__":
    run()
