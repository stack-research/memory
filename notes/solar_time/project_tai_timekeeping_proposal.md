---
name: project_tai_timekeeping_proposal
description: User has proposed refactoring memory-lab timekeeping off UTC/Gregorian and onto TAI + solar-age-and-ecliptic-longitude, on the grounds that the current scheme contradicts the lab's own "trust is a prior, not truth" invariant.
type: project
originSessionId: 7a61facc-0b69-449f-a302-9950c16b6b0e
---
On 2026-05-13 the user proposed refactoring the memory lab's timekeeping conventions: use TAI (International Atomic Time) not UTC, and use solar age + ecliptic longitude as the physical coordinate, not the Gregorian calendar.

**Why:**
- The repo's stated invariants treat lineage as physical (append-only, replayable, observer-independent in the way reality is observer-independent).
- But the repo currently encodes time using UTC (leap seconds inserted by committee to track Earth's irregular rotation) and Gregorian dates (centuries of papal and political revision baked in).
- That is the exact category error `notes/MEMORY_!=_REALITY.md` warns against: treating a social-convention representation as if it were the underlying physical fact.
- TAI is uninterrupted SI seconds from caesium-133; the counting mechanism is physical. Its epoch (1958-01-01) is still a social choice — the user acknowledges this — but the mechanism is not.
- Solar age at birth + heliocentric ecliptic longitude locates a moment in solar history rather than human political time. This is the framing the user prefers for identity and for lineage time.

**How to apply:**
- Surfaces in the repo where this lands. The user explicitly rejected "out of scope" framing on 2026-05-13 — schema bump to v6 is in scope.
  1. `notes/agent-pov/` entry headers (`date:` field) and file names. Text-only, no code change.
  2. `notes/agent-pov/INDEX.md` "Date" column. Same.
  3. `src/explicit_memory/provenance.py::compute_chain_signals` — already uses `datetime.utcnow()` as a default for `computed_at`. Switch to TAI explicitly and pass it from the loop tick. Closes a determinism leak as a side effect.
  4. Add a `physical_moment` payload field on lineage events carrying TAI ISO + solar-age + ecliptic-longitude, alongside the existing `event_time`.
  5. **Bump canonical Iceberg table from `memory_events_v5` to `memory_events_v6`** with TAI and physical-coordinate columns as load-bearing fields. The v5 → v6 transition is itself a lineage event under the existing invariants (new table, new events going forward, v5 stays untouched as historical record). This is the right scope, not deferred work.
- Append-only invariant: v5 history stays. v6 begins from a defined moment. No rewrite.
- Treat Gregorian input as "legacy garbage accepted at the door, converted immediately, discarded" — user's framing, matches lab discipline at other boundaries.

**Parallel side-output: `spacetimestamp` Python OSS library.** The user named this on 2026-05-13 as the kind of unintended-but-useful artifact that justifies a lab existing ("example of something from a lab that wasn't intended. usually means we can keep our jobs another day"). The TAI + solar-age + ecliptic-longitude code from `solar_identity.py` is the seed. Track it as a parallel deliverable, not a subordinate task — lab byproducts often outlive the planned outputs.

This is a user-stated preference, not yet a promoted spec. Natural promotion path: user files `notes/agent-pov/proposals/TAI_TIMEKEEPING.md`, then proposal-to-spec-to-code arc as with prior promotions. Do not pre-promote. Do not pre-author.
