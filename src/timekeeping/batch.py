"""
Atomic-batch boundary marker for §6.2 same-batch resolution.

A `canonical_batch_committed` event closes a batch. A `time_context_id` or
`canonical_table_genesis.predecessor_boundary_event_id` reference resolves
to "same batch" if both the referencing and referenced events share the
same `batch_id` and the closing `canonical_batch_committed` event for that
`batch_id` is present in lineage.

`batch_id` is a deterministic hash of the ordered list of event ids in the
batch. Two batches with identical contents in identical order produce the
same batch_id; that property is what makes batch resolution replay-stable.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class BatchCommit:
    """Accumulator for events that will close as a single atomic batch."""

    event_ids: list[str] = field(default_factory=list)
    closed: bool = False

    def add(self, event_id: str) -> None:
        if self.closed:
            raise RuntimeError("Cannot add events to a closed batch")
        self.event_ids.append(event_id)

    def close(self) -> str:
        """Close the batch and return its deterministic batch_id."""
        if self.closed:
            raise RuntimeError("Batch already closed")
        self.closed = True
        return new_batch_id(self.event_ids)


def new_batch_id(event_ids: list[str]) -> str:
    """Deterministic batch id: SHA-256 of the joined event id sequence."""
    material = "\n".join(event_ids).encode("utf-8")
    return hashlib.sha256(material).hexdigest()
