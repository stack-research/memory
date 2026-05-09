from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.eligibility import eligibility_gate
from src.implicit_memory.settings import load_implicit_test_settings


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-e"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    cfg = load_implicit_test_settings()

    # A and not-A remain present; context shifts should change winner, not erase loser.
    claims = [
        {
            "memory_id": "e-A",
            "claim": "Customer wants weekly reports.",
            "trust": 0.72,
            "recency": 0.75,
            "reinforcement": 1.05,
            "consistency": 0.65,
            "safety": 1.0,
        },
        {
            "memory_id": "e-notA",
            "claim": "Customer wants monthly reports.",
            "trust": 0.68,
            "recency": 0.95,
            "reinforcement": 1.0,
            "consistency": 0.95,
            "safety": 1.0,
        },
    ]

    for c in claims:
        emit(
            lineage,
            event_type="observed",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=c["memory_id"],
            payload={"claim": c["claim"]},
        )

    contexts = [
        {"name": "ctx-weekly", "relevance_A": 0.95, "relevance_notA": 0.55},
        {"name": "ctx-monthly", "relevance_A": 0.55, "relevance_notA": 0.95},
    ]

    winners: list[str] = []

    for ctx in contexts:
        dec_a = eligibility_gate(
            relevance=ctx["relevance_A"],
            trust=claims[0]["trust"],
            recency=claims[0]["recency"],
            reinforcement=claims[0]["reinforcement"],
            consistency=claims[0]["consistency"],
            safety=claims[0]["safety"],
            threshold=cfg.eligibility_threshold,
        )
        dec_b = eligibility_gate(
            relevance=ctx["relevance_notA"],
            trust=claims[1]["trust"],
            recency=claims[1]["recency"],
            reinforcement=claims[1]["reinforcement"],
            consistency=claims[1]["consistency"],
            safety=claims[1]["safety"],
            threshold=cfg.eligibility_threshold,
        )

        winner = "e-A" if dec_a.score >= dec_b.score else "e-notA"
        winners.append(winner)

        emit(
            lineage,
            event_type="implicit_trigger_fired",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=f"winner-{ctx['name']}",
            payload={
                "context": ctx["name"],
                "winner": winner,
                "score_A": dec_a.score,
                "score_notA": dec_b.score,
                "allow_A": dec_a.allow_influence,
                "allow_notA": dec_b.allow_influence,
            },
        )

    # persistence: both original conflict memories must remain observed in lineage
    observed_ids = [e.get("memory_id") for e in events if e.get("event_type") == "observed"]
    persistence_ok = "e-A" in observed_ids and "e-notA" in observed_ids
    contextual_flip = len(set(winners)) > 1

    summary = {
        "suite": "E",
        "winners": winners,
        "persistence_ok": persistence_ok,
        "contextual_flip": contextual_flip,
        "pass": persistence_ok and contextual_flip,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
