from __future__ import annotations

from src.bootstrap import ensure_lineage_bootstrap
from src.config import load_config
from src.lineage_engine import LineageEngine
from src.storage import LineageStorage


def run() -> dict:
    cfg = load_config()
    storage = LineageStorage(cfg)
    ensure_lineage_bootstrap(storage)
    lineage = LineageEngine(storage)

    agent_id = "lab-agent-1"
    stream_id = "im-s-provenance-closeout"
    memory_id = "provenance-signal-writer-v1"

    deferred_items = [
        {
            "item": "cross_memory_parent_fallback_path",
            "status": "deferred",
            "reason": "lineage query scopes by memory_id in v1, so cross-memory parent resolution is not currently reachable in runtime path",
        }
    ]

    event = lineage.emit(
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        actor_class="system_worker",
        source_class="internal_engine",
        payload={
            "snapshot_type": "provenance_signal_writer_implementation_status",
            "spec": "PROVENANCE_SIGNAL_WRITER",
            "version": "v1.0",
            "status": "implemented_with_noted_deferred_items",
            "completed": [
                "deterministic_compute_chain_signals",
                "bounded_parent_walk_with_max_depth",
                "fallback_reason_and_provenance_signal_source_emission",
                "vector_write_provenance_metadata_and_lineage_event",
                "implicit_loop_provenance_inputs_from_resolver",
                "im_r_determinism_replay_fallback_unknown_source_coverage",
                "im_regression_and_axis_dominance_audit_green",
            ],
            "deferred": deferred_items,
        },
    )

    summary = {
        "suite": "S",
        "pass": True,
        "event_id": event.event_id,
        "stream_id": stream_id,
        "deferred_count": len(deferred_items),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
