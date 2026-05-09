from __future__ import annotations

from src.experiments.implicit.im_a_unprompted_trigger import run as run_a
from src.experiments.implicit.im_c_trusted_false_contamination import run as run_c
from src.experiments.implicit.im_d_reflex_boundary import run as run_d
from src.experiments.implicit.im_e_conflict_persistence import run as run_e
from src.experiments.implicit.im_f_replay_determinism import run as run_f
from src.experiments.implicit.im_g_event_flood import run as run_g


def run() -> dict:
    a = run_a()
    c = run_c()
    d = run_d()
    e = run_e()
    f = run_f()
    g = run_g()

    # explicit flood fail gates
    flood_gate_ok = (
        g["flood_detected"] >= 1
        and g["quarantined"] >= 1
        and g["event_type_counts"].get("contamination_suspected", 0) >= g["quarantined"]
    )

    summary = {
        "implicit_regression": "PASSED" if a["pass"] and c["pass"] and d["pass"] and e["pass"] and f["pass"] and g["pass"] and flood_gate_ok else "FAILED",
        "a_pass": a["pass"],
        "c_pass": c["pass"],
        "d_pass": d["pass"],
        "e_pass": e["pass"],
        "f_pass": f["pass"],
        "g_pass": g["pass"],
        "flood_gate_ok": flood_gate_ok,
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
