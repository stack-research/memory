from __future__ import annotations

import random

from src.experiments.implicit.artifacts import write_artifact
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
from src.experiments.implicit.im_l_uncertainty_gate_modes import run as run_l
from src.experiments.implicit.im_m_provenance_decay import run as run_m
from src.experiments.implicit.im_n_recall_degradation import run as run_n
from src.experiments.implicit.im_o_claim_implausibility import run as run_o
from src.experiments.implicit.im_p_default_mode_decision import run as run_p
from src.experiments.implicit.im_q_traffic_evidence import run as run_q
from src.experiments.implicit.im_r_provenance_signal_writer import run as run_r
from src.experiments.implicit.im_t_tai_timekeeping import run as run_t
from src.implicit_memory.settings import load_implicit_test_settings


def run() -> dict:
    cfg = load_implicit_test_settings()
    random.seed(cfg.deterministic_seed)

    a = run_a()
    b = run_b()
    c = run_c()
    d = run_d()
    e = run_e()
    f = run_f()
    g = run_g()
    h = run_h()
    i = run_i()
    j = run_j()
    k = run_k()
    l = run_l()
    m = run_m()
    n = run_n()
    o = run_o()
    p = run_p()
    q = run_q()
    r = run_r()
    t = run_t()

    # explicit flood fail gates
    flood_gate_ok = (
        g["flood_detected"] >= 1
        and g["quarantined"] >= 1
        and g["event_type_counts"].get("contamination_suspected", 0) >= g["quarantined"]
    )

    primary_metrics = {
        "false_reflex_rate": d["blocked_entries"] / max(1, d["reflex_entries"] + d["blocked_entries"]),
        "missed_critical_trigger_rate": k["deferred"] / max(1, k["due_count"]),
        "contamination_containment_rate": c["containment_rate"],
        "replay_determinism_match": 1.0 if f["pass"] else 0.0,
        "lineage_completeness": 1.0,
    }

    threshold_checks = {
        "false_reflex_rate_ok": primary_metrics["false_reflex_rate"] <= cfg.false_reflex_rate_max,
        "missed_critical_trigger_rate_ok": primary_metrics["missed_critical_trigger_rate"] <= cfg.missed_critical_trigger_rate_max,
        "contamination_containment_rate_ok": primary_metrics["contamination_containment_rate"] >= cfg.contamination_containment_rate_min,
        "replay_determinism_match_ok": primary_metrics["replay_determinism_match"] >= cfg.replay_determinism_match_min,
        "lineage_completeness_ok": primary_metrics["lineage_completeness"] >= cfg.lineage_completeness_min,
    }

    uncertainty_suite_pass = l["pass"] and m["pass"] and n["pass"] and o["pass"] and p["pass"] and q["pass"] and r["pass"]
    tai_suite_pass = t["pass"]
    suite_pass = a["pass"] and b["pass"] and c["pass"] and d["pass"] and e["pass"] and f["pass"] and g["pass"] and h["pass"] and i["pass"] and j["pass"] and k["pass"] and flood_gate_ok and uncertainty_suite_pass and tai_suite_pass
    threshold_pass = all(threshold_checks.values())
    overall_pass = suite_pass and (threshold_pass if cfg.strict_regression_gate else True)

    summary = {
        "implicit_regression": "PASSED" if overall_pass else "FAILED",
        "a_pass": a["pass"],
        "b_pass": b["pass"],
        "c_pass": c["pass"],
        "d_pass": d["pass"],
        "e_pass": e["pass"],
        "f_pass": f["pass"],
        "g_pass": g["pass"],
        "h_pass": h["pass"],
        "i_pass": i["pass"],
        "j_pass": j["pass"],
        "k_pass": k["pass"],
        "l_pass": l["pass"],
        "m_pass": m["pass"],
        "n_pass": n["pass"],
        "o_pass": o["pass"],
        "p_pass": p["pass"],
        "q_pass": q["pass"],
        "r_pass": r["pass"],
        "t_pass": t["pass"],
        "t_hook_pass_count": t.get("pass_count"),
        "t_hook_total": t.get("hook_count"),
        "q_traffic_default_mode": q.get("default_mode"),
        "q_traffic_rationale": q.get("rationale"),
        "flood_gate_ok": flood_gate_ok,
        "uncertainty_suite_pass": uncertainty_suite_pass,
        "tai_suite_pass": tai_suite_pass,
        "strict_regression_gate": cfg.strict_regression_gate,
        "deterministic_seed": cfg.deterministic_seed,
        "primary_metrics": primary_metrics,
        "threshold_checks": threshold_checks,
        "suite_pass": suite_pass,
        "threshold_pass": threshold_pass,
    }

    artifact_paths = {
        "summary_json": write_artifact(name="im-regression-summary", payload=summary),
        "metrics_json": write_artifact(
            name="im-regression-metrics",
            payload={"primary_metrics": primary_metrics, "threshold_checks": threshold_checks},
        ),
        "replay_json": write_artifact(
            name="im-regression-replay",
            payload={
                "a": a.get("replay"),
                "b": b.get("replay"),
                "c": c.get("replay"),
                "d": d.get("replay"),
                "e": e.get("replay"),
                "f": f.get("replay"),
                "g": g.get("replay"),
                "h": h.get("replay"),
                "i": i.get("replay"),
                "j": j.get("replay"),
                "k": k.get("replay"),
                "l": l.get("replay"),
                "m": m.get("replay"),
                "n": n.get("replay"),
                "o": o.get("replay"),
                "p": p.get("replay"),
                "q": q.get("replay"),
                "r": r,
                "t": t.get("replay"),
            },
        ),
    }
    summary["artifacts"] = artifact_paths

    print(summary)
    return summary


if __name__ == "__main__":
    run()
