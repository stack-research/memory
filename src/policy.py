from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RejectionReason(StrEnum):
    ELIGIBILITY_BELOW_THRESHOLD = "eligibility_below_threshold"
    CROSS_SCOPE_REFERENCE_ATTEMPT = "cross_scope_reference_attempt"


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

    def audit_fields(self) -> dict[str, str]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.version,
            "policy_effective_at": self.effective_at,
        }


def build_policy_id(*, name: str, version: str, effective_at: str) -> str:
    return f"{name}:{version}:{effective_at}"
