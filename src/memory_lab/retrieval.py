from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .contracts import MemoryState, VectorRecord, stable_json_hash
from .embeddings import cosine_similarity, embed_text
from .invariants import validate_vector_record
from .storage import read_json, write_json


class VectorIndex:
    def __init__(self, root: Path) -> None:
        self.path = root / "vectors" / "index.json"

    def load(self) -> list[VectorRecord]:
        if not self.path.exists():
            return []
        rows = read_json(self.path)["records"]
        return [VectorRecord(**row) for row in rows]

    def upsert_from_state(self, state: MemoryState, agent_id: str = "agent-memory") -> None:
        records = self.load()
        claim_hash = stable_json_hash({"claim": state.claim})
        vector = VectorRecord(
            memory_id=state.memory_id,
            embedding=embed_text(state.claim),
            claim_hash=claim_hash,
            source_event_id=state.source_event_id,
            source_payload_hash=state.source_payload_hash,
            agent_id=agent_id,
            status=state.status,
            kind="memory",
            source_trust=state.trust_score,
            confidence=state.confidence,
            decay_score=state.decay_score,
            last_recalled_ts=state.last_recalled,
            assertion_ts=state.assertion_ts,
            has_conflicts=bool(state.conflicts),
        )
        validate_vector_record(vector)

        by_id = {r.memory_id: r for r in records}
        by_id[state.memory_id] = vector
        payload = {"records": [asdict(row) for row in by_id.values()]}
        write_json(self.path, payload)

    def search(self, query: str, top_k: int = 10) -> list[tuple[VectorRecord, float]]:
        query_emb = embed_text(query)
        scored = []
        for record in self.load():
            sim = cosine_similarity(query_emb, record.embedding)
            scored.append((record, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


def _recency_component(last_recalled: str | None) -> float:
    return 0.7 if last_recalled is None else 1.0


def _reinforcement_component(access_count: int) -> float:
    return min(1.0, 0.2 + (access_count * 0.05))


def _consistency_component(state: MemoryState) -> float:
    return max(0.0, 1.0 - (len(state.conflicts) * 0.1))


def eligibility_score(relevance: float, state: MemoryState) -> float:
    score = (
        max(0.0, relevance)
        * state.trust_score
        * _recency_component(state.last_recalled)
        * _reinforcement_component(state.reinforcement_count)
        * _consistency_component(state)
        * state.safety_score
    )
    return max(0.0, min(1.0, score))


def select_eligible_memories(
    query: str,
    vector_index: VectorIndex,
    state_by_id: dict[str, MemoryState],
    top_k: int = 10,
) -> list[tuple[str, float]]:
    ranked = []
    for vector_record, relevance in vector_index.search(query, top_k=top_k):
        state = state_by_id.get(vector_record.memory_id)
        if state is None:
            continue
        if state.status in {"quarantined", "deleted"}:
            continue
        score = eligibility_score(relevance, state)
        if score <= 0:
            continue
        ranked.append((state.memory_id, score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked
