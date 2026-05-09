from __future__ import annotations

from collections import Counter
from hashlib import sha256


def rebuild_from_lineage(events: list[dict]) -> dict:
    counts = Counter(event.get("event_type", "unknown") for event in events)
    ordered_ids = [str(event.get("event_id", "")) for event in events]
    signature = sha256("|".join(ordered_ids).encode("utf-8")).hexdigest()
    return {
        "event_count": len(events),
        "event_type_counts": dict(counts),
        "decision_signature": signature,
    }
