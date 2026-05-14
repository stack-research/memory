"""
Phase 3 self-test for v6 cutover.

Contracts verified:
  - The cutover emits exactly three events in order:
      time_context_declared → canonical_table_genesis → canonical_batch_committed
  - The genesis event references the same time_context_id declared above
    (same-batch resolution per §6.2).
  - The batch commit lists both prior event ids in order.
  - sequence_in_stream increments 1→2→3 across the bootstrap batch.
  - Each event's HLC monotonically advances (logical bumps on TAI collision).
  - The time_context_id verifies against its own content fields (no
    self-reference circularity).
  - Replay determinism: two cutover invocations with same args produce
    identical time_context_id and identical physical_moment payloads.

Run:
  PYTHONPATH=. uv run --project stacks python -m src.timekeeping._phase3_verify
"""

from __future__ import annotations

import sys
from typing import Callable

from src.cutover_v6 import CLEAN_RESET_PREDECESSOR_SENTINEL, cutover
from src.timekeeping.context import verify_time_context_id


def _events_from_cutover() -> tuple[list[dict], dict]:
    """Run a cutover into an in-memory accumulator and return the events.

    We can't introspect LineageEngine state with storage=None, so we capture
    via a tiny inline storage stub.
    """

    class _Capture:
        def __init__(self) -> None:
            self.events: list = []

        def append_event(self, event) -> dict:
            self.events.append(event)
            return {}

    cap = _Capture()
    summary = cutover(storage=cap, stream_id="phase3", agent_id="phase3-bot", memory_id="phase3-mem")
    return [
        {
            "event_id": e.event_id,
            "event_type": e.event_type,
            "payload": e.payload,
            "physical_moment": e.physical_moment,
            "parent_event_id": e.parent_event_id,
        }
        for e in cap.events
    ], summary


def test_cutover_emits_three_events_in_order() -> None:
    events, _ = _events_from_cutover()
    types_in_order = [e["event_type"] for e in events]
    assert types_in_order == [
        "time_context_declared",
        "canonical_table_genesis",
        "canonical_batch_committed",
    ], f"unexpected order: {types_in_order}"


def test_genesis_references_declared_context() -> None:
    events, summary = _events_from_cutover()
    declared, genesis, _ = events
    assert declared["payload"]["time_context_id"] == summary["time_context_id"]
    assert genesis["payload"]["time_context_id"] == summary["time_context_id"]
    assert genesis["payload"]["predecessor_boundary_event_id"] == CLEAN_RESET_PREDECESSOR_SENTINEL
    assert genesis["payload"]["genesis_reason"] in {
        "reset_and_replay", "lab_phase_iteration", "recovery", "schema_evolution",
    }


def test_batch_commit_lists_prior_events() -> None:
    events, _ = _events_from_cutover()
    declared, genesis, commit = events
    commit_payload = commit["payload"]
    assert commit_payload["event_ids"] == [declared["event_id"], genesis["event_id"]]
    assert commit_payload["batch_id"]
    assert commit_payload["time_context_id"] == declared["payload"]["time_context_id"]


def test_sequence_increments_across_batch() -> None:
    events, _ = _events_from_cutover()
    seqs = [e["physical_moment"]["sequence_in_stream"] for e in events]
    assert seqs == [1, 2, 3], f"expected sequence 1,2,3 — got {seqs}"


def test_hlc_advances_across_batch() -> None:
    """All three bootstrap events share the same TAI input, so logical
    component must bump 0 → 1 → 2 within the same stream HLC."""
    events, _ = _events_from_cutover()
    hlcs = [e["physical_moment"]["hlc_timestamp"] for e in events]
    parts = [tuple(int(p) for p in h.split(".")) for h in hlcs]
    assert parts[0][0] == parts[1][0] == parts[2][0], f"phys_ns should match: {hlcs}"
    assert parts == sorted(parts), f"HLC must be monotonic: {hlcs}"
    assert parts[0][1] == 0 and parts[1][1] == 1 and parts[2][1] == 2


def test_time_context_id_verifies_against_declared_payload() -> None:
    events, summary = _events_from_cutover()
    declared = events[0]
    assert verify_time_context_id(declared["payload"], summary["time_context_id"])


def test_replay_determinism_across_two_runs() -> None:
    events_a, summary_a = _events_from_cutover()
    events_b, summary_b = _events_from_cutover()
    # time_context_id must be identical.
    assert summary_a["time_context_id"] == summary_b["time_context_id"]
    # physical_moment payloads must be identical (event_ids will differ — UUIDs).
    for ea, eb in zip(events_a, events_b):
        assert ea["physical_moment"] == eb["physical_moment"], (
            f"physical_moment drift between runs: {ea['physical_moment']} vs {eb['physical_moment']}"
        )


def test_parent_chain_links_three_events() -> None:
    events, _ = _events_from_cutover()
    declared, genesis, commit = events
    assert declared["parent_event_id"] is None
    assert genesis["parent_event_id"] == declared["event_id"]
    assert commit["parent_event_id"] == genesis["event_id"]


CHECKS: list[tuple[str, Callable[[], None]]] = [
    ("cutover_emits_three_events_in_order", test_cutover_emits_three_events_in_order),
    ("genesis_references_declared_context", test_genesis_references_declared_context),
    ("batch_commit_lists_prior_events", test_batch_commit_lists_prior_events),
    ("sequence_increments_across_batch", test_sequence_increments_across_batch),
    ("hlc_advances_across_batch", test_hlc_advances_across_batch),
    ("time_context_id_verifies_against_declared_payload", test_time_context_id_verifies_against_declared_payload),
    ("replay_determinism_across_two_runs", test_replay_determinism_across_two_runs),
    ("parent_chain_links_three_events", test_parent_chain_links_three_events),
]


def _check(name: str, fn: Callable[[], None]) -> tuple[str, bool, str]:
    try:
        fn()
        return name, True, ""
    except AssertionError as exc:
        return name, False, str(exc) or "assertion failed"
    except Exception as exc:
        return name, False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    results = [_check(name, fn) for name, fn in CHECKS]
    width = max(len(name) for name, _, _ in results)
    failures = 0
    for name, ok, reason in results:
        status = "PASS" if ok else "FAIL"
        line = f"{status:4}  {name:<{width}}"
        if not ok:
            line += f"  -- {reason}"
            failures += 1
        print(line)
    print()
    print(f"Phase 3 verify: {len(results) - failures}/{len(results)} passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
