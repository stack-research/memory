"""
Timekeeping primitives implementing `specs/TAI_TIMEKEEPING.md` v1.2.

Modules:
  - `context` — TimeContext, deterministic `time_context_id`, declaration helpers.
  - `hlc` — Kulkarni 2014 hybrid logical clock, deterministic from TAI + sequence.
  - `batch` — `canonical_batch_committed` marker for same-batch resolution.
  - `events` — payload builders for time_context_declared / canonical_batch_committed
              / canonical_table_genesis / canonical_table_boundary events.

Spec terminology preserved: field names match the spec verbatim so the
audit chain works at read time.
"""

from .context import (
    TimeContext,
    compute_time_context_id,
    declare_time_context,
)
from .hlc import HLC, HLCState
from .batch import BatchCommit, new_batch_id
from .events import (
    BootstrapBatch,
    canonical_batch_committed_payload,
    canonical_table_boundary_payload,
    canonical_table_genesis_payload,
    time_context_declared_payload,
)

__all__ = [
    "TimeContext",
    "compute_time_context_id",
    "declare_time_context",
    "HLC",
    "HLCState",
    "BatchCommit",
    "new_batch_id",
    "BootstrapBatch",
    "canonical_batch_committed_payload",
    "canonical_table_boundary_payload",
    "canonical_table_genesis_payload",
    "time_context_declared_payload",
]
