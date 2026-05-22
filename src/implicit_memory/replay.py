from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256

from src.implicit_memory.cue_ingest import Cue, cue_from_ingested_event


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


class ReplayCueProvider:
    """Replays captured cues for deterministic loop replay.

    CONTROL_PLANE_INGEST Decision 3: a live bus is non-deterministic
    input; replay must not depend on it. This provider yields `Cue`
    objects decoded from recorded `control_cue_ingested` events — no
    bus, no queue, no wall clock. Feed it to `ImplicitControllerLoop`
    in place of a live or fixture provider; the loop re-emits the same
    lineage, and `rebuild_from_lineage` over that lineage yields the
    same signature.

    Note what `rebuild_from_lineage` is and is not: it is a *post-hoc
    signature function* over an emitted-event list, not the replay
    driver. The replay driver is the loop itself, re-run with this
    provider.

    `pull` ignores `now` by design — replay's inputs come entirely from
    the recorded events, never the clock.
    """

    def __init__(self, ingested_events: list[dict]) -> None:
        self._cues: list[Cue] = [
            cue_from_ingested_event(event)
            for event in ingested_events
            if event.get("event_type") == "control_cue_ingested"
        ]

    def pull(self, *, now=None) -> list[Cue]:
        return list(self._cues)
