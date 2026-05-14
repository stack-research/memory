"""
Kulkarni 2014 hybrid logical clock, deterministic on replay.

Spec §6.1 (hlc_variant default), §8 (determinism contract).

Reference: Kulkarni et al., "Logical Physical Clocks," 2014.

Determinism property: the physical-time input is the event's replayed
`physical_moment.tai_iso` (parsed to integer nanoseconds since TAI epoch
2000-01-01T00:00:00 for monotonic comparison), NOT current wall-clock.
The logical component increments on collision with the previous TAI
value. Same input sequence => same output sequence, byte-for-byte.

Encoded value format: "<phys_ns>.<logical>" where:
  - phys_ns is integer nanoseconds since TAI 2000-01-01T00:00:00
  - logical is a non-negative integer counter
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from astropy.time import Time


_TAI_EPOCH: Time = Time("2000-01-01 00:00:00", scale="tai", format="iso")
_NS_PER_DAY: int = 24 * 60 * 60 * 1_000_000_000


def _tai_iso_to_ns(tai_iso: str) -> int:
    """Convert a TAI ISO string to integer nanoseconds since TAI 2000-01-01.

    Format is auto-detected: astropy's `Time` accepts both ISO-with-T (isot)
    and ISO-with-space (iso). The TAI ISO strings we emit upstream may use
    either spelling depending on whether they came from `Time.tai.isot` or
    `Time.tai.iso`.
    """
    t = Time(tai_iso, scale="tai")
    delta_days = float(t.jd - _TAI_EPOCH.jd)
    return int(round(delta_days * _NS_PER_DAY))


@dataclass(frozen=True)
class HLCState:
    """Per-stream HLC state.

    `phys_ns`: largest TAI nanosecond value observed so far.
    `logical`: tiebreak counter when an incoming TAI <= `phys_ns`.
    """

    phys_ns: int
    logical: int


def encode(state: HLCState) -> str:
    return f"{state.phys_ns}.{state.logical}"


def decode(value: str) -> HLCState:
    phys_str, logical_str = value.split(".", 1)
    return HLCState(phys_ns=int(phys_str), logical=int(logical_str))


class HLC:
    """Kulkarni 2014 hybrid logical clock for a single stream.

    Per Kulkarni 2014 algorithm `Send` (used here on local emission;
    the lab is currently single-node, so `Recv` is not yet exercised
    and will be added when distribution lands):

        new_phys = max(prev_phys, event_phys)
        if new_phys == prev_phys:
            new_logical = prev_logical + 1
        else:
            new_logical = 0
        emit (new_phys, new_logical)
    """

    def __init__(self, initial: HLCState | None = None) -> None:
        self._state = initial or HLCState(phys_ns=0, logical=0)

    @property
    def state(self) -> HLCState:
        return self._state

    def step(self, tai_iso: str) -> HLCState:
        """Advance the clock by an event whose TAI is `tai_iso`."""
        event_ns = _tai_iso_to_ns(tai_iso)
        if event_ns > self._state.phys_ns:
            self._state = HLCState(phys_ns=event_ns, logical=0)
        else:
            self._state = HLCState(
                phys_ns=self._state.phys_ns,
                logical=self._state.logical + 1,
            )
        return self._state

    def fork(self) -> "HLC":
        """Return an independent HLC with the same current state."""
        return HLC(initial=replace(self._state))


def replay_sequence(tai_isos: list[str]) -> list[str]:
    """Deterministically compute HLC values for a sequence of TAI inputs.

    Pure function: same input list => same output list. No wall-clock read.
    Used by the falsification suite to verify replay determinism.
    """
    clock = HLC()
    return [encode(clock.step(t)) for t in tai_isos]
