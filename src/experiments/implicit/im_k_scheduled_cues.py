from __future__ import annotations

from datetime import timedelta

from src.experiments.implicit.common import InMemoryLineageEngine, summarize
from src.implicit_memory.reasons import ImplicitReason
from src.implicit_memory.scheduler import ScheduledCue, due_cues, escalation_level, now_utc


def run() -> dict:
    agent_id = "lab-agent-1"
    stream_id = "im-k"
    events: list[dict] = []
    lineage = InMemoryLineageEngine(events=events)

    t0 = now_utc()
    cues = [
        ScheduledCue(cue_id="cue-1", memory_id="meds-am", due_at=t0 - timedelta(seconds=30), urgency=0.7, risk_signal=0.8),
        ScheduledCue(cue_id="cue-2", memory_id="meds-pm", due_at=t0 - timedelta(seconds=200), urgency=0.75, risk_signal=0.85),
        ScheduledCue(cue_id="cue-3", memory_id="safety-check", due_at=t0 - timedelta(seconds=900), urgency=0.9, risk_signal=0.95),
        ScheduledCue(cue_id="cue-4", memory_id="low-priority-note", due_at=t0 + timedelta(seconds=120), urgency=0.2, risk_signal=0.2),
    ]

    due = due_cues(now=t0, cues=cues)

    prompted = 0
    admitted = 0
    deferred = 0

    for cue in due:
        overdue_seconds = max(0.0, (t0 - cue.due_at).total_seconds())
        level = escalation_level(overdue_seconds=overdue_seconds)

        lineage.emit(
            event_type="implicit_trigger_evaluated",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=cue.memory_id,
            actor_class="implicit_memory_controller",
            source_class="scheduler",
            payload={
                "trigger": "scheduled_cue",
                "cue_id": cue.cue_id,
                "overdue_seconds": overdue_seconds,
                "escalation_level": level,
                "urgency": cue.urgency,
                "risk_signal": cue.risk_signal,
            },
        )

        prompted += 1
        lineage.emit(
            event_type="implicit_trigger_fired",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=cue.memory_id,
            actor_class="implicit_memory_controller",
            source_class="scheduler",
            payload={
                "action": "invoke_recall",
                "cue_id": cue.cue_id,
                "escalation_level": level,
            },
        )

        # State-aware prompting equivalent: high urgency/risk auto-admit for influence, else defer.
        if cue.urgency * cue.risk_signal >= 0.5:
            admitted += 1
            lineage.emit(
                event_type="implicit_admitted",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=cue.memory_id,
                actor_class="implicit_memory_controller",
                source_class="scheduler",
                payload={"reason": ImplicitReason.SCHEDULED_PRIORITY.value, "cue_id": cue.cue_id, "escalation_level": level},
            )
        else:
            deferred += 1
            lineage.emit(
                event_type="implicit_trigger_deferred",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=cue.memory_id,
                actor_class="implicit_memory_controller",
                source_class="scheduler",
                payload={"reason": ImplicitReason.SCHEDULED_LOW_PRIORITY.value, "cue_id": cue.cue_id},
            )

    # not-due cue should be no-op
    not_due = [c for c in cues if c not in due]
    for cue in not_due:
        lineage.emit(
            event_type="implicit_no_op",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=cue.memory_id,
            actor_class="implicit_memory_controller",
            source_class="scheduler",
            payload={"reason": ImplicitReason.NOT_DUE.value, "cue_id": cue.cue_id},
        )

    critical_count = sum(
        1
        for e in events
        if e.get("event_type") == "implicit_trigger_evaluated"
        and e.get("payload", {}).get("escalation_level") == "critical"
    )

    summary = {
        "suite": "K",
        "due_count": len(due),
        "prompted": prompted,
        "admitted": admitted,
        "deferred": deferred,
        "critical_count": critical_count,
        "pass": len(due) >= 3 and prompted == len(due) and admitted >= 2 and critical_count >= 1,
        "replay": summarize(events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
