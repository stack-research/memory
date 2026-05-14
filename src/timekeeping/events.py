"""
Payload builders for the four time-related event types added in v6:

  - `time_context_declared`      (§6, §6.1)
  - `canonical_batch_committed`  (§6.2)
  - `canonical_table_boundary`   (§10)
  - `canonical_table_genesis`    (§10.1)

These functions build the *payload dict* only. The lineage engine wraps
them in MemoryEvent envelopes.

Genesis event behaviour at bootstrap: the first `time_context_declared`
event in v6 carries `physical_moment.time_context_id` equal to the id it
declares (self-reference, safe per §6.2 because the hash preimage excludes
`time_context_id`). The lineage engine handles the self-reference on
emission; this module provides the payload only.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .context import TimeContext


GENESIS_REASON_ENUM = {
    "schema_evolution",
    "reset_and_replay",
    "recovery",
    "lab_phase_iteration",
}


def time_context_declared_payload(
    *,
    time_context_id: str,
    context: TimeContext,
    declared_at_tai_iso: str,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    """Build the payload for a `time_context_declared` event."""
    payload: dict[str, Any] = {
        "time_context_id": time_context_id,
        "declared_at_tai_iso": declared_at_tai_iso,
        **asdict(context),
        "fallback_reason": fallback_reason,
    }
    return payload


def canonical_batch_committed_payload(
    *,
    batch_id: str,
    event_ids: list[str],
    time_context_id: str,
) -> dict[str, Any]:
    """Build the payload for a `canonical_batch_committed` event.

    Closes a batch by listing its member event ids in order. Replay uses
    this to resolve same-batch references for `time_context_id` resolution
    per §6.2.
    """
    return {
        "batch_id": batch_id,
        "event_ids": list(event_ids),
        "time_context_id": time_context_id,
    }


def canonical_table_boundary_payload(
    *,
    predecessor_table: str,
    successor_table: str,
    final_sequence_in_stream: int,
    boundary_reason: str,
    time_context_id: str,
) -> dict[str, Any]:
    """Build the payload for a `canonical_table_boundary` event.

    Emitted in the predecessor (e.g. v5) table to mark the cutover and
    carry the final per-stream sequence number.
    """
    return {
        "predecessor_table": predecessor_table,
        "successor_table": successor_table,
        "final_sequence_in_stream": final_sequence_in_stream,
        "boundary_reason": boundary_reason,
        "time_context_id": time_context_id,
    }


def canonical_table_genesis_payload(
    *,
    predecessor_table: str,
    predecessor_boundary_event_id: str,
    genesis_reason: str,
    time_context_id: str,
    schema_version: str,
) -> dict[str, Any]:
    """Build the payload for a `canonical_table_genesis` event."""
    if genesis_reason not in GENESIS_REASON_ENUM:
        raise ValueError(
            f"genesis_reason '{genesis_reason}' not in closed enum {sorted(GENESIS_REASON_ENUM)}"
        )
    return {
        "predecessor_table": predecessor_table,
        "predecessor_boundary_event_id": predecessor_boundary_event_id,
        "genesis_reason": genesis_reason,
        "time_context_id": time_context_id,
        "schema_version": schema_version,
    }


class BootstrapBatch:
    """Helper that emits the v6 bootstrap pair in a single atomic batch:

        1. time_context_declared (self-referential time_context_id)
        2. canonical_table_genesis (references the same time_context_id
           and the predecessor's canonical_table_boundary event id)
        3. canonical_batch_committed (closes the batch)

    Same-batch resolution per §6.2 lets the genesis event reference the
    time_context_id declared in the same atomic batch.
    """

    def __init__(
        self,
        *,
        context: TimeContext,
        time_context_id: str,
        predecessor_table: str,
        predecessor_boundary_event_id: str,
        genesis_reason: str,
        schema_version: str,
        declared_at_tai_iso: str,
    ) -> None:
        self.context = context
        self.time_context_id = time_context_id
        self.predecessor_table = predecessor_table
        self.predecessor_boundary_event_id = predecessor_boundary_event_id
        self.genesis_reason = genesis_reason
        self.schema_version = schema_version
        self.declared_at_tai_iso = declared_at_tai_iso

    def declaration_payload(self) -> dict[str, Any]:
        return time_context_declared_payload(
            time_context_id=self.time_context_id,
            context=self.context,
            declared_at_tai_iso=self.declared_at_tai_iso,
        )

    def genesis_payload(self) -> dict[str, Any]:
        return canonical_table_genesis_payload(
            predecessor_table=self.predecessor_table,
            predecessor_boundary_event_id=self.predecessor_boundary_event_id,
            genesis_reason=self.genesis_reason,
            time_context_id=self.time_context_id,
            schema_version=self.schema_version,
        )
