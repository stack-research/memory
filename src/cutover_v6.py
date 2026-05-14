"""
v6 cutover: emit the bootstrap batch into the v6 canonical table.

Per TAI_TIMEKEEPING spec §10/§10.1 and the lab-phase reset policy in
`AGENTS.md`, this lab does a *clean reset* rather than a v5 → v6 migration:
v5 stays untouched as a historical container; v6 starts cold with the
bootstrap batch as its first three events.

The bootstrap batch contains, in order:
  1. `time_context_declared` — declares the active TimeContext with a
     self-referential `physical_moment.time_context_id` (safe per §6.2
     because the hash preimage excludes that field).
  2. `canonical_table_genesis` — opens the v6 stream; references the
     time_context_id declared above (same-batch resolution per §6.2).
  3. `canonical_batch_committed` — closes the batch; replay uses this
     to validate same-batch references deterministically.

For a clean-reset lab, `predecessor_boundary_event_id` is the literal
`clean_reset_no_predecessor` since there is no v5 boundary event to
point at. This is consistent with `genesis_reason = "reset_and_replay"`.

Run:
  PYTHONPATH=. uv run --project stacks python -m src.cutover_v6 \
    [--stream-id <id>] [--agent-id <id>] [--memory-id <id>]
    [--genesis-reason reset_and_replay|lab_phase_iteration|recovery|schema_evolution]
    [--storage real|inmemory]  (inmemory is the default; real requires AWS)

Exit code 0 on success.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from src.heliotime import physical_moment
from src.heliotime._ephemeris import (
    DEFAULT_EPHEMERIS_ID,
    ephemeris_data_hash,
    try_set_ephemeris,
)
from src.lineage_engine import LineageEngine
from src.timekeeping import (
    BatchCommit,
    BootstrapBatch,
    canonical_batch_committed_payload,
    declare_time_context,
)
from src.timekeeping.context import (
    EPHEMERIS_ID_DEFAULT,
    HLC_VARIANT_DEFAULT,
    SOLAR_AGE_ANCHOR_DEFAULT,
    TIMEKEEPING_LIBRARY,
    TIMEKEEPING_LIBRARY_VERSION,
)


CLEAN_RESET_PREDECESSOR_SENTINEL = "clean_reset_no_predecessor"


def _build_time_context() -> tuple[Any, str, str | None]:
    """Build the default v6 TimeContext.

    Tries to pin astropy to DE440; falls back deterministically if
    unavailable (recorded in `fallback_reason`).
    """
    active_ephem, fallback_reason = try_set_ephemeris(DEFAULT_EPHEMERIS_ID)
    ephem_id_in_use = active_ephem or EPHEMERIS_ID_DEFAULT
    ephem_hash = ephemeris_data_hash(ephem_id_in_use)

    ctx, ctx_id = declare_time_context(
        tzdata_version="iana-2025a",  # pinned for v1; future spec amendment to bump
        bipm_tai_realization="bipm-tai-2026-04",
        ephemeris_id=ephem_id_in_use,
        ephemeris_data_hash=ephem_hash,
        leap_second_table_version="iers-bulletin-c-2026-01",
        solar_age_anchor=SOLAR_AGE_ANCHOR_DEFAULT,
        timekeeping_library=TIMEKEEPING_LIBRARY,
        timekeeping_library_version=TIMEKEEPING_LIBRARY_VERSION,
        hlc_variant=HLC_VARIANT_DEFAULT,
        calculator_config_hash="v6-default",
    )
    return ctx, ctx_id, fallback_reason


def cutover(
    *,
    storage,
    stream_id: str = "lab-default",
    agent_id: str = "lab-bootstrap",
    memory_id: str = "lab-cutover-v6",
    genesis_reason: str = "reset_and_replay",
) -> dict[str, Any]:
    """Emit the v6 bootstrap batch and return a summary."""

    ctx, ctx_id, fallback_reason = _build_time_context()
    bootstrap_moment = physical_moment("2026-05-14T00:00:00.000", scale="tai")

    engine = LineageEngine(storage=storage, time_context_id=ctx_id)

    batch = BatchCommit()

    # 1) time_context_declared (self-referential time_context_id).
    declared = engine.emit(
        event_type="time_context_declared",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload={
            "time_context_id": ctx_id,
            "declared_at_tai_iso": bootstrap_moment.tai_iso,
            "fallback_reason": fallback_reason,
            **{
                "tzdata_version": ctx.tzdata_version,
                "bipm_tai_realization": ctx.bipm_tai_realization,
                "ephemeris_id": ctx.ephemeris_id,
                "ephemeris_data_hash": ctx.ephemeris_data_hash,
                "leap_second_table_version": ctx.leap_second_table_version,
                "solar_age_anchor": ctx.solar_age_anchor,
                "timekeeping_library": ctx.timekeeping_library,
                "timekeeping_library_version": ctx.timekeeping_library_version,
                "hlc_variant": ctx.hlc_variant,
                "calculator_config_hash": ctx.calculator_config_hash,
            },
        },
        tai_moment=bootstrap_moment,
        actor_class="lab_bootstrap",
        source_class="cutover_v6",
        tier1b_null_reasons={
            "local_civil_time_observed": "machine_origin",
            "tz_offset_seconds": "tz_undeclared",
            "ntp_state": "ntp_unavailable",
        },
    )
    batch.add(declared.event_id)

    # 2) canonical_table_genesis (references the same time_context_id
    #    declared above; same-batch resolution per §6.2).
    genesis = engine.emit(
        event_type="canonical_table_genesis",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload={
            "predecessor_table": "memory_lab.memory_events_v5",
            "predecessor_boundary_event_id": CLEAN_RESET_PREDECESSOR_SENTINEL,
            "genesis_reason": genesis_reason,
            "time_context_id": ctx_id,
            "schema_version": "6.0",
        },
        tai_moment=bootstrap_moment,
        actor_class="lab_bootstrap",
        source_class="cutover_v6",
        parent_event_id=declared.event_id,
        tier1b_null_reasons={
            "local_civil_time_observed": "machine_origin",
            "tz_offset_seconds": "tz_undeclared",
            "ntp_state": "ntp_unavailable",
        },
    )
    batch.add(genesis.event_id)

    batch_id = batch.close()

    # 3) canonical_batch_committed (closes the batch).
    commit = engine.emit(
        event_type="canonical_batch_committed",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=memory_id,
        payload=canonical_batch_committed_payload(
            batch_id=batch_id,
            event_ids=[declared.event_id, genesis.event_id],
            time_context_id=ctx_id,
        ),
        tai_moment=bootstrap_moment,
        actor_class="lab_bootstrap",
        source_class="cutover_v6",
        parent_event_id=genesis.event_id,
        tier1b_null_reasons={
            "local_civil_time_observed": "machine_origin",
            "tz_offset_seconds": "tz_undeclared",
            "ntp_state": "ntp_unavailable",
        },
    )

    return {
        "time_context_id": ctx_id,
        "fallback_reason": fallback_reason,
        "batch_id": batch_id,
        "event_ids": {
            "time_context_declared": declared.event_id,
            "canonical_table_genesis": genesis.event_id,
            "canonical_batch_committed": commit.event_id,
        },
        "stream_id": stream_id,
        "schema_version": "6.0",
    }


def _build_storage(kind: str):
    if kind == "inmemory":
        return None  # LineageEngine accepts None and skips persistence
    if kind == "real":
        from src.aws_session import make_session  # noqa: F401  (lazy import)
        from src.bootstrap import ensure_lineage_bootstrap
        from src.config import load_config
        from src.storage import LineageStorage

        cfg = load_config()
        storage = LineageStorage(cfg)
        ensure_lineage_bootstrap(storage)
        return storage
    raise SystemExit(f"unknown --storage value: {kind!r}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="v6 cutover bootstrap batch emitter")
    p.add_argument("--stream-id", default="lab-default")
    p.add_argument("--agent-id", default="lab-bootstrap")
    p.add_argument("--memory-id", default="lab-cutover-v6")
    p.add_argument(
        "--genesis-reason",
        default="reset_and_replay",
        choices=["reset_and_replay", "lab_phase_iteration", "recovery", "schema_evolution"],
    )
    p.add_argument("--storage", default="inmemory", choices=["inmemory", "real"])
    args = p.parse_args(argv)

    storage = _build_storage(args.storage)
    summary = cutover(
        storage=storage,
        stream_id=args.stream_id,
        agent_id=args.agent_id,
        memory_id=args.memory_id,
        genesis_reason=args.genesis_reason,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
