from __future__ import annotations

import argparse

from src.experiments.e1_trusted_false_vs_weak_true import run as run_e1


EXPERIMENTS = {
    "e1": run_e1,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name", choices=EXPERIMENTS.keys())
    args = parser.parse_args()
    EXPERIMENTS[args.name]()
