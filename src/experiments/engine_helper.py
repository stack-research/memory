"""Shared LineageEngine factory for explicit experiments (e1–e12).

The e* experiments don't construct their own TimeContext; they share
the cutover's v1 default so all experiment lineage anchors against
the same time context as the canonical bootstrap. The default
bootstrap moment is fixed so the experiments are replay-deterministic
even when re-run against a clean canonical table.

Per the operator override (2026-05-14T17:47:57.222), prior S3
objects are disposable — each experiment run regenerates fresh
lineage events; there is no migration burden.
"""

from __future__ import annotations

from src.heliotime import PhysicalMoment, physical_moment
from src.heliotime._ephemeris import (
    DEFAULT_EPHEMERIS_ID,
    ephemeris_data_hash,
    try_set_ephemeris,
)
from src.lineage_engine import LineageEngine
from src.storage import LineageStorage
from src.timekeeping import declare_time_context
from src.timekeeping.context import (
    EPHEMERIS_ID_DEFAULT,
    HLC_VARIANT_DEFAULT,
    SOLAR_AGE_ANCHOR_DEFAULT,
    TIMEKEEPING_LIBRARY,
    TIMEKEEPING_LIBRARY_VERSION,
)


# Fixed bootstrap moment for explicit experiments. Replay-deterministic.
# Cutover v7 used 2026-05-15T00:00:00.000; experiments run "after"
# the cutover so we pick a slightly later anchor.
EXPERIMENT_TAI_ANCHOR: str = "2026-05-15T01:00:00.000"


def _build_experiment_time_context() -> str:
    """Build the same TimeContext shape as cutover_v7 so experiment
    lineage and canonical bootstrap share a context id when the
    inputs match. Returns the deterministic time_context_id."""
    active_ephem, _ = try_set_ephemeris(DEFAULT_EPHEMERIS_ID)
    ephem_id_in_use = active_ephem or EPHEMERIS_ID_DEFAULT
    ephem_hash = ephemeris_data_hash(ephem_id_in_use)
    _, ctx_id = declare_time_context(
        tzdata_version="iana-2025a",
        bipm_tai_realization="bipm-tai-2026-04",
        ephemeris_id=ephem_id_in_use,
        ephemeris_data_hash=ephem_hash,
        leap_second_table_version="iers-bulletin-c-2026-01",
        solar_age_anchor=SOLAR_AGE_ANCHOR_DEFAULT,
        timekeeping_library=TIMEKEEPING_LIBRARY,
        timekeeping_library_version=TIMEKEEPING_LIBRARY_VERSION,
        hlc_variant=HLC_VARIANT_DEFAULT,
        calculator_config_hash="v7-default",
    )
    return ctx_id


def make_experiment_engine(
    storage: LineageStorage | None,
    *,
    anchor_tai_iso: str = EXPERIMENT_TAI_ANCHOR,
) -> LineageEngine:
    """Return a v7-ready `LineageEngine` for explicit experiments.

    The engine is constructed with:
      - the v7 default `TimeContext` (same shape as cutover_v7)
      - a fixed `default_tai_moment` so per-emit `tai_moment` can be
        omitted by experiment code (no wall-clock reads)

    Pass the result anywhere the e1–e12 experiments construct an
    engine.
    """
    ctx_id = _build_experiment_time_context()
    anchor_moment: PhysicalMoment = physical_moment(anchor_tai_iso, scale="tai")
    return LineageEngine(
        storage,
        time_context_id=ctx_id,
        default_tai_moment=anchor_moment,
    )


__all__ = ["EXPERIMENT_TAI_ANCHOR", "make_experiment_engine"]
