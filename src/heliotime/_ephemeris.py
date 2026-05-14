"""
Ephemeris pinning for `time_context_declared.ephemeris_data_hash`.

Spec §6.1: the same `ephemeris_id` (e.g. `DE440`) can resolve to different
kernel bytes across astropy releases or environments. The data hash pins the
loaded kernel content, not just the name.

For v1 the implementation hashes the active astropy solar-system ephemeris
identifier plus the astropy version string. A future iteration may locate
and hash actual kernel files when available.
"""

from __future__ import annotations

import hashlib

import astropy
from astropy.coordinates import solar_system_ephemeris


DEFAULT_EPHEMERIS_ID: str = "DE440"


def active_ephemeris_id() -> str:
    return str(solar_system_ephemeris.get())


def ephemeris_data_hash(ephemeris_id: str | None = None) -> str:
    """Return a stable content hash of the active ephemeris configuration.

    Inputs that influence `ecliptic_lon_deg`:
      - ephemeris identifier (e.g. DE440, builtin)
      - astropy version string

    Two environments computing the same input moment with the same hash
    must produce the same `ecliptic_lon_deg`.
    """
    ident = ephemeris_id or active_ephemeris_id()
    material = f"{ident}|astropy=={astropy.__version__}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def try_set_ephemeris(ephemeris_id: str) -> tuple[str, str | None]:
    """Attempt to set the active astropy ephemeris.

    Returns `(active_id, fallback_reason)`. On success `fallback_reason` is
    None and `active_id == ephemeris_id`. On failure the active ephemeris
    is left unchanged and a deterministic fallback reason is returned.
    """
    try:
        solar_system_ephemeris.set(ephemeris_id)
        return solar_system_ephemeris.get(), None
    except Exception as exc:
        message = type(exc).__name__
        if ephemeris_id == DEFAULT_EPHEMERIS_ID:
            return active_ephemeris_id(), "de440_unavailable"
        return active_ephemeris_id(), f"ephemeris_unavailable:{message}"
