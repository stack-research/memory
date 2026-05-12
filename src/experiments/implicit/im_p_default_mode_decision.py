from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.experiments.implicit.im_l_uncertainty_gate_modes import run as run_l
from src.experiments.implicit.im_m_provenance_decay import run as run_m
from src.experiments.implicit.im_n_recall_degradation import run as run_n
from src.experiments.implicit.im_o_claim_implausibility import run as run_o


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-p"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    l = run_l()
    m = run_m()
    n = run_n()
    o = run_o()

    evidence = {
        "mode_divergence_detected": l.get("divergence_count", 0) >= 1,
        "provenance_decay_axis_guard": bool(m.get("pass", False)),
        "recall_degradation_axis_guard": bool(n.get("pass", False)),
        "claim_implausibility_axis_guard": bool(o.get("pass", False)),
    }
    per_axis_strength = sum(1 for v in evidence.values() if v)

    default_mode = "per_axis" if per_axis_strength >= 3 else "combined"
    rationale = (
        "axis_stress_supports_per_axis"
        if default_mode == "per_axis"
        else "insufficient_axis_stress_support_for_per_axis"
    )

    emit(
        lineage,
        event_type="policy_threshold_updated",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="policy-uncertainty-gate-default",
        payload={
            "mutation_type": "uncertainty_gate_mode_default_decision",
            "target": "uncertainty_gate_mode",
            "old_value": "combined",
            "new_value": default_mode,
            "reason": rationale,
            "evidence": evidence,
        },
    )

    emit(
        lineage,
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="uncertainty-gate-mode-decision-summary",
        payload={
            "snapshot_type": "uncertainty_gate_default_mode_decision",
            "default_mode": default_mode,
            "rationale": rationale,
            "evidence": evidence,
            "source_suites": {
                "L": l,
                "M": m,
                "N": n,
                "O": o,
            },
        },
    )

    summary = {
        "suite": "P",
        "default_mode": default_mode,
        "rationale": rationale,
        "evidence": evidence,
        "pass": default_mode in {"combined", "per_axis"},
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
