from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.contamination import contamination_risk
from src.implicit_memory.eligibility import eligibility_gate
from src.implicit_memory.settings import load_implicit_test_settings


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-b"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    cfg = load_implicit_test_settings()

    # Simulated article-derived claims with conflict/trust asymmetry.
    claims = [
        {
            "memory_id": "b-claim-1",
            "concept": "Concept-X",
            "claim": "Concept-X increases reliability under low load.",
            "source_trust": 0.65,
            "support": 0.8,
            "conflict": 0.3,
            "recency": 0.9,
            "reinforcement": 1.0,
            "consistency": 0.9,
        },
        {
            "memory_id": "b-claim-2",
            "concept": "Concept-X",
            "claim": "Concept-X always increases reliability under all load.",
            "source_trust": 0.95,
            "support": 0.2,
            "conflict": 0.85,
            "recency": 0.85,
            "reinforcement": 1.0,
            "consistency": 0.6,
        },
    ]

    # Ingest/extract phase.
    for c in claims:
        emit(
            lineage,
            event_type="observed",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=c["memory_id"],
            payload={"concept": c["concept"], "claim": c["claim"], "phase": "ingest"},
        )

    # Session reset + time lapse markers.
    emit(
        lineage,
        event_type="implicit_trigger_deferred",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="b-reset",
        payload={"reason": "session_reset", "phase": "reset"},
    )
    emit(
        lineage,
        event_type="implicit_trigger_deferred",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="b-timegap",
        payload={"reason": "simulated_time_lapse", "hours": 72, "phase": "time_gap"},
    )

    # Recall request with partial cue after gap.
    emit(
        lineage,
        event_type="implicit_trigger_evaluated",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="b-recall",
        payload={"query": "Tell me about concept X", "partial_cue": True},
    )

    outcomes: list[dict] = []
    quarantined = 0
    for c in claims:
        risk = contamination_risk(
            source_trust=c["source_trust"],
            cross_source_support=c["support"],
            conflict_pressure=c["conflict"],
            anomaly_signal=0.6 if c["memory_id"] == "b-claim-2" else 0.1,
        )
        if risk >= cfg.contamination_threshold:
            quarantined += 1
            emit(
                lineage,
                event_type="contamination_suspected",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=c["memory_id"],
                payload={"reason": "high_trust_low_support_conflict_cluster", "risk": risk},
            )
            emit(
                lineage,
                event_type="implicit_rejected",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=c["memory_id"],
                payload={"reason": "contamination_risk_threshold", "risk": risk},
            )
            outcomes.append({"memory_id": c["memory_id"], "status": "quarantined", "risk": risk, "score": 0.0})
            continue

        dec = eligibility_gate(
            relevance=0.9,
            trust=c["source_trust"],
            recency=c["recency"],
            reinforcement=c["reinforcement"],
            consistency=c["consistency"],
            safety=1.0,
            threshold=cfg.eligibility_threshold,
        )
        event_type = "implicit_admitted" if dec.allow_influence else "implicit_rejected"
        emit(
            lineage,
            event_type=event_type,
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=c["memory_id"],
            payload={"eligibility_score": dec.score, "reason": dec.reason},
        )
        outcomes.append({"memory_id": c["memory_id"], "status": "admitted" if dec.allow_influence else "rejected", "risk": risk, "score": dec.score})

    admitted = [o for o in outcomes if o["status"] == "admitted"]
    winner = max(admitted, key=lambda x: float(x["score"]))["memory_id"] if admitted else None

    # Conflict must persist (no silent collapse): both claims remain present in lineage.
    observed_ids = {e.get("memory_id") for e in events if e.get("event_type") == "observed"}
    conflict_persisted = {"b-claim-1", "b-claim-2"}.issubset(observed_ids)

    # High-trust false-ish claim should not dominate unconditionally.
    no_false_dominance = winner != "b-claim-2"

    # Some contamination handling should occur for the risky branch.
    contamination_handled = quarantined >= 1

    summary = {
        "suite": "B",
        "winner": winner,
        "quarantined": quarantined,
        "conflict_persisted": conflict_persisted,
        "no_false_dominance": no_false_dominance,
        "contamination_handled": contamination_handled,
        "pass": conflict_persisted and no_false_dominance and contamination_handled,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
