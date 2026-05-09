from __future__ import annotations

from src.experiments.implicit.im_a_unprompted_trigger import run as run_a
from src.experiments.implicit.im_c_trusted_false_contamination import run as run_c
from src.experiments.implicit.im_d_reflex_boundary import run as run_d
from src.experiments.implicit.im_e_conflict_persistence import run as run_e
from src.experiments.implicit.im_f_replay_determinism import run as run_f


def run() -> dict:
    a = run_a()
    c = run_c()
    d = run_d()
    e = run_e()
    f = run_f()
    summary = {
        "implicit_regression": "PASSED" if a["pass"] and c["pass"] and d["pass"] and e["pass"] and f["pass"] else "FAILED",
        "a_pass": a["pass"],
        "c_pass": c["pass"],
        "d_pass": d["pass"],
        "e_pass": e["pass"],
        "f_pass": f["pass"],
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
