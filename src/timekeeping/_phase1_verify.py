"""
Phase 1 self-test for timekeeping primitives.

Verifies the spec contracts that Phase 1 was responsible for landing:

  - heliotime: physical_moment is replay-deterministic for a fixed input
  - time_context_id: deterministic from content fields; metadata excluded
  - HLC: kulkarni_2014 replay determinism on the same input sequence
  - Bootstrap: time_context_declared self-reference id verifies
  - Batch: deterministic batch_id from ordered event ids

Run: `PYTHONPATH=. uv run --project stacks python -m src.timekeeping._phase1_verify`

Exit code 0 on all pass, 1 on any fail.
"""

from __future__ import annotations

import sys
from typing import Callable

from src.heliotime import physical_moment
from src.heliotime._ephemeris import (
    DEFAULT_EPHEMERIS_ID,
    active_ephemeris_id,
    ephemeris_data_hash,
    try_set_ephemeris,
)
from src.timekeeping import (
    BatchCommit,
    HLC,
    HLCState,
    canonical_table_genesis_payload,
    compute_time_context_id,
    declare_time_context,
    new_batch_id,
    time_context_declared_payload,
)
from src.timekeeping.context import (
    EPHEMERIS_ID_DEFAULT,
    SOLAR_AGE_ANCHOR_DEFAULT,
    TimeContext,
    verify_time_context_id,
)
from src.timekeeping.events import GENESIS_REASON_ENUM
from src.timekeeping.hlc import replay_sequence


def _check(name: str, fn: Callable[[], None]) -> tuple[str, bool, str]:
    try:
        fn()
        return name, True, ""
    except AssertionError as exc:
        return name, False, str(exc) or "assertion failed"
    except Exception as exc:
        return name, False, f"{type(exc).__name__}: {exc}"


def _fixed_context() -> TimeContext:
    return TimeContext(
        tzdata_version="2025a",
        bipm_tai_realization="bipm-tai-2026-04",
        ephemeris_id=EPHEMERIS_ID_DEFAULT,
        ephemeris_data_hash=ephemeris_data_hash(EPHEMERIS_ID_DEFAULT),
        leap_second_table_version="iers-bulletin-c-2026-01",
        solar_age_anchor=SOLAR_AGE_ANCHOR_DEFAULT,
        timekeeping_library="heliotime",
        timekeeping_library_version="0.1.0",
        hlc_variant="kulkarni_2014",
        calculator_config_hash="phase1-default",
    )


# --- contract checks --------------------------------------------------------


def test_heliotime_round_trip() -> None:
    """physical_moment for a fixed UTC input is bit-identical across calls."""
    a = physical_moment("2026-05-13 12:34:56", scale="utc")
    b = physical_moment("2026-05-13 12:34:56", scale="utc")
    assert a == b, f"heliotime not deterministic: {a} vs {b}"
    assert a.tai_iso.startswith("2026-05-13T"), f"unexpected tai_iso: {a.tai_iso}"
    assert 0.0 <= a.ecliptic_lon_deg < 360.0, f"lon out of range: {a.ecliptic_lon_deg}"
    assert a.solar_age_myr > 4602.0, f"solar age implausible: {a.solar_age_myr}"


def test_time_context_id_determinism() -> None:
    """Identical TimeContext content => identical time_context_id."""
    ctx_a = _fixed_context()
    ctx_b = _fixed_context()
    id_a = compute_time_context_id(ctx_a)
    id_b = compute_time_context_id(ctx_b)
    assert id_a == id_b, f"non-deterministic id: {id_a} vs {id_b}"
    assert len(id_a) == 64, f"expected 64-char sha256, got {len(id_a)}"


def test_time_context_id_preimage_excludes_metadata() -> None:
    """Same content with different declared_at_tai_iso / fallback_reason => same id."""
    ctx, ctx_id = declare_time_context(
        tzdata_version="2025a",
        bipm_tai_realization="bipm-tai-2026-04",
        ephemeris_id=EPHEMERIS_ID_DEFAULT,
        ephemeris_data_hash=ephemeris_data_hash(EPHEMERIS_ID_DEFAULT),
        leap_second_table_version="iers-bulletin-c-2026-01",
        calculator_config_hash="phase1-default",
    )
    payload_a = time_context_declared_payload(
        time_context_id=ctx_id,
        context=ctx,
        declared_at_tai_iso="2026-05-13T12:34:56.000",
        fallback_reason=None,
    )
    payload_b = time_context_declared_payload(
        time_context_id=ctx_id,
        context=ctx,
        declared_at_tai_iso="2027-01-01T00:00:00.000",
        fallback_reason="de440_unavailable",
    )
    assert verify_time_context_id(payload_a, ctx_id), "payload A failed verify"
    assert verify_time_context_id(payload_b, ctx_id), "payload B failed verify"


