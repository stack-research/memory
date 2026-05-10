from __future__ import annotations

import itertools
import os
from typing import Any

from src.experiments.implicit.artifacts import write_artifact
from src.experiments.implicit.im_regression import run as run_regression


MATRIX = {
    "IMPLICIT_TRUST_PROFILE": ["low", "medium", "high"],
    "IMPLICIT_CONFLICT_PRESSURE": ["none", "moderate", "high"],
    "IMPLICIT_URGENCY_PROFILE": ["stable", "spiky", "sustained"],
    "IMPLICIT_TIME_GAP": ["none", "short", "long"],
    "IMPLICIT_REINFORCEMENT_PATTERN": ["sparse", "bursty", "steady"],
}


def run() -> dict[str, Any]:
    keys = list(MATRIX.keys())
    values = [MATRIX[k] for k in keys]

    max_runs = int(os.environ.get("IMPLICIT_MATRIX_MAX_RUNS", "9"))
    rows: list[dict[str, Any]] = []

    for idx, combo in enumerate(itertools.product(*values)):
        if idx >= max_runs:
            break

        profile = dict(zip(keys, combo, strict=False))
        old_env = {k: os.environ.get(k) for k in keys}
        os.environ.update(profile)
        try:
            result = run_regression()
        finally:
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        rows.append({
            "profile": profile,
            "pass": result.get("implicit_regression") == "PASSED",
            "suite_pass": result.get("suite_pass"),
            "threshold_pass": result.get("threshold_pass"),
        })

    summary = {
        "runs": len(rows),
        "passes": sum(1 for r in rows if r["pass"]),
        "rows": rows,
    }
    summary["artifact"] = write_artifact(name="im-matrix-summary", payload=summary)
    print(summary)
    return summary


if __name__ == "__main__":
    run()
