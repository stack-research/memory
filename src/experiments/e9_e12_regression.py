from __future__ import annotations

import sys

from src.experiments.e10_reconsolidation_stability import run as run_e10
from src.experiments.e11_promotion_forgetting_coupling import run as run_e11
from src.experiments.e12_trusted_source_poison_resilience import run as run_e12
from src.experiments.e9_eligibility_contradiction_pressure import run as run_e9


def _fail(msg: str) -> None:
    print({"e9_e12_regression": "FAILED", "reason": msg})
    raise SystemExit(1)


def _require_keys(payload: dict, *, keys: list[str], label: str) -> None:
    missing = [k for k in keys if k not in payload]
    if missing:
        _fail(f"{label} missing required keys: {', '.join(missing)}")


def main() -> None:
    e9 = run_e9()
    _require_keys(
        e9,
        keys=["agreement_rate", "scenario_count", "pass", "results"],
        label="e9",
    )
    if not (0.0 <= float(e9["agreement_rate"]) <= 1.0):
        _fail("e9 agreement_rate out of range")
    if int(e9["scenario_count"]) <= 0:
        _fail("e9 scenario_count must be > 0")

    e10 = run_e10()
    _require_keys(
        e10,
        keys=["steps", "median_cosine_to_previous", "final_cosine_to_base", "pass"],
        label="e10",
    )
    if int(e10["steps"]) <= 0:
        _fail("e10 steps must be > 0")
    if not (0.0 <= float(e10["median_cosine_to_previous"]) <= 1.0):
        _fail("e10 median_cosine_to_previous out of range")
    if not (0.0 <= float(e10["final_cosine_to_base"]) <= 1.0):
        _fail("e10 final_cosine_to_base out of range")

    e11 = run_e11()
    _require_keys(
        e11,
        keys=["promotion_precision", "episodic_drop_ratio", "semantic_gain", "pass"],
        label="e11",
    )
    if not (0.0 <= float(e11["promotion_precision"]) <= 1.0):
        _fail("e11 promotion_precision out of range")

    e12 = run_e12()
    _require_keys(
        e12,
        keys=["scenario_count", "poison_promotion_rate", "label_coverage_rate", "pass"],
        label="e12",
    )
    if int(e12["scenario_count"]) <= 0:
        _fail("e12 scenario_count must be > 0")
    if not (0.0 <= float(e12["poison_promotion_rate"]) <= 1.0):
        _fail("e12 poison_promotion_rate out of range")
    if not (0.0 <= float(e12["label_coverage_rate"]) <= 1.0):
        _fail("e12 label_coverage_rate out of range")

    print(
        {
            "e9_e12_regression": "PASSED",
            "e9_pass": e9["pass"],
            "e10_pass": e10["pass"],
            "e11_pass": e11["pass"],
            "e12_pass": e12["pass"],
        }
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover
        print({"e9_e12_regression": "FAILED", "error": str(exc)})
        sys.exit(1)
