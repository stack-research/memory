from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class ScheduledCue:
    cue_id: str
    memory_id: str
    due_at: datetime
    urgency: float
    risk_signal: float
    acknowledged: bool = False


def due_cues(*, now: datetime, cues: list[ScheduledCue], grace_seconds: int = 0) -> list[ScheduledCue]:
    out: list[ScheduledCue] = []
    for cue in cues:
        if cue.acknowledged:
            continue
        if now + timedelta(seconds=grace_seconds) >= cue.due_at:
            out.append(cue)
    return out


def escalation_level(*, overdue_seconds: float) -> str:
    if overdue_seconds < 60:
        return "haptic"
    if overdue_seconds < 300:
        return "audio"
    return "critical"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
