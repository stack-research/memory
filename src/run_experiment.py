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
from src.experiments.e9_eligibility_contradiction_pressure import run as run_e9
from src.experiments.e10_reconsolidation_stability import run as run_e10
from src.experiments.e11_promotion_forgetting_coupling import run as run_e11
from src.experiments.e12_trusted_source_poison_resilience import run as run_e12
from src.experiments.implicit.im_a_unprompted_trigger import run as run_im_a
from src.experiments.implicit.im_b_session_reset_timegap import run as run_im_b
from src.experiments.implicit.im_c_trusted_false_contamination import run as run_im_c
from src.experiments.implicit.im_d_reflex_boundary import run as run_im_d
from src.experiments.implicit.im_e_conflict_persistence import run as run_im_e
from src.experiments.implicit.im_f_replay_determinism import run as run_im_f
from src.experiments.implicit.im_g_event_flood import run as run_im_g
from src.experiments.implicit.im_aws_lineage_replay import run as run_im_aws
from src.experiments.implicit.im_h_procedure_lifecycle import run as run_im_h
from src.experiments.implicit.im_i_policy_mutation_lineage import run as run_im_i
from src.experiments.implicit.im_j_split_reality_integration import run as run_im_j
from src.experiments.implicit.im_k_scheduled_cues import run as run_im_k
from src.experiments.implicit.im_l_uncertainty_gate_modes import run as run_im_l
from src.experiments.implicit.im_m_provenance_decay import run as run_im_m
from src.experiments.implicit.im_n_recall_degradation import run as run_im_n
from src.experiments.implicit.im_o_claim_implausibility import run as run_im_o
from src.experiments.implicit.im_p_default_mode_decision import run as run_im_p
from src.experiments.implicit.im_q_traffic_evidence import run as run_im_q
from src.experiments.implicit.im_r_provenance_signal_writer import run as run_im_r
from src.experiments.implicit.im_s_provenance_writer_closeout import run as run_im_s
from src.experiments.implicit.im_regression import run as run_im_regression
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
    "e9": run_e9,
    "e10": run_e10,
    "e11": run_e11,
    "e12": run_e12,
    "im-a": run_im_a,
    "im-b": run_im_b,
    "im-c": run_im_c,
    "im-d": run_im_d,
    "im-e": run_im_e,
    "im-f": run_im_f,
    "im-g": run_im_g,
    "im-aws": run_im_aws,
    "im-h": run_im_h,
    "im-i": run_im_i,
    "im-j": run_im_j,
    "im-k": run_im_k,
    "im-l": run_im_l,
    "im-m": run_im_m,
    "im-n": run_im_n,
    "im-o": run_im_o,
    "im-p": run_im_p,
    "im-q": run_im_q,
    "im-r": run_im_r,
    "im-s": run_im_s,
    "im-regression": run_im_regression,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name", choices=EXPERIMENTS.keys())
    args = parser.parse_args()

    cfg = load_config()
    ensure_lineage_bootstrap(LineageStorage(cfg))

    EXPERIMENTS[args.name]()
