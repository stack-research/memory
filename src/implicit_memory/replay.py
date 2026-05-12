from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256


_DECISION_KEYS = (
    "uncertainty_triple",
    "combined_score",
    "dominant_axis",
    "eligibility_score",
    "reason",
    "uncertainty_gate_mode",
    "provenance_signals",
    "policy_id",
    "policy_version",
    "snapshot_type",
    "mutation_type",
    "target",
    "old_value",
    "new_value",
    "allow_influence",
)


def _decision_record(event: dict) -> dict:
    payload = event.get("payload") or {}
    decision_payload = {k: payload[k] for k in _DECISION_KEYS if k in payload}
    return {
        "event_type": event.get("event_type", "unknown"),
        "decision_payload": decision_payload,
    }


def rebuild_from_lineage(events: list[dict]) -> dict:
    counts = Counter(event.get("event_type", "unknown") for event in events)
    decision_records = [_decision_record(event) for event in events]
    serialized = json.dumps(
        decision_records,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    signature = sha256(serialized.encode("utf-8")).hexdigest()
    return {
        "event_count": len(events),
        "event_type_counts": dict(counts),
        "decision_signature": signature,
    }
