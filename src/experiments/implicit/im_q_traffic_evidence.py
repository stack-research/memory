"""Traffic-backed evidence for the uncertainty gate-mode default decision.

Suite P decides the default gate mode (combined vs per_axis) from four engineered
stress cases (L, M, N, O). Those tests use hand-crafted inputs designed to make a
specific axis fail. They prove the math can distinguish axes; they do not prove
that real workload traffic produces decisions where the modes diverge.

Q closes that gap. It registers an observer on eligibility_gate, runs the
existing A-K regression workload, captures every gating call's inputs, recomputes
the decision under the alternate mode, and reports the decision flip rate. The
final default-mode policy event cites the measured flip rate rather than the
toy stress evidence.

This experiment does not alter regression behavior. The observer is read-only.
"""

from __future__ import annotations

from src.experiments.implicit.common import InMemoryLineageEngine, emit, summarize
from src.experiments.implicit.im_a_unprompted_trigger import run as run_a
from src.experiments.implicit.im_b_session_reset_timegap import run as run_b
from src.experiments.implicit.im_c_trusted_false_contamination import run as run_c
from src.experiments.implicit.im_d_reflex_boundary import run as run_d
from src.experiments.implicit.im_e_conflict_persistence import run as run_e
from src.experiments.implicit.im_f_replay_determinism import run as run_f
from src.experiments.implicit.im_g_event_flood import run as run_g
from src.experiments.implicit.im_h_procedure_lifecycle import run as run_h
from src.experiments.implicit.im_i_policy_mutation_lineage import run as run_i
from src.experiments.implicit.im_j_split_reality_integration import run as run_j
from src.experiments.implicit.im_k_scheduled_cues import run as run_k
from src.implicit_memory.eligibility import (
    EligibilityDecision,
    eligibility_gate,
    set_eligibility_observer,
)


def _alternate_mode(requested: str) -> str:
    return "per_axis" if requested == "combined" else "combined"


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-q"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    observations: list[dict] = []

    def observer(inputs: dict, decision: EligibilityDecision) -> None:
        alt_mode = _alternate_mode(decision.gate_mode)
        alt_kwargs = dict(inputs)
        alt_kwargs["gate_mode"] = alt_mode
        alt_decision = eligibility_gate(**alt_kwargs)
        observations.append(
            {
                "requested_mode": decision.gate_mode,
                "alt_mode": alt_mode,
                "requested_allow": decision.allow_influence,
                "alt_allow": alt_decision.allow_influence,
                "dominant_axis": decision.dominant_axis,
                "alt_dominant_axis": alt_decision.dominant_axis,
                "combined_score": decision.combined_score,
                "triple": {
                    "claim": decision.uncertainty_triple.confidence_in_claim,
                    "recall_process": decision.uncertainty_triple.confidence_in_recall_process,
                    "provenance_chain": decision.uncertainty_triple.confidence_in_provenance_chain,
                },
            }
        )

    set_eligibility_observer(observer)
    try:
        run_a()
        run_b()
        run_c()
        run_d()
        run_e()
        run_f()
        run_g()
        run_h()
        run_i()
        run_j()
        run_k()
    finally:
        set_eligibility_observer(None)

    total = len(observations)
    flips = sum(1 for o in observations if o["requested_allow"] != o["alt_allow"])
    flip_rate = (flips / total) if total else 0.0

    axis_counts: dict[str, int] = {"claim": 0, "recall_process": 0, "provenance_chain": 0}
    for o in observations:
        axis_counts[o["dominant_axis"]] = axis_counts.get(o["dominant_axis"], 0) + 1

    tied_axes_count = sum(
        1
        for o in observations
        if round(o["triple"]["claim"], 6)
        == round(o["triple"]["recall_process"], 6)
        == round(o["triple"]["provenance_chain"], 6)
    )
    tied_rate = (tied_axes_count / total) if total else 0.0

    # Honest decision rule:
    # 1. The sample must be large enough to back any decision. 5 calls is not a
    #    workload; it is a smoke test. Below the minimum, we explicitly refuse
    #    to back per_axis on this evidence and surface why.
    # 2. Above the minimum, if modes diverge meaningfully, per_axis adds signal.
    #    If they do not, per_axis is decoration.
    minimum_sample_size = 50
    sample_too_small = total < minimum_sample_size
    if sample_too_small:
        default_mode = "undecided"
        rationale = "traffic_sample_too_small_to_back_decision"
    elif flip_rate >= 0.05:
        default_mode = "per_axis"
        rationale = "traffic_flip_rate_supports_per_axis"
    else:
        default_mode = "combined"
        rationale = "traffic_flip_rate_too_low_to_back_per_axis"

    evidence = {
        "gate_calls_total": total,
        "minimum_sample_size": minimum_sample_size,
        "sample_too_small": sample_too_small,
        "flips": flips,
        "flip_rate": round(flip_rate, 6),
        "dominant_axis_counts": axis_counts,
        "tied_axes_count": tied_axes_count,
        "tied_axes_rate": round(tied_rate, 6),
    }

    emit(
        lineage,
        event_type="policy_threshold_updated",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="policy-uncertainty-gate-default-traffic",
        payload={
            "mutation_type": "uncertainty_gate_mode_default_decision_traffic_backed",
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
        memory_id="uncertainty-gate-mode-traffic-evidence",
        payload={
            "snapshot_type": "uncertainty_gate_default_mode_traffic_evidence",
            "default_mode": default_mode,
            "rationale": rationale,
            "evidence": evidence,
        },
    )

    # Q passes if it ran and emitted an honest verdict. An "undecided" outcome
    # is a successful Q run because Q is a measurement, not a stress test that
    # must be passable. The downstream consumer can read the rationale and
    # decide whether to enrich the regression workload or accept the gap.
    summary = {
        "suite": "Q",
        "default_mode": default_mode,
        "rationale": rationale,
        "evidence": evidence,
        "pass": total > 0,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
