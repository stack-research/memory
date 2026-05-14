"""
solar_timestamp.py

Returns a solar timestamp for any moment in time:

    {solar_age_Myr}:{ecliptic_lon_deg}

  - Solar age in megayears (Sun's age, ~4603 Myr at J2000.0)
  - Earth's heliocentric ecliptic longitude in degrees [0, 360)

Timescale: TAI (International Atomic Time)
  Counts uninterrupted SI seconds via caesium-133 atomic transitions.
  No leap seconds. No coupling to Earth's irregular rotation.
  UTC is accepted as input only as a convenience bridge and is
  immediately converted to TAI. All calculations are in TAI.

Usage
-----
  # Current moment
  print(solar_timestamp())

  # From a UTC datetime object
  from datetime import datetime, timezone
  print(solar_timestamp(datetime(1982, 10, 27, 5, 21, tzinfo=timezone.utc)))

  # From a UTC string (ISO 8601)
  print(solar_timestamp("1982-10-27 05:21:00"))

  # From a TAI string (pass scale='tai')
  print(solar_timestamp("1982-10-27 05:21:21", scale="tai"))

Dependencies: astropy
"""

from datetime import datetime, timezone, timedelta
from astropy.time import Time
from astropy.coordinates import get_body_barycentric_posvel, SkyCoord


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Sun's age in megayears at J2000.0 in TAI.
# J2000.0 = 2000-01-01 12:00:00 UTC = 2000-01-01 12:00:32 TAI
# Best current estimate: 4.603 Gyr +/- ~1 Myr
# Sources: Bonanno & Fröhlich (2015), Connelly et al. (2012)
SOLAR_AGE_AT_J2000_MYR: float = 4603.0

_J2000_TAI: Time = Time("2000-01-01 12:00:32", scale="tai", format="iso")
JD_J2000_TAI: float = _J2000_TAI.jd

DAYS_PER_MYR: float = 365.25 * 1_000_000


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_tai(t: Time) -> Time:
    """Ensure a Time object is in TAI scale."""
    return t.tai if t.scale != "tai" else t


def _parse_input(dt, scale: str) -> Time:
    """
    Accept:
      - None                  -> current moment
      - datetime object       -> uses tzinfo if present, else assumes UTC
      - ISO 8601 string       -> parsed as the given scale (default 'utc')
      - astropy Time object   -> used directly
    """
    if dt is None:
        return Time.now().tai

    if isinstance(dt, Time):
        return _to_tai(dt)

    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            # aware datetime: convert to UTC naive for astropy
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            scale = "utc"
        return _to_tai(Time(dt, scale=scale, format="datetime"))

    if isinstance(dt, str):
        return _to_tai(Time(dt, scale=scale, format="iso"))

    raise TypeError(
        f"Expected None, datetime, ISO string, or astropy Time. Got: {type(dt)}"
    )


# ---------------------------------------------------------------------------
# Core calculations
# ---------------------------------------------------------------------------

def _solar_age_myr(t: Time) -> float:
    delta_days = t.jd - JD_J2000_TAI
    return SOLAR_AGE_AT_J2000_MYR + (delta_days / DAYS_PER_MYR)


def _ecliptic_lon(t: Time) -> float:
    pos, _ = get_body_barycentric_posvel("earth", t)
    coord = SkyCoord(pos, frame="icrs", representation_type="cartesian")
    return float(coord.heliocentricmeanecliptic.lon.deg)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def solar_timestamp(
    dt=None,
    scale: str = "utc",
    age_precision: int = 6,
    lon_precision: int = 4,
) -> str:
    """
    Return a solar timestamp string for a given moment.

    Parameters
    ----------
    dt : None | datetime | str | astropy.time.Time
        The moment to timestamp.
          None          -> current moment (default)
          datetime      -> UTC assumed unless tzinfo present
          str           -> ISO 8601, interpreted as `scale`
          astropy Time  -> used directly
    scale : str
        Timescale for string input: 'utc' (default) or 'tai'.
        Ignored for datetime and Time inputs.
    age_precision : int
        Decimal places for solar age in Myr. Default 6.
    lon_precision : int
        Decimal places for ecliptic longitude in degrees. Default 4.

    Returns
    -------
    str
        Solar timestamp in the form "{solar_age_Myr}:{ecliptic_lon_deg}"
        e.g. "4603.000017:127.4231"

    Ecliptic longitude convention
    -----------------------------
      ~  0 deg  autumnal equinox  (~Sep 22)
      ~ 90 deg  winter solstice   (~Dec 21)
      ~180 deg  vernal equinox    (~Mar 20)
      ~270 deg  summer solstice   (~Jun 21)
    """
    t = _parse_input(dt, scale)
    age = _solar_age_myr(t)
    lon = _ecliptic_lon(t)
    return f"{age:.{age_precision}f}:{lon:.{lon_precision}f}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        # No args: current moment
        print(solar_timestamp())

    elif len(sys.argv) == 2:
        # One arg: UTC datetime string
        print(solar_timestamp(sys.argv[1], scale="utc"))

    elif len(sys.argv) == 3:
        # Two args: datetime string + scale
        print(solar_timestamp(sys.argv[1], scale=sys.argv[2]))

    else:
        print(
            "Usage:\n"
            "  python solar_timestamp.py\n"
            "  python solar_timestamp.py '2024-03-15 14:30:00'\n"
            "  python solar_timestamp.py '1982-10-27 05:21:21' tai",
            file=sys.stderr,
        )
        sys.exit(1)
