from __future__ import annotations

from dataclasses import dataclass

from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.explicit_memory.eligibility import score_candidate
from src.lineage_engine import LineageEngine
from src.explicit_memory.recall import RecallEngine
from src.storage import LineageStorage
from src.vectors import RecallVectors


@dataclass
class CandidateProfile:
    memory_id: str
    claim: str
    trust: float
    hours_stale: float
    reinforcement: float
    has_conflicts: bool
    safety: float


@dataclass
class Scenario:
    name: str
    axis: str
    a: CandidateProfile
    b: CandidateProfile


def _expected_score(c: CandidateProfile) -> float:
    recency = 1.0 / (1.0 + c.hours_stale / 24.0)
    consistency = 0.6 if c.has_conflicts else 1.0
    return score_candidate(
        relevance=0.9,
        trust=c.trust,
        recency=recency,
        reinforcement=c.reinforcement,
        consistency=consistency,
        safety=c.safety,
    )


def run() -> dict:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = LineageEngine(storage)
    recall = RecallEngine(vectors=vectors, embedder=embedder, lineage=lineage, policy=cfg.retrieval_policy)

    agent_id = "lab-agent-1"
    stream_id = "exp-e9"
    vectors.set_lineage_context(lineage=lineage, agent_id=agent_id, stream_id=stream_id)

    scenarios = [
        Scenario(
            name="trust_shift",
            axis="trust",
            a=CandidateProfile(
                memory_id="mem-e9-a-trust",
                claim="The rollout was completed on Tuesday.",
                trust=0.9,
                hours_stale=6,
                reinforcement=1.1,
                has_conflicts=True,
                safety=1.0,
            ),
            b=CandidateProfile(
                memory_id="mem-e9-b-trust",
                claim="The rollout was paused at 40 percent on Tuesday.",
                trust=0.55,
                hours_stale=6,
                reinforcement=1.1,
                has_conflicts=False,
                safety=1.0,
            ),
        ),
        Scenario(
            name="recency_shift",
            axis="recency",
            a=CandidateProfile(
                memory_id="mem-e9-a-recency",
                claim="Customer prefers weekly reports.",
                trust=0.7,
                hours_stale=120,
                reinforcement=1.0,
                has_conflicts=False,
                safety=1.0,
            ),
            b=CandidateProfile(
                memory_id="mem-e9-b-recency",
                claim="Customer prefers monthly reports.",
                trust=0.7,
                hours_stale=2,
                reinforcement=1.0,
                has_conflicts=False,
                safety=1.0,
            ),
        ),
        Scenario(
            name="safety_penalty",
            axis="safety",
            a=CandidateProfile(
                memory_id="mem-e9-a-safety",
                claim="Customer opted out of all security alerts.",
                trust=0.92,
                hours_stale=4,
                reinforcement=1.2,
                has_conflicts=True,
                safety=0.2,
            ),
            b=CandidateProfile(
                memory_id="mem-e9-b-safety",
                claim="Customer asked for additional security alerts.",
                trust=0.6,
                hours_stale=8,
                reinforcement=1.0,
                has_conflicts=False,
                safety=1.0,
            ),
        ),
    ]

    results: list[dict] = []

    for scenario in scenarios:
        for candidate in [scenario.a, scenario.b]:
            vectors.put_memory_vector(
                key=candidate.memory_id,
                vector=embedder.embed_text(candidate.claim),
                metadata={
                    "agent_id": agent_id,
                    "stream_id": stream_id,
                    "kind": "claim",
                    "status": "active",
                    "source_trust": candidate.trust,
                    "hours_stale": candidate.hours_stale,
                    "reinforcement": candidate.reinforcement,
                    "has_conflicts": candidate.has_conflicts,
                    "safety": candidate.safety,
                    "scenario": scenario.name,
                    "axis": scenario.axis,
                },
            )
            lineage.emit(
                event_type="observed",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=candidate.memory_id,
                payload={
                    "scenario": scenario.name,
                    "axis": scenario.axis,
                    "claim": candidate.claim,
                },
            )

        expected_a = _expected_score(scenario.a)
        expected_b = _expected_score(scenario.b)
        expected_winner = scenario.a.memory_id if expected_a >= expected_b else scenario.b.memory_id

        retrieval = recall.retrieve(
            agent_id=agent_id,
            stream_id=stream_id,
            query="What is the best-supported interpretation for this contradiction?",
            top_k=6,
        )

        accepted = retrieval.get("accepted", [])
        observed_winner = None
        if accepted:
            observed_winner = max(accepted, key=lambda row: float(row.get("score", 0.0))).get("memory_id")

        agreement = observed_winner == expected_winner if observed_winner else False
        row = {
            "scenario": scenario.name,
            "axis": scenario.axis,
            "expected_winner": expected_winner,
            "observed_winner": observed_winner,
            "agreement": agreement,
            "expected_score_a": expected_a,
            "expected_score_b": expected_b,
            "accepted_count": len(accepted),
            "rejected_count": len(retrieval.get("rejected", [])),
        }
        results.append(row)

        lineage.emit(
            event_type="snapshotted",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=f"e9-scenario-{scenario.name}",
            payload={
                "snapshot_type": "eligibility_contradiction_pressure",
                "snapshot_stage": "per_scenario",
                **row,
                **cfg.retrieval_policy.audit_fields(),
            },
        )

    agreement_rate = sum(1 for r in results if r["agreement"]) / max(1, len(results))
    threshold = cfg.retrieval_policy.eligibility_threshold

    summary = {
        "agreement_rate": agreement_rate,
        "scenario_count": len(results),
        "pass": agreement_rate >= 0.9,
        "eligibility_threshold": threshold,
        "results": results,
    }

    lineage.emit(
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="e9-summary",
        payload={
            "snapshot_type": "eligibility_contradiction_pressure",
            "snapshot_stage": "final",
            "agreement_rate": agreement_rate,
            "scenario_count": len(results),
            "pass": summary["pass"],
            **cfg.retrieval_policy.audit_fields(),
        },
    )

    print(summary)
    return summary


if __name__ == "__main__":
    run()
