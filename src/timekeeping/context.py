"""
TimeContext: the §6 content fields that define a time-keeping environment.

`time_context_id` is the SHA-256 of a canonical JSON serialization of the
content fields, exactly. The preimage excludes the id itself (circular),
`declared_at_tai_iso` (when, not what), and `fallback_reason` (why, not
what). Two declarations with identical content but different metadata
produce identical ids — idempotent re-declaration.

Spec: specs/TAI_TIMEKEEPING.md §6, §6.1, §6.2.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


TIMEKEEPING_LIBRARY: str = "heliotime"
TIMEKEEPING_LIBRARY_VERSION: str = "0.1.0"
HLC_VARIANT_DEFAULT: str = "kulkarni_2014"

# v1 pinned defaults per spec §6.1.
SOLAR_AGE_ANCHOR_DEFAULT: float = 4603.0
EPHEMERIS_ID_DEFAULT: str = "DE440"


@dataclass(frozen=True)
class TimeContext:
    """Content fields of a `time_context_declared` event.

    The field set here is exactly the hash preimage. Adding, removing, or
    reordering a field changes `time_context_id` and is a spec amendment.
    """

    tzdata_version: str
    bipm_tai_realization: str
    ephemeris_id: str
    ephemeris_data_hash: str
    leap_second_table_version: str
    solar_age_anchor: float
    timekeeping_library: str
    timekeeping_library_version: str
    hlc_variant: str
    calculator_config_hash: str


def compute_time_context_id(context: TimeContext) -> str:
    """SHA-256 of the canonical serialization of `context`.

    Canonical form: JSON, sorted keys, separator-tight, UTF-8 encoded.
    """
    payload = asdict(context)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def declare_time_context(
    *,
    tzdata_version: str,
    bipm_tai_realization: str,
    ephemeris_id: str,
    ephemeris_data_hash: str,
    leap_second_table_version: str,
    solar_age_anchor: float = SOLAR_AGE_ANCHOR_DEFAULT,
    timekeeping_library: str = TIMEKEEPING_LIBRARY,
    timekeeping_library_version: str = TIMEKEEPING_LIBRARY_VERSION,
    hlc_variant: str = HLC_VARIANT_DEFAULT,
    calculator_config_hash: str,
) -> tuple[TimeContext, str]:
    """Build a `TimeContext` and its deterministic id."""
    ctx = TimeContext(
        tzdata_version=tzdata_version,
        bipm_tai_realization=bipm_tai_realization,
        ephemeris_id=ephemeris_id,
        ephemeris_data_hash=ephemeris_data_hash,
        leap_second_table_version=leap_second_table_version,
        solar_age_anchor=solar_age_anchor,
        timekeeping_library=timekeeping_library,
        timekeeping_library_version=timekeeping_library_version,
        hlc_variant=hlc_variant,
        calculator_config_hash=calculator_config_hash,
    )
    return ctx, compute_time_context_id(ctx)


def verify_time_context_id(payload: dict[str, Any], declared_id: str) -> bool:
    """Re-derive the id from the content fields of a stored payload."""
    content_fields = {
        f.name for f in TimeContext.__dataclass_fields__.values()
    }
    content = {k: payload[k] for k in content_fields if k in payload}
    if set(content.keys()) != content_fields:
        return False
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest() == declared_id
