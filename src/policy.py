from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RejectionReason(StrEnum):
    ELIGIBILITY_BELOW_THRESHOLD = "eligibility_below_threshold"
    CROSS_SCOPE_REFERENCE_ATTEMPT = "cross_scope_reference_attempt"
    URGENCY_SPOOF_SUSPECTED = "urgency_spoof_suspected"
    SENSORY_CONFIDENCE_SPOOF_SUSPECTED = "sensory_confidence_spoof_suspected"
    REFLEX_BUDGET_EXHAUSTED = "reflex_budget_exhausted"
    EVENT_FLOOD_SUSPECTED = "event_flood_suspected"


class QuarantineReason(StrEnum):
    HIGH_TRUST_LOW_SUPPORT_CONFLICT_CLUSTER = "high_trust_low_support_conflict_cluster"


class SuspicionTag(StrEnum):
    GOAL_HIJACK_SUSPECTED = "goal_hijack_suspected"
    CROSS_SCOPE_INFLUENCE_ATTEMPT = "cross_scope_influence_attempt"


class ThreatLabel(StrEnum):
    INFLUENCE_MANIPULATION = "influence_manipulation"
    SCOPE_ESCAPE_ATTEMPT = "scope_escape_attempt"


@dataclass(frozen=True)
class RetrievalPolicy:
    policy_id: str
    version: str
    effective_at: str
    eligibility_threshold: float
    quarantine_risk_threshold: float
    uncertainty_gate_mode: str = "combined"
    uncertainty_combined_threshold: float | None = None
    uncertainty_claim_threshold: float = 0.3
    uncertainty_recall_process_threshold: float = 0.3
    uncertainty_provenance_chain_threshold: float = 0.3
    uncertainty_safety_floor: float = 0.1
    implicit_admission_threshold: float = 0.45
    implicit_reflex_threshold: float = 0.75
    implicit_reflex_max_actions: int = 2
    implicit_reflex_cooldown_steps: int = 3
    implicit_event_flood_threshold: int = 5

    def audit_fields(self) -> dict[str, str]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.version,
            "policy_effective_at": self.effective_at,
        }


def build_policy_id(*, name: str, version: str, effective_at: str) -> str:
    return f"{name}:{version}:{effective_at}"
