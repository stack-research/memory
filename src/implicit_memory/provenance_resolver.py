from __future__ import annotations

from src.explicit_memory.provenance import compute_chain_signals
from src.lineage_reader import LineageReader


class LineageProvenanceResolver:
    def __init__(self, *, lineage_reader: LineageReader) -> None:
        self.lineage_reader = lineage_reader

    def resolve(self, *, memory_id: str, stream_id: str, as_of_time: str, computed_at: str | None = None) -> dict[str, object]:
        # `computed_at` must be replay-derived TAI per TAI_TIMEKEEPING §13.
        # Fallback to `as_of_time` (the loop tick) keeps both fields anchored
        # to the same deterministic source.
        signals = compute_chain_signals(
            memory_id=memory_id,
            stream_id=stream_id,
            as_of_time=as_of_time,
            lineage_reader=self.lineage_reader,
            computed_at=computed_at or as_of_time,
        )
        payload = signals.as_payload()
        return {
            "parent_chain_depth": payload["provenance_signals"]["parent_chain_depth"],
            "source_diversity": payload["provenance_signals"]["source_diversity"],
            "age_of_original_source": payload["provenance_signals"]["age_of_original_source"],
            "chain_root_event_id": payload["chain_root_event_id"],
            "chain_length": payload["chain_length"],
            "distinct_source_classes": payload["distinct_source_classes"],
            "computed_at": payload["computed_at"],
            "as_of_time": payload["as_of_time"],
            "fallback_reason": payload["fallback_reason"],
            "provenance_signal_source": payload.get("provenance_signal_source", "computed"),
        }
