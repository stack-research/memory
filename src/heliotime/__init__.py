"""
heliotime — TAI + heliocentric ecliptic coordinate kernel.

Spec: specs/TAI_TIMEKEEPING.md
Seed: notes/solar_time/solar_timestamp.py

Produces deterministic `PhysicalMoment` values from an explicit input
moment. No default current wall-clock in replay paths: every public
function accepts an explicit input moment and operates on it; only
`now()` reads the clock and it is explicitly named.

Mechanism: TAI (uninterrupted SI seconds, no leap seconds).
Coordinate: solar age (megayears) + Earth heliocentric ecliptic
longitude (degrees), computed via astropy.

Dependency: astropy only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from astropy.coordinates import SkyCoord, get_body_barycentric_posvel
from astropy.time import Time


SOLAR_AGE_AT_J2000_MYR: float = 4603.0
"""Solar age at J2000.0 in megayears.

Sources: Bonanno & Frohlich 2015; Connelly et al. 2012.
±1 Myr uncertainty. Pinned by `time_context_declared.solar_age_anchor`.
"""

_J2000_TAI: Time = Time("2000-01-01 12:00:32", scale="tai", format="iso")
JD_J2000_TAI: float = _J2000_TAI.jd

_DAYS_PER_MYR: float = 365.25 * 1_000_000


@dataclass(frozen=True)
class PhysicalMoment:
    """Tier 1a content of a v6 lineage event's `physical_moment` block.

    Tier 1b/2 fields are layered on at emission time by the lineage engine.
    """

    tai_iso: str
    solar_age_myr: float
    ecliptic_lon_deg: float


def _to_tai(t: Time) -> Time:
    return t.tai if t.scale != "tai" else t


def _parse_input(dt: datetime | str | Time, scale: str) -> Time:
    if isinstance(dt, Time):
        return _to_tai(dt)
    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            scale = "utc"
        return _to_tai(Time(dt, scale=scale, format="datetime"))
    if isinstance(dt, str):
        # astropy auto-detects iso vs isot vs other ISO-shaped strings.
        # Pinning `format="iso"` rejects T-separator inputs even though
        # astropy emits them by default via `.isot`.
        return _to_tai(Time(dt, scale=scale))
    raise TypeError(
        f"Expected datetime, ISO string, or astropy Time. Got: {type(dt).__name__}"
    )


def physical_moment(
    dt: datetime | str | Time,
    *,
    scale: str = "utc",
) -> PhysicalMoment:
    """Compute a `PhysicalMoment` for an explicit input moment.

    `dt` must be supplied. Use `now()` if you intend to read the wall-clock,
    which makes the read explicit and auditable.
    """
    t = _parse_input(dt, scale)
    delta_days = float(t.jd - JD_J2000_TAI)
    age = SOLAR_AGE_AT_J2000_MYR + (delta_days / _DAYS_PER_MYR)
    pos, _ = get_body_barycentric_posvel("earth", t)
    coord = SkyCoord(pos, frame="icrs", representation_type="cartesian")
    lon = float(coord.heliocentricmeanecliptic.lon.deg)
    # Cast to plain Python types so downstream JSON serialization and
    # equality comparisons don't carry numpy semantics into payloads.
    return PhysicalMoment(
        tai_iso=str(t.tai.isot),
        solar_age_myr=float(age),
        ecliptic_lon_deg=float(lon),
    )


def now() -> PhysicalMoment:
    """Read the wall-clock and produce a `PhysicalMoment`.

    Named explicitly so callers cannot accidentally introduce a wall-clock
    dependency. Replay code paths must never call `now()` — they must
    pass an explicit `dt` from lineage.
    """
    return physical_moment(Time.now(), scale="tai")


def tai_iso(dt: datetime | str | Time, *, scale: str = "utc") -> str:
    """Convenience: return only the TAI ISO string for an input moment."""
    return _parse_input(dt, scale).tai.isot
