from __future__ import annotations

from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.experiments.engine_helper import make_experiment_engine
from src.explicit_memory.recall import RecallEngine
from src.storage import LineageStorage
from src.vectors import RecallVectors



def run() -> None:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = make_experiment_engine(storage)
    recall = RecallEngine(vectors=vectors, embedder=embedder, lineage=lineage, policy=cfg.retrieval_policy)

    agent_id = "lab-agent-1"
    stream_id = "exp-e1"
    vectors.set_lineage_context(lineage=lineage, agent_id=agent_id, stream_id=stream_id)

    false_claim = "The capital of Australia is Sydney."
    true_claim = "The capital of Australia is Canberra."

    false_vec = embedder.embed_text(false_claim)
    true_vec = embedder.embed_text(true_claim)

    vectors.put_memory_vector(
        key="mem-false-trusted",
        vector=false_vec,
        metadata={"source_trust": 0.95, "kind": "claim", "status": "active", "reinforcement": 1.0, "agent_id": agent_id, "stream_id": stream_id},
    )
    vectors.put_memory_vector(
        key="mem-true-weak",
        vector=true_vec,
        metadata={"source_trust": 0.40, "kind": "claim", "status": "active", "reinforcement": 1.0, "agent_id": agent_id, "stream_id": stream_id},
    )

    print(
        lineage.emit(
            event_type="observed",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id="mem-false-trusted",
            payload={"claim": false_claim},
        )
    )
    print(
        lineage.emit(
            event_type="observed",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id="mem-true-weak",
            payload={"claim": true_claim},
        )
    )

    result = recall.retrieve(
        agent_id=agent_id,
        stream_id=stream_id,
        query="What is the capital of Australia?",
        top_k=5,
    )
    print(result)


if __name__ == "__main__":
    run()
