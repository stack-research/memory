from __future__ import annotations

from datetime import datetime, timezone

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.experiments.implicit.templates import validate_claim_template
from src.implicit_memory.contamination import contamination_risk
from src.implicit_memory.reasons import ImplicitReason
from src.implicit_memory.settings import load_implicit_test_settings


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-c"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    cfg = load_implicit_test_settings()

    now_iso = datetime.now(timezone.utc).isoformat()
    scenarios = [
        {
            "memory_id": "c1",
            "source_trust": 0.95,
            "support": 0.2,
            "conflict": 0.9,
            "anomaly": 0.7,
            "claim_id": "c1",
            "claim_text": "Trusted source claim with weak support and high conflict.",
            "source_id": "c-source-1",
            "source_trust_prior": 0.95,
            "event_time": now_iso,
            "context_tags": ["suite-c", "contamination"],
            "risk_signal": 0.9,
        },
        {
            "memory_id": "c2",
            "source_trust": 0.60,
            "support": 0.8,
            "conflict": 0.2,
            "anomaly": 0.1,
            "claim_id": "c2",
            "claim_text": "Medium-trust source claim with strong support.",
            "source_id": "c-source-2",
            "source_trust_prior": 0.60,
            "event_time": now_iso,
            "context_tags": ["suite-c", "control"],
            "risk_signal": 0.2,
        },
        {
            "memory_id": "c3",
            "source_trust": 0.90,
            "support": 0.1,
            "conflict": 0.8,
            "anomaly": 0.8,
            "claim_id": "c3",
            "claim_text": "High-trust source claim with anomaly and conflict.",
            "source_id": "c-source-3",
            "source_trust_prior": 0.90,
            "event_time": now_iso,
            "context_tags": ["suite-c", "contamination"],
            "risk_signal": 0.85,
        },
    ]

    quarantined = 0
    promoted = 0
    for s in scenarios:
        validate_claim_template(s)
        risk = contamination_risk(
            source_trust=s["source_trust"],
            cross_source_support=s["support"],
            conflict_pressure=s["conflict"],
            anomaly_signal=s["anomaly"],
        )
        emit(
            lineage,
            event_type="contamination_suspected",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=s["memory_id"],
            payload={"risk": risk, **s},
        )
        if risk >= cfg.contamination_threshold:
            quarantined += 1
            emit(
                lineage,
                event_type="implicit_rejected",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=s["memory_id"],
                payload={
                    "reason": ImplicitReason.CONTAMINATION_RISK_THRESHOLD.value,
                    "risk": risk,
                    "eligibility_score": 0.0,
                    "uncertainty_triple": {
                        "confidence_in_claim": 0.0,
                        "confidence_in_recall_process": 0.0,
                        "confidence_in_provenance_chain": 0.0,
                    },
                    "combined_score": 0.0,
                    "dominant_axis": "claim",
                },
            )
        else:
            promoted += 1
            emit(
                lineage,
                event_type="implicit_admitted",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=s["memory_id"],
                payload={
                    "risk": risk,
                    "eligibility_score": 1.0,
                    "uncertainty_triple": {
                        "confidence_in_claim": 1.0,
                        "confidence_in_recall_process": 1.0,
                        "confidence_in_provenance_chain": 1.0,
                    },
                    "combined_score": 1.0,
                    "dominant_axis": "claim",
                },
            )

    containment_rate = quarantined / max(1, len(scenarios))
    summary = {
        "suite": "C",
        "scenario_count": len(scenarios),
        "quarantined": quarantined,
        "promoted": promoted,
        "containment_rate": containment_rate,
        "pass": quarantined >= 2,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
