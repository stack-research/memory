from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.implicit_memory.policy_mutation import PolicyState, supersede_procedure, update_threshold


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-i"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    state = PolicyState(
        threshold_map={
            "eligibility_threshold": 0.30,
            "contamination_threshold": 0.60,
            "reflex_threshold": 0.75,
        },
        procedure_map={"reflex_slot": "proc-reflex-v1"},
    )

    threshold_updates = 0
    procedure_supersessions = 0
    invalid_rejections = 0

    # Valid threshold mutation
    state, payload = update_threshold(
        state,
        name="eligibility_threshold",
        new_value=0.35,
        reason="post_attack_hardening",
    )
    threshold_updates += 1
    emit(
        lineage,
        event_type="policy_threshold_updated",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="policy-eligibility-threshold",
        payload=payload,
    )

    # Valid procedure supersession
    state, payload = supersede_procedure(
        state,
        slot="reflex_slot",
        new_procedure_id="proc-reflex-v2",
        reason="spoof_resilience_upgrade",
    )
    procedure_supersessions += 1
    emit(
        lineage,
        event_type="policy_procedure_superseded",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="policy-reflex-slot",
        payload=payload,
    )

    # Invalid mutation should be rejected and logged
    try:
        update_threshold(
            state,
            name="contamination_threshold",
            new_value=1.5,
            reason="invalid_out_of_range",
        )
    except ValueError as exc:
        invalid_rejections += 1
        emit(
            lineage,
            event_type="implicit_rejected",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id="policy-contamination-threshold",
            payload={"reason": "invalid_policy_mutation", "error": str(exc)},
        )

    # replay policy state reconstruction from lineage payloads
    replay_threshold = 0.30
    replay_proc = "proc-reflex-v1"
    for evt in events:
        et = evt.get("event_type")
        p = evt.get("payload", {})
        if et == "policy_threshold_updated" and p.get("target") == "eligibility_threshold":
            replay_threshold = float(p.get("new_value"))
        if et == "policy_procedure_superseded" and p.get("slot") == "reflex_slot":
            replay_proc = str(p.get("new_procedure_id"))

    replay_ok = replay_threshold == state.threshold_map["eligibility_threshold"] and replay_proc == state.procedure_map["reflex_slot"]

    summary = {
        "suite": "I",
        "threshold_updates": threshold_updates,
        "procedure_supersessions": procedure_supersessions,
        "invalid_rejections": invalid_rejections,
        "eligibility_threshold_final": state.threshold_map["eligibility_threshold"],
        "reflex_procedure_final": state.procedure_map["reflex_slot"],
        "replay_ok": replay_ok,
        "pass": threshold_updates >= 1 and procedure_supersessions >= 1 and invalid_rejections >= 1 and replay_ok,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
