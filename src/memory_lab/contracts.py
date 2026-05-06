from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

SCHEMA_VERSION = "v1"
EVENT_TYPES = {
    "observed",
    "recalled",
    "mutated",
    "promoted",
    "quarantined",
    "deleted",
    "contradicted",
    "supported",
    "compacted",
}
STATE_STATUSES = {"active", "quarantined", "deleted"}


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def stable_json_hash(payload: Any) -> str:
    import json

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(slots=True)
class Event:
    event_id: str
    sequence: int
    event_type: str
    memory_id: str
    payload: dict[str, Any]
    source: str
    timestamp: str
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema version: {self.schema_version}")
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported event type: {self.event_type}")
        if self.sequence < 0:
            raise ValueError("sequence must be >= 0")
        if not self.event_id or not self.memory_id:
            raise ValueError("event_id and memory_id are required")


@dataclass(slots=True)
class ConflictLink:
    target_memory_id: str
    relation: str
    source_event_id: str


@dataclass(slots=True)
class MemoryState:
    memory_id: str
    claim: str
    trust_score: float
    confidence: float
    decay_score: float
    last_recalled: str | None
    access_count: int
    status: str = "active"
    source_event_id: str | None = None
    source_payload_hash: str | None = None
    lineage_event_ids: list[str] = field(default_factory=list)
    conflicts: list[ConflictLink] = field(default_factory=list)
    supports: list[ConflictLink] = field(default_factory=list)
    reinforcement_count: int = 0
    safety_score: float = 1.0
    assertion_ts: str = field(default_factory=utc_now_iso)

    def validate(self) -> None:
        if self.status not in STATE_STATUSES:
            raise ValueError(f"invalid status: {self.status}")
        for name, score in (
            ("trust_score", self.trust_score),
            ("confidence", self.confidence),
            ("decay_score", self.decay_score),
            ("safety_score", self.safety_score),
        ):
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"{name} must be in [0,1]")
        if self.access_count < 0 or self.reinforcement_count < 0:
            raise ValueError("counts must be >= 0")
        if not (self.source_event_id or self.source_payload_hash):
            raise ValueError("state must point to source_event_id or source_payload_hash")


@dataclass(slots=True)
class VectorRecord:
    memory_id: str
    embedding: list[float]
    claim_hash: str
    source_event_id: str | None
    source_payload_hash: str | None
    agent_id: str
    status: str
    kind: str
    source_trust: float
    confidence: float
    decay_score: float
    last_recalled_ts: str | None
    assertion_ts: str
    has_conflicts: bool
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema version: {self.schema_version}")
        if self.status not in STATE_STATUSES:
            raise ValueError(f"invalid vector status: {self.status}")
        if not (self.source_event_id or self.source_payload_hash):
            raise ValueError("vector must point to source_event_id or source_payload_hash")
        if not self.embedding:
            raise ValueError("embedding cannot be empty")
