from __future__ import annotations

from .contracts import ConflictLink, Event, MemoryState, stable_json_hash


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def reduce_events(events: list[Event]) -> dict[str, MemoryState]:
    state: dict[str, MemoryState] = {}
    for event in sorted(events, key=lambda e: (e.memory_id, e.sequence, e.event_id)):
        mem = state.get(event.memory_id)
        if event.event_type == "observed":
            claim = str(event.payload.get("claim", ""))
            trust = float(event.payload.get("trust_score", 0.5))
            confidence = float(event.payload.get("confidence", 0.5))
            mem = MemoryState(
                memory_id=event.memory_id,
                claim=claim,
                trust_score=_clamp(trust),
                confidence=_clamp(confidence),
                decay_score=float(event.payload.get("decay_score", 1.0)),
                last_recalled=None,
                access_count=0,
                status="active",
                source_event_id=event.event_id,
                source_payload_hash=stable_json_hash(event.payload),
                lineage_event_ids=[event.event_id],
                assertion_ts=event.timestamp,
            )
            state[event.memory_id] = mem
            continue

        if mem is None:
            # Ignore out-of-order references for v0.
            continue

        mem.lineage_event_ids.append(event.event_id)
        if event.event_type == "recalled":
            mem.access_count += 1
            mem.reinforcement_count += 1
            mem.last_recalled = event.timestamp
            mem.decay_score = _clamp(mem.decay_score + 0.05)
            continue
        if event.event_type == "mutated":
            if "claim" in event.payload:
                mem.claim = str(event.payload["claim"])
            if "confidence" in event.payload:
                mem.confidence = _clamp(float(event.payload["confidence"]))
            continue
        if event.event_type == "promoted":
            mem.claim = str(event.payload.get("claim", mem.claim))
            mem.confidence = _clamp(float(event.payload.get("confidence", mem.confidence)))
            continue
        if event.event_type == "quarantined":
            mem.status = "quarantined"
            mem.safety_score = 0.0
            continue
        if event.event_type == "deleted":
            mem.status = "deleted"
            mem.safety_score = 0.0
            continue
        if event.event_type == "contradicted":
            target = str(event.payload["target_memory_id"])
            mem.conflicts.append(
                ConflictLink(
                    target_memory_id=target,
                    relation="contradicts",
                    source_event_id=event.event_id,
                )
            )
            mem.confidence = _clamp(mem.confidence * 0.9)
            continue
        if event.event_type == "supported":
            target = str(event.payload["target_memory_id"])
            mem.supports.append(
                ConflictLink(
                    target_memory_id=target,
                    relation="supports",
                    source_event_id=event.event_id,
                )
            )
            mem.confidence = _clamp(mem.confidence + 0.05)
            continue
    return state
