from __future__ import annotations

import os
import sys
import uuid

from src.bootstrap import ensure_lineage_bootstrap
from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.experiments.e6_poisoning_before_promotion import run as run_e6
from src.lineage_engine import LineageEngine
from src.explicit_memory.recall import RecallEngine
from src.storage import LineageStorage
from src.vectors import RecallVectors


def _fail(msg: str) -> None:
    print({"phase6_regression": "FAILED", "reason": msg})
    raise SystemExit(1)


def main() -> None:
    cfg = load_config()
    storage = LineageStorage(cfg)
    ensure_lineage_bootstrap(storage)

    # 1) Quarantine path should emit deterministic suspicion/threat tags.
    run_e6()

    # 2) Cross-scope candidate should be observable as explicit rejection reason.
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = LineageEngine(storage)
    recall = RecallEngine(vectors=vectors, embedder=embedder, lineage=lineage, policy=cfg.retrieval_policy)

    run_id = os.environ.get("MEMORY_LAB_REPLAY_RUN_ID", f"phase6-{uuid.uuid4().hex[:8]}")
    agent_id = "lab-agent-1"
    stream_id = f"phase6-regression-{run_id}"
    vectors.set_lineage_context(lineage=lineage, agent_id=agent_id, stream_id=stream_id)
    other_agent_id = "lab-agent-2"
    other_stream_id = f"phase6-other-{run_id}"

    in_scope_memory_id = f"mem-phase6-in-scope-{run_id}"
    cross_scope_memory_id = f"mem-phase6-cross-scope-{run_id}"

    in_scope_claim = "Customer opted in to all security notifications."
    cross_scope_claim = "Customer opted out of all security notifications."

    vectors.put_memory_vector(
        key=in_scope_memory_id,
        vector=embedder.embed_text(in_scope_claim),
        metadata={
            "agent_id": agent_id,
            "stream_id": stream_id,
            "source_trust": 0.8,
            "reinforcement": 1.0,
            "has_conflicts": False,
            "safety": 1.0,
            "status": "active",
            "kind": "claim",
        },
    )
    vectors.put_memory_vector(
        key=cross_scope_memory_id,
        vector=embedder.embed_text(cross_scope_claim),
        metadata={
            "agent_id": other_agent_id,
            "stream_id": other_stream_id,
            "source_trust": 0.95,
            "reinforcement": 1.2,
            "has_conflicts": True,
            "safety": 1.0,
            "status": "active",
            "kind": "claim",
        },
    )

    result = recall.retrieve(
        agent_id=agent_id,
        stream_id=stream_id,
        query="What is the customer security notification preference?",
        top_k=10,
    )

    cross_scope_rejections = [
        row for row in result.get("rejected", []) if row.get("reason") == "cross_scope_reference_attempt"
    ]
    if not cross_scope_rejections:
        _fail("No cross_scope_reference_attempt rejection observed")

    print(
        {
            "phase6_regression": "PASSED",
            "stream_id": stream_id,
            "cross_scope_rejection_count": len(cross_scope_rejections),
            "accepted_count": len(result.get("accepted", [])),
            "rejected_count": len(result.get("rejected", [])),
        }
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover
        print({"phase6_regression": "FAILED", "error": str(exc)})
        sys.exit(1)
