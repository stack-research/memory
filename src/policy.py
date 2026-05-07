from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RejectionReason(StrEnum):
    ELIGIBILITY_BELOW_THRESHOLD = "eligibility_below_threshold"


class QuarantineReason(StrEnum):
    HIGH_TRUST_LOW_SUPPORT_CONFLICT_CLUSTER = "high_trust_low_support_conflict_cluster"


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
