from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_CLAIM_FIELDS = {
    "claim_id",
    "claim_text",
    "source_id",
    "source_trust_prior",
    "event_time",
    "context_tags",
    "risk_signal",
}


@dataclass(frozen=True)
class ClaimTemplate:
    claim_id: str
    claim_text: str
    source_id: str
    source_trust_prior: float
    event_time: str
    context_tags: list[str]
    risk_signal: float
    expected_conflicts: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "source_id": self.source_id,
            "source_trust_prior": self.source_trust_prior,
            "event_time": self.event_time,
            "context_tags": self.context_tags,
            "risk_signal": self.risk_signal,
        }
        if self.expected_conflicts is not None:
            out["expected_conflicts"] = self.expected_conflicts
        return out


def validate_claim_template(row: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_CLAIM_FIELDS - set(row.keys()))
    if missing:
        raise ValueError(f"Missing required claim template fields: {', '.join(missing)}")
    if not isinstance(row.get("context_tags"), list):
        raise ValueError("claim template field 'context_tags' must be a list")
