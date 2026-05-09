from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.config import AwsConfig
from src.implicit_memory.controller import ObservationSignals, process_observation
from src.implicit_memory.scheduler import ScheduledCue, due_cues, escalation_level, now_utc


class ObservationProvider(Protocol):
    def pull(self, *, now: datetime) -> list[tuple[str, ObservationSignals]]: ...


class ScheduledCueProvider(Protocol):
    def pull(self, *, now: datetime) -> list[ScheduledCue]: ...


class LineageEmitter(Protocol):
    def emit(
        self,
        *,
        event_type: str,
        agent_id: str,
        stream_id: str,
        memory_id: str,
        payload: dict,
        actor_class: str = "implicit_memory_controller",
        source_class: str = "internal_engine",
        parent_event_id: str | None = None,
    ): ...


@dataclass
class LoopStats:
    observations_processed: int = 0
    observation_fired: int = 0
    observation_deferred: int = 0
    cues_due: int = 0
    cues_fired: int = 0
    cues_admitted: int = 0
    cues_deferred: int = 0

    def to_dict(self) -> dict:
        return {
            "observations_processed": self.observations_processed,
            "observation_fired": self.observation_fired,
            "observation_deferred": self.observation_deferred,
            "cues_due": self.cues_due,
            "cues_fired": self.cues_fired,
            "cues_admitted": self.cues_admitted,
            "cues_deferred": self.cues_deferred,
        }


class ImplicitControllerLoop:
    def __init__(
        self,
        *,
        cfg: AwsConfig,
        lineage: LineageEmitter,
        observation_provider: ObservationProvider,
        cue_provider: ScheduledCueProvider,
        agent_id: str,
        stream_id: str,
    ) -> None:
        self.cfg = cfg
        self.lineage = lineage
        self.observation_provider = observation_provider
        self.cue_provider = cue_provider
        self.agent_id = agent_id
        self.stream_id = stream_id

    def tick(self, *, now: datetime | None = None) -> dict:
        t = now or now_utc()
        stats = LoopStats()

        observations = self.observation_provider.pull(now=t)
        for memory_id, signals in observations:
            decision = process_observation(
                lineage=self.lineage,
                agent_id=self.agent_id,
                stream_id=self.stream_id,
                memory_id=memory_id,
                signals=signals,
            )
            stats.observations_processed += 1
            if decision.action.value in {"invoke_encode", "invoke_recall", "reflex_execute"}:
                stats.observation_fired += 1
            else:
                stats.observation_deferred += 1

        cues = self.cue_provider.pull(now=t)
        due = due_cues(now=t, cues=cues)
        stats.cues_due = len(due)

        for cue in due:
            overdue_seconds = max(0.0, (t - cue.due_at).total_seconds())
            level = escalation_level(overdue_seconds=overdue_seconds)

            self.lineage.emit(
                event_type="implicit_trigger_evaluated",
                agent_id=self.agent_id,
                stream_id=self.stream_id,
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
            self.lineage.emit(
                event_type="implicit_trigger_fired",
                agent_id=self.agent_id,
                stream_id=self.stream_id,
                memory_id=cue.memory_id,
                actor_class="implicit_memory_controller",
                source_class="scheduler",
                payload={"action": "invoke_recall", "cue_id": cue.cue_id, "escalation_level": level},
            )
            stats.cues_fired += 1

            # policy-gated admission for scheduled path
            if cue.urgency * cue.risk_signal >= self.cfg.retrieval_policy.eligibility_threshold:
                self.lineage.emit(
                    event_type="implicit_admitted",
                    agent_id=self.agent_id,
                    stream_id=self.stream_id,
                    memory_id=cue.memory_id,
                    actor_class="implicit_memory_controller",
                    source_class="scheduler",
                    payload={"reason": "scheduled_priority", "cue_id": cue.cue_id, "escalation_level": level},
                )
                stats.cues_admitted += 1
            else:
                self.lineage.emit(
                    event_type="implicit_trigger_deferred",
                    agent_id=self.agent_id,
                    stream_id=self.stream_id,
                    memory_id=cue.memory_id,
                    actor_class="implicit_memory_controller",
                    source_class="scheduler",
                    payload={"reason": "scheduled_low_priority", "cue_id": cue.cue_id},
                )
                stats.cues_deferred += 1

        self.lineage.emit(
            event_type="snapshotted",
            agent_id=self.agent_id,
            stream_id=self.stream_id,
            memory_id="implicit-loop-tick",
            actor_class="implicit_memory_controller",
            source_class="internal_engine",
            payload={
                "snapshot_type": "implicit_loop_tick",
                "timestamp": t.isoformat(),
                "stats": stats.to_dict(),
                **self.cfg.retrieval_policy.audit_fields(),
            },
        )

        return stats.to_dict()
