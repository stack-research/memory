from __future__ import annotations

from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.eligibility_engine import score_candidate
from src.lineage_engine import LineageEngine
from src.storage import LineageStorage
from src.time_engine import decay_score
from src.vectors import RecallVectors



def _eligibility(*, relevance: float, trust: float, hours_stale: float, reinforcement: float) -> float:
    return score_candidate(
        relevance=relevance,
        trust=trust,
        recency=decay_score(hours_since_last_reinforced=hours_stale),
        reinforcement=reinforcement,
        consistency=1.0,
        safety=1.0,
    )


def run() -> None:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = LineageEngine(storage)

    agent_id = "lab-agent-1"
    stream_id = "exp-e3"

    spaced_id = "mem-e3-spaced"
    single_id = "mem-e3-single-strong"

    claim_spaced = "Database backup verification was completed successfully each week."
    claim_single = "Database backup verification was completed successfully once with a strong confidence update."

    vec_spaced = embedder.embed_text(claim_spaced)
    vec_single = embedder.embed_text(claim_single)

    trust_spaced = 0.7
    trust_single = 0.7
    reinforcement_spaced = 1.0
    reinforcement_single = 2.5

    vectors.put_memory_vector(
        key=spaced_id,
        vector=vec_spaced,
        metadata={"source_trust": trust_spaced, "reinforcement": reinforcement_spaced, "hours_stale": 0.0, "kind": "episodic", "status": "active", "agent_id": agent_id, "stream_id": stream_id},
    )
    vectors.put_memory_vector(
        key=single_id,
        vector=vec_single,
        metadata={"source_trust": trust_single, "reinforcement": reinforcement_single, "hours_stale": 0.0, "kind": "episodic", "status": "active", "agent_id": agent_id, "stream_id": stream_id},
    )

    lineage.emit(event_type="observed", agent_id=agent_id, stream_id=stream_id, memory_id=spaced_id, payload={"claim": claim_spaced, "strategy": "spaced"})
    lineage.emit(event_type="observed", agent_id=agent_id, stream_id=stream_id, memory_id=single_id, payload={"claim": claim_single, "strategy": "single_strong"})

    checkpoints = [0, 24, 72, 168]
    relevance_spaced = 0.9
    relevance_single = 0.9

    for i, hours in enumerate(checkpoints):
        if i > 0:
            reinforcement_spaced += 0.35
            lineage.emit(
                event_type="recalled",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=spaced_id,
                payload={"hours_since_start": hours, "strategy": "spaced", "reinforcement_after": reinforcement_spaced},
            )

        score_spaced = _eligibility(
            relevance=relevance_spaced,
            trust=trust_spaced,
            hours_stale=0.0 if i > 0 else hours,
            reinforcement=reinforcement_spaced,
        )
        score_single = _eligibility(
            relevance=relevance_single,
            trust=trust_single,
            hours_stale=hours,
            reinforcement=reinforcement_single,
        )

        lineage.emit(
            event_type="mutated",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=spaced_id,
            payload={
                "hours_since_start": hours,
                "strategy": "spaced",
                "eligibility_score": score_spaced,
                "reinforcement": reinforcement_spaced,
                "hours_stale": 0.0 if i > 0 else hours,
            },
        )
        lineage.emit(
            event_type="mutated",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=single_id,
            payload={
                "hours_since_start": hours,
                "strategy": "single_strong",
                "eligibility_score": score_single,
                "reinforcement": reinforcement_single,
                "hours_stale": hours,
            },
        )

        vectors.put_memory_vector(
            key=spaced_id,
            vector=vec_spaced,
            metadata={"source_trust": trust_spaced, "reinforcement": reinforcement_spaced, "hours_stale": 0.0 if i > 0 else hours, "kind": "episodic", "status": "active", "agent_id": agent_id, "stream_id": stream_id},
        )
        vectors.put_memory_vector(
            key=single_id,
            vector=vec_single,
            metadata={"source_trust": trust_single, "reinforcement": reinforcement_single, "hours_stale": hours, "kind": "episodic", "status": "active", "agent_id": agent_id, "stream_id": stream_id},
        )

        print({"hours": hours, "spaced_score": score_spaced, "single_strong_score": score_single})


if __name__ == "__main__":
    run()
