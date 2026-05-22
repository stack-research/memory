from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from src.bootstrap import ensure_lineage_bootstrap
from src.config import load_config
from src.implicit_memory.cue_ingest import Cue
from src.implicit_memory.loop import ImplicitControllerLoop
from src.implicit_memory.procedure_state_store import S3ProcedureStateStore
from src.implicit_memory.provenance_resolver import LineageProvenanceResolver
from src.implicit_memory.scheduler import now_utc
from src.lineage_engine import LineageEngine
from src.lineage_reader import build_lineage_reader
from src.storage import LineageStorage


@dataclass
class StaticCueProvider:
    """Fixture cue provider — yields captured `Cue` objects directly,
    the same shape the live ingestion path (`cue_ingest.py`) produces.

    CONTROL_PLANE_INGEST Decision 2: the loop's input is one `Cue`
    stream; a fixture and a live drain are indistinguishable to it.
    This replaces the former two-provider stub pair
    (`StaticObservationProvider` + `StaticCueProvider`).
    """

    agent_id: str
    stream_id: str

    def pull(self, *, now):
        return [
            Cue(
                cue_id="cue-loop-obs-1",
                cue_type="safety_anomaly",
                agent_id=self.agent_id,
                stream_id=self.stream_id,
                source_id="static-fixture",
                source_class="fixture",
                payload={
                    "memory_id": "loop-obs-1",
                    "prediction_error": 0.5,
                    "goal_impact": 0.4,
                    "risk_signal": 0.6,
                    "repetition_signal": 0.1,
                    "contradiction_pressure": 0.2,
                    "explicit_directive": False,
                    "urgency": 0.4,
                    "sensory_confidence": 0.9,
                    "sensor_values": [0.8, 0.82, 0.79],
                },
            ),
            Cue(
                cue_id="cue-loop-1",
                cue_type="scheduled_cue",
                agent_id=self.agent_id,
                stream_id=self.stream_id,
                source_id="static-fixture",
                source_class="fixture",
                payload={
                    "memory_id": "meds-am",
                    "due_at": (now - timedelta(seconds=120)).isoformat(),
                    "urgency": 0.8,
                    "risk_signal": 0.9,
                },
            ),
        ]


if __name__ == "__main__":
    cfg = load_config()
    storage = LineageStorage(cfg)
    ensure_lineage_bootstrap(storage)
    # FIXME: pre-existing — LineageEngine requires a `time_context_id`
    # keyword; this __main__ runner predates that and is not exercised
    # by the regression suites.
    lineage = LineageEngine(storage)

    agent_id = "lab-agent-1"
    stream_id = f"im-loop-{now_utc().strftime('%Y%m%d%H%M%S')}"
    loop = ImplicitControllerLoop(
        cfg=cfg,
        lineage=lineage,
        cue_provider=StaticCueProvider(agent_id=agent_id, stream_id=stream_id),
        agent_id=agent_id,
        stream_id=stream_id,
        procedure_state_store=S3ProcedureStateStore(cfg),
        provenance_resolver=LineageProvenanceResolver(lineage_reader=build_lineage_reader(cfg)),
    )
    print(loop.tick())
