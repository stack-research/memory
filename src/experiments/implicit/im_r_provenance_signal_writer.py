from __future__ import annotations

from src.explicit_memory.provenance import compute_chain_signals


class _StubReader:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def query_memory_events(self, *, stream_id: str, memory_id: str, as_of_time: str | None = None):
        if as_of_time is None:
            return list(self.rows)
        return [r for r in self.rows if r.get("event_time", "") <= as_of_time]


def run() -> dict:
    stream_id = "im-r"
    memory_id = "m-r"

    rows = [
        {
            "event_id": "e-1",
            "parent_event_id": None,
            "source_class": "sensor",
            "event_time": "2026-05-12T00:00:00+00:00",
        },
        {
            "event_id": "e-2",
            "parent_event_id": "e-1",
            "source_class": "scheduler",
            "event_time": "2026-05-12T01:00:00+00:00",
        },
        {
            "event_id": "e-3",
            "parent_event_id": "e-2",
            "source_class": "scheduler",
            "event_time": "2026-05-12T02:00:00+00:00",
        },
    ]

    reader = _StubReader(rows)
    as_of = "2026-05-12T03:00:00+00:00"

    a = compute_chain_signals(memory_id=memory_id, stream_id=stream_id, as_of_time=as_of, lineage_reader=reader, computed_at=as_of)
    b = compute_chain_signals(memory_id=memory_id, stream_id=stream_id, as_of_time=as_of, lineage_reader=reader, computed_at=as_of)

    determinism_ok = (
        a.parent_chain_depth == b.parent_chain_depth
        and round(a.source_diversity, 6) == round(b.source_diversity, 6)
        and round(a.age_of_original_source, 6) == round(b.age_of_original_source, 6)
        and a.chain_root_event_id == b.chain_root_event_id
    )

    replay_cutoff = compute_chain_signals(
        memory_id=memory_id,
        stream_id=stream_id,
        as_of_time="2026-05-12T01:00:00+00:00",
        lineage_reader=reader,
        computed_at="2026-05-12T01:00:00+00:00",
    )
    replay_ok = replay_cutoff.parent_chain_depth == 1 and replay_cutoff.chain_root_event_id == "e-1"

    broken_reader = _StubReader(
        [
            {
                "event_id": "x-2",
                "parent_event_id": "missing-parent",
                "source_class": "sensor",
                "event_time": "2026-05-12T02:00:00+00:00",
            }
        ]
    )
    broken = compute_chain_signals(
        memory_id=memory_id,
        stream_id=stream_id,
        as_of_time=as_of,
        lineage_reader=broken_reader,
        computed_at=as_of,
    )
    fallback_ok = broken.fallback_reason == "broken_parent_link"

    cycle_reader = _StubReader(
        [
            {
                "event_id": "c-1",
                "parent_event_id": "c-2",
                "source_class": "sensor",
                "event_time": "2026-05-12T00:00:00+00:00",
            },
            {
                "event_id": "c-2",
                "parent_event_id": "c-1",
                "source_class": "sensor",
                "event_time": "2026-05-12T01:00:00+00:00",
            },
        ]
    )
    cycle = compute_chain_signals(
        memory_id=memory_id,
        stream_id=stream_id,
        as_of_time=as_of,
        lineage_reader=cycle_reader,
        computed_at=as_of,
    )
    cycle_ok = cycle.fallback_reason == "cycle_detected"

    deep_rows = [
        {
            "event_id": "d-0",
            "parent_event_id": None,
            "source_class": "sensor",
            "event_time": "2026-05-12T00:00:00+00:00",
        }
    ]
    for i in range(1, 70):
        hh = i // 60
        mm = i % 60
        deep_rows.append(
            {
                "event_id": f"d-{i}",
                "parent_event_id": f"d-{i-1}",
                "source_class": "sensor",
                "event_time": f"2026-05-12T{hh:02d}:{mm:02d}:00+00:00",
            }
        )
    deep = compute_chain_signals(
        memory_id=memory_id,
        stream_id=stream_id,
        as_of_time=as_of,
        lineage_reader=_StubReader(deep_rows),
        max_chain_depth=16,
        computed_at=as_of,
    )
    max_depth_ok = deep.fallback_reason == "max_chain_depth_exceeded" and deep.parent_chain_depth == 16

    unknown_reader = _StubReader(
        [
            {
                "event_id": "u-1",
                "parent_event_id": None,
                "source_class": "",
                "event_time": "2026-05-12T00:00:00+00:00",
            },
            {
                "event_id": "u-2",
                "parent_event_id": "u-1",
                "source_class": None,
                "event_time": "2026-05-12T01:00:00+00:00",
            },
        ]
    )
    unknown = compute_chain_signals(
        memory_id=memory_id,
        stream_id=stream_id,
        as_of_time=as_of,
        lineage_reader=unknown_reader,
        computed_at=as_of,
    )
    # Unknown source classes are sentinel-normalized, not fallback.
    unknown_source_ok = unknown.fallback_reason is None and round(unknown.source_diversity, 6) == 0.5

    summary = {
        "suite": "R",
        "determinism_ok": determinism_ok,
        "replay_ok": replay_ok,
        "fallback_ok": fallback_ok,
        "cycle_ok": cycle_ok,
        "unknown_source_ok": unknown_source_ok,
        "max_depth_ok": max_depth_ok,
        "pass": determinism_ok and replay_ok and fallback_ok and cycle_ok and unknown_source_ok and max_depth_ok,
        "sample": {
            "parent_chain_depth": a.parent_chain_depth,
            "source_diversity": a.source_diversity,
            "age_of_original_source": a.age_of_original_source,
        },
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
