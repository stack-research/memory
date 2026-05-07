from __future__ import annotations

import argparse

from src.experiments.e1_trusted_false_vs_weak_true import run as run_e1
from src.experiments.e2_repeated_recall_drift import run as run_e2
from src.experiments.e3_time_reinforcement import run as run_e3
from src.experiments.e4_conflict_persistence import run as run_e4


EXPERIMENTS = {
    "e1": run_e1,
    "e2": run_e2,
    "e3": run_e3,
    "e4": run_e4,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name", choices=EXPERIMENTS.keys())
    args = parser.parse_args()
    EXPERIMENTS[args.name]()
