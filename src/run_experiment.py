from __future__ import annotations

import argparse

from src.bootstrap import ensure_lineage_bootstrap
from src.config import load_config
from src.experiments.e1_trusted_false_vs_weak_true import run as run_e1
from src.experiments.e2_repeated_recall_drift import run as run_e2
from src.experiments.e3_time_reinforcement import run as run_e3
from src.experiments.e4_conflict_persistence import run as run_e4
from src.experiments.e5_sleep_promotion import run as run_e5
from src.experiments.e6_poisoning_before_promotion import run as run_e6
from src.experiments.e7_replay_rebuild import run as run_e7
from src.experiments.e8_vector_rebuild import run as run_e8
from src.storage import LineageStorage


EXPERIMENTS = {
    "e1": run_e1,
    "e2": run_e2,
    "e3": run_e3,
    "e4": run_e4,
    "e5": run_e5,
    "e6": run_e6,
    "e7": run_e7,
    "e8": run_e8,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name", choices=EXPERIMENTS.keys())
    args = parser.parse_args()

    cfg = load_config()
    ensure_lineage_bootstrap(LineageStorage(cfg))

    EXPERIMENTS[args.name]()
