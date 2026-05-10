from __future__ import annotations

from enum import StrEnum


class ImplicitReason(StrEnum):
    ELIGIBLE = "eligible"
    ELIGIBILITY_BELOW_THRESHOLD = "eligibility_below_threshold"
    SPLIT_REALITY_DETECTED = "split_reality_detected"
    LOW_SIGNIFICANCE = "low_significance"
    REFLEX_BUDGET_EXHAUSTED = "reflex_budget_exhausted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CYCLE_COMPLETE = "cycle_complete"
    DEFERRED = "deferred"
    NOT_REFLEX = "not_reflex"
    NOT_DUE = "not_due"
    PROLONGED_HIGH_URGENCY_TRUST_DECAY = "prolonged_high_urgency_trust_decay"
    SCHEDULED_PRIORITY = "scheduled_priority"
    SCHEDULED_LOW_PRIORITY = "scheduled_low_priority"
    EVENT_FLOOD_SUSPECTED = "event_flood_suspected"
    URGENCY_SPOOF_SUSPECTED = "urgency_spoof_suspected"
    SENSORY_CONFIDENCE_SPOOF_SUSPECTED = "sensory_confidence_spoof_suspected"
    CONTAMINATION_RISK_THRESHOLD = "contamination_risk_threshold"
    HIGH_TRUST_LOW_SUPPORT_CONFLICT_CLUSTER = "high_trust_low_support_conflict_cluster"
    INVALID_POLICY_MUTATION = "invalid_policy_mutation"
    IDLE_DECAY = "idle_decay"


__all__ = ["ImplicitReason"]