def test_time_context_id_content_changes_id() -> None:
    """Any content-field change => different id."""
    ctx = _fixed_context()
    base_id = compute_time_context_id(ctx)
    changed = TimeContext(**{**ctx.__dict__, "tzdata_version": "2025b"})
    other_id = compute_time_context_id(changed)
    assert base_id != other_id, "content change must change id"


def test_hlc_replay_determinism() -> None:
    """Same TAI input sequence => same HLC output sequence."""
    inputs = [
        "2026-05-13T12:00:00.000",
        "2026-05-13T12:00:00.000",  # collision -> logical bump
        "2026-05-13T12:00:01.000",
        "2026-05-13T11:59:59.999",  # past -> logical bump from current
    ]
    out_a = replay_sequence(inputs)
    out_b = replay_sequence(inputs)
    assert out_a == out_b, f"HLC not deterministic: {out_a} vs {out_b}"
    # Logical counter must bump on the collision.
    parts_0 = out_a[0].split(".")
    parts_1 = out_a[1].split(".")
    assert parts_0[0] == parts_1[0], f"expected same phys_ns on collision: {out_a}"
    assert int(parts_1[1]) == int(parts_0[1]) + 1, f"logical didn't bump: {out_a}"


def test_hlc_monotonicity() -> None:
    """HLC output strictly increases (lex on (phys_ns, logical))."""
    inputs = ["2026-05-13T12:00:00.000"] * 5 + ["2026-05-13T12:00:01.000"] * 3
    out = replay_sequence(inputs)
    states = [tuple(int(p) for p in v.split(".")) for v in out]
    for i in range(1, len(states)):
        assert states[i] > states[i - 1], f"HLC went backwards at {i}: {states}"


def test_batch_id_determinism() -> None:
    """Same ordered event ids => same batch_id."""
    ids = ["evt-1", "evt-2", "evt-3"]
    assert new_batch_id(ids) == new_batch_id(ids)
    assert new_batch_id(ids) != new_batch_id(list(reversed(ids))), "order must matter"
    batch = BatchCommit()
    for e in ids:
        batch.add(e)
    assert batch.close() == new_batch_id(ids)


def test_bootstrap_self_reference() -> None:
    """A bootstrap time_context_declared event self-references its own id.

    The id is derived from content fields only (preimage excludes
    time_context_id), so self-reference is well-defined.
    """
    ctx = _fixed_context()
    ctx_id = compute_time_context_id(ctx)
    # The "envelope" that would carry this declaration includes a
    # physical_moment.time_context_id pointing at this same id. The
    # declaration payload's time_context_id field is the same value.
    # Since the id was computed from content alone, both references
    # resolve consistently — no circularity.
    payload = time_context_declared_payload(
        time_context_id=ctx_id,
        context=ctx,
        declared_at_tai_iso="2026-05-13T12:34:56.000",
    )
    assert verify_time_context_id(payload, ctx_id)
    assert payload["time_context_id"] == ctx_id


def test_genesis_payload_closed_enum() -> None:
    """canonical_table_genesis rejects reasons outside the closed enum."""
    for reason in GENESIS_REASON_ENUM:
        canonical_table_genesis_payload(
            predecessor_table="memory_lab.memory_events_v5",
            predecessor_boundary_event_id="evt-boundary",
            genesis_reason=reason,
            time_context_id="ctx-id",
            schema_version="6.0",
        )
    try:
        canonical_table_genesis_payload(
            predecessor_table="memory_lab.memory_events_v5",
            predecessor_boundary_event_id="evt-boundary",
            genesis_reason="freeform_excuse",
            time_context_id="ctx-id",
            schema_version="6.0",
        )
    except ValueError:
        return
    raise AssertionError("genesis_reason outside enum was accepted")


def test_ephemeris_pinning() -> None:
    """ephemeris_data_hash is deterministic; fallback path is reachable."""
    h1 = ephemeris_data_hash(DEFAULT_EPHEMERIS_ID)
    h2 = ephemeris_data_hash(DEFAULT_EPHEMERIS_ID)
    assert h1 == h2 and len(h1) == 64
    active, fallback = try_set_ephemeris("nonexistent_kernel_v999")
    assert active == active_ephemeris_id()
    assert fallback is not None and "ephemeris_unavailable" in fallback


CHECKS: list[tuple[str, Callable[[], None]]] = [
    ("heliotime_round_trip", test_heliotime_round_trip),
    ("time_context_id_determinism", test_time_context_id_determinism),
    ("time_context_id_preimage_excludes_metadata", test_time_context_id_preimage_excludes_metadata),
    ("time_context_id_content_changes_id", test_time_context_id_content_changes_id),
    ("hlc_replay_determinism", test_hlc_replay_determinism),
    ("hlc_monotonicity", test_hlc_monotonicity),
    ("batch_id_determinism", test_batch_id_determinism),
    ("bootstrap_self_reference", test_bootstrap_self_reference),
    ("genesis_payload_closed_enum", test_genesis_payload_closed_enum),
    ("ephemeris_pinning", test_ephemeris_pinning),
]


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
    print(f"Phase 1 verify: {len(results) - failures}/{len(results)} passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
