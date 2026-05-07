from __future__ import annotations

import os
import sys

from src.experiments.e7_replay_rebuild import run as run_e7
from src.experiments.e8_vector_rebuild import run as run_e8


def _fail(msg: str) -> None:
    print({"lab_regression": "FAILED", "reason": msg})
    raise SystemExit(1)


def main() -> None:
    run_id = os.environ.get("MEMORY_LAB_REPLAY_RUN_ID", "phase5-regression")
    os.environ["MEMORY_LAB_REPLAY_RUN_ID"] = run_id

    first = run_e7()
    if not first["replay_equal"]:
        _fail("E7 replay_equal is false on first run")

    second = run_e7()
    if not second["replay_equal"]:
        _fail("E7 replay_equal is false on second run")

    if first["state_signature"] != second["state_signature"]:
        _fail("E7 state signature changed across same run_id replay")

    e8 = run_e8()
    if not e8["equivalent_within_tolerance"]:
        _fail("E8 equivalence check failed")

    print(
        {
            "lab_regression": "PASSED",
            "run_id": run_id,
            "e7_state_signature": second["state_signature"],
            "e8_ranking_signature": e8["ranking_signature"],
            "e8_top3_overlap": e8["top3_overlap"],
            "e8_tolerance": e8["tolerance"],
        }
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover
        print({"lab_regression": "FAILED", "error": str(exc)})
        sys.exit(1)
