from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from src.bootstrap import ensure_lineage_bootstrap
from src.config import load_config
from src.implicit_memory.controller import ObservationSignals
from src.implicit_memory.loop import ImplicitControllerLoop
from src.implicit_memory.procedure_state_store import S3ProcedureStateStore
from src.implicit_memory.scheduler import ScheduledCue, now_utc
from src.lineage_engine import LineageEngine
from src.storage import LineageStorage


@dataclass
class StaticObservationProvider:
    def pull(self, *, now):
        return [
            (
                "loop-obs-1",
                ObservationSignals(
                    prediction_error=0.5,
                    goal_impact=0.4,
                    risk_signal=0.6,
                    repetition_signal=0.1,
                    contradiction_pressure=0.2,
                    explicit_directive=False,
                    urgency=0.4,
                    sensory_confidence=0.9,
                    sensor_values=[0.8, 0.82, 0.79],
                ),
            )
        ]


@dataclass
class StaticCueProvider:
    def pull(self, *, now):
        return [
            ScheduledCue(
                cue_id="cue-loop-1",
                memory_id="meds-am",
                due_at=now - timedelta(seconds=120),
                urgency=0.8,
                risk_signal=0.9,
            )
        ]


if __name__ == "__main__":
    cfg = load_config()
    storage = LineageStorage(cfg)
    ensure_lineage_bootstrap(storage)
    lineage = LineageEngine(storage)

    loop = ImplicitControllerLoop(
        cfg=cfg,
        lineage=lineage,
        observation_provider=StaticObservationProvider(),
        cue_provider=StaticCueProvider(),
        agent_id="lab-agent-1",
        stream_id=f"im-loop-{now_utc().strftime('%Y%m%d%H%M%S')}",
        procedure_state_store=S3ProcedureStateStore(cfg),
    )
    print(loop.tick())
