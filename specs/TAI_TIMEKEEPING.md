# TAI_TIMEKEEPING

Status: Adopted spec, implementation pending
Version: v1.2
Promoted from: `notes/agent-pov/proposals/TAI_TIMEKEEPING.md`
Promotion date: 2026-05-13

## Changelog

- **v1.2 (2026-05-13)**: amendment closing seven ambiguities surfaced by cross-substrate review (gpt-5.5). Specified the `time_context_id` hash preimage (no circularity), resolved the genesis/declaration bootstrap ordering, made absent-prone Tier 1 fields required-nullable with closed reason enums, pinned `kulkarni_2014` as the v1 HLC default, specified UTC-derived basis for Tier 2 civil convenience fields, added ephemeris-data pinning and fallback discipline for `DE440`, and added an `AGENTS.md` reconciliation item to the implementation checklist. No fields removed; v1.1 implementations migrate to v1.2 by clarifying behaviors that were ambiguous, not by changing data shapes.
- **v1.1 (2026-05-13)**: amendment closing eight gaps surfaced by internal review. Tightened `time_context_id` determinism (removed escape hatch), closed the Tier 2 null-reason enum, pinned v1 defaults for `solar_age_anchor` and `ephemeris_id`, scoped HLC values to implementation lineage via `time_context_declared`, specified `sequence_in_stream` reset semantics at v5→v6 cutover, added a Genesis event subsection (§10.1), and added a falsification hook for `time_context_id` determinism. No behavioral fields removed; v1.0 implementations migrate cleanly to v1.1 by tightening, not rewriting.
- **v1.0 (2026-05-13)**: initial adopted spec promoted from proposal.

## Implementation checklist (v1)

- [ ] Add a timekeeping module that produces deterministic `physical_moment` values from an explicit input moment; no default current wall-clock in replay paths.
- [ ] Stop defaulting `src/explicit_memory/provenance.py::compute_chain_signals` `computed_at` to `datetime.utcnow()`; require a replayed TAI-derived timestamp from the loop tick or caller.
- [ ] Add `time_context_declared` lineage events and deterministic `time_context_id` references.
- [ ] Treat dangling `time_context_id` as deterministic quarantine.
- [ ] Add v6 canonical lineage schema/table with `physical_moment` and first-class TAI/solar-coordinate columns.
- [ ] Accept legacy `event_time` only at raw ingress boundaries; convert at the door and do not propagate it into canonical v6.
- [ ] Emit `sequence_in_stream` and deterministic `hlc_timestamp` on v6 events.
- [ ] Add replay signature support for the required deterministic time fields.
- [ ] Add falsification tests for UTC/TAI round-trip, leap-second crossing, wall-clock drift replay, ecliptic continuity, solar-age monotonicity, HLC replay determinism, and `time_context_id` determinism.
- [ ] Record v5 -> v6 cutover as lineage: a v5 boundary event and a v6 genesis event per §10.1.
- [ ] Pin v1 defaults for `solar_age_anchor` (4603.0), `ephemeris_id` (`DE440`), and `hlc_variant` (`kulkarni_2014`) in the initial `time_context_declared` event.
- [ ] Pin ephemeris data files alongside the library version pin (e.g. JPL kernel hash) so `ecliptic_lon_deg` is replay-reproducible across environments.
- [ ] Update `AGENTS.md` at v6 cutover: change canonical table reference from v5 to v6, replace `event_time` in the required envelope with `physical_moment`, and lift "no current wall-clock influence on replay outputs" into the non-negotiable invariants list.

## 1) Purpose

Refactor lab timekeeping away from UTC/Gregorian as canonical lineage time and onto TAI plus explicit physical and logical time coordinates.

The immediate defect is replay nondeterminism: code paths such as `compute_chain_signals` use current wall-clock defaults, so two replays of the same logical event can emit different payloads. The larger defect is representational: UTC and Gregorian dates are civil conventions being treated as if they were the physical time axis of lineage.

This spec makes canonical time explicit, replayable, and auditable.

## 2) Scope

In scope:

- TAI as canonical physical counting mechanism.
- A `physical_moment` payload block on canonical v6 events.
- `time_context_declared` events for version pins and transform environment.
- v6 canonical lineage table beginning at an explicit genesis/cutover boundary.
- Boundary conversion from legacy UTC/Gregorian fields.
- Deterministic logical ordering fields (`sequence_in_stream`, `hlc_timestamp`).
- Falsification tests that prove determinism and monotonicity properties.

Out of scope for v1:

- Migrating v5 history into v6. v5 remains historical record.
- Stellar or galactic coordinate frames.
- Relativistic corrections beyond the chosen astropy/ephemeris path.
- Lamport timestamp as a separate required field. HLC is required; Lamport may be added later if needed.

## 3) Time model

The spec separates two dimensions:

1. **Mechanism**: TAI, not UTC. TAI counts uninterrupted SI seconds and has no leap seconds.
2. **Coordinate**: solar age plus Earth's heliocentric ecliptic longitude. This locates a moment in solar history rather than in civil calendar convention.

TAI is not free of social choice: its epoch and realization are conventions. The point is narrower: TAI has a physical counting mechanism without UTC's committee-inserted discontinuities.

## 4) Canonical v6 event time contract

Canonical v6 events use `physical_moment.tai_iso` as the physical time anchor.

Legacy `event_time` rules:

- Raw ingress may accept `event_time` as untrusted boundary input.
- Ingestion converts it immediately into `physical_moment` using a declared `time_context_id`.
- The conversion emits deterministic lineage describing the source field, conversion context, and any fallback/quarantine reason.
- Canonical v6 does not propagate `event_time` as a load-bearing field.

If a v6 event cannot produce a valid `physical_moment.tai_iso`, it must be quarantined with a deterministic reason.

## 5) `physical_moment` block

Every canonical v6 event must carry `physical_moment`.

### 5.1 Tier 1: required on every event

Tier 1 splits into two sub-classes. All Tier 1 fields are present on every v6 event; the difference is whether the field's value can be `null`.

**Tier 1a: required, non-nullable.** Absence is quarantine, not null.

- `tai_iso`: TAI timestamp. This is the physical-time anchor. Absence → quarantine `missing_physical_moment`.
- `solar_age_myr`: solar age in megayears using the declared `solar_age_anchor`.
- `ecliptic_lon_deg`: Earth's heliocentric ecliptic longitude in degrees using the declared ephemeris.
- `sequence_in_stream`: monotonic per-stream sequence number.
- `hlc_timestamp`: hybrid logical clock value computed under the deterministic contract in section 8.
- `time_context_id`: reference to a `time_context_declared` event resolvable in lineage (see §10.1 for bootstrap semantics).

**Tier 1b: required, nullable with closed reason enum.** The field is always present on the event; its value may be `null` only when accompanied by a machine-readable reason in `physical_moment.tier1b_null_reasons`.

- `local_civil_time_observed`: witness data for what the observer or source reported seeing locally.
- `tz_offset_seconds`: offset reported with `local_civil_time_observed`.
- `ntp_state`: synchronization state observed at capture.

The v1 Tier 1b null-reason enum is closed:

- `machine_origin` — event originated from a process with no observer-perceived civil time (purely TAI-driven).
- `observer_did_not_report` — observer was present but did not capture civil time / tz / NTP state at the moment.
- `ntp_unavailable` — applicable only to `ntp_state`; the host had no NTP source configured.
- `tz_undeclared` — applicable only to `tz_offset_seconds`; civil time was reported without a timezone offset.

Adding a Tier 1b null reason requires a spec amendment, same discipline as Tier 2. An unrecognized reason triggers `invalid_tier1b_null_reason` quarantine.

`local_civil_time_observed` is not canonical truth. It is witness data. It records what an observer or source saw at capture time, not what the system would compute now from TAI and current timezone rules.

### 5.2 Tier 2: computed/source-present fields

Tier 2 fields are deterministically derivable from Tier 1 plus Tier 3, or are external time representations useful for cross-checking.

Required handling:

- If the value is present in the source or computed by the active timekeeping module, emit it.
- If it is not present and not computed, emit `null` plus a machine-readable reason in `physical_moment.tier2_null_reasons`.
- Do not fabricate values from silent defaults.

Tier 2 fields:

- `utc_iso`
- `leap_second_pending`
- `gps_time`
- `tt_iso`
- `sidereal_time`
- `lunar_age_days`
- `day_of_year` — UTC-derived from `tai_iso` via the declared leap-second table. Implementations may additionally emit `day_of_year_local` derived from `local_civil_time_observed` if the latter is non-null; in that case both fields are emitted and tagged distinctly. The unqualified `day_of_year` is always UTC-derived.
- `iso_week_date` — UTC-derived under the same rule as `day_of_year`. An optional `iso_week_date_local` may be emitted alongside if `local_civil_time_observed` is non-null.

The v1 null-reason enum is closed:

- `source_absent`
- `calculator_unavailable`
- `time_context_missing`
- `unsupported_scale`
- `ephemeris_unavailable`

Adding a reason requires a spec amendment, recorded as a lineage-visible amendment event. Implementations must not emit ad-hoc reason strings; an unrecognized reason is itself a quarantine condition (`invalid_tier2_null_reason`, added to the §7 enum).

### 5.3 Tier 3: version pins via `time_context_id`

Tier 3 values are not repeated inline on every event unless implementation chooses to denormalize. The canonical contract is a lineage event named `time_context_declared` and a `time_context_id` reference from each event.

A dangling `time_context_id` is deterministic quarantine with reason:

- `dangling_time_context_id`

### 5.4 Tier 4: logical/causal time

`hlc_timestamp` is required from v6 onward, even in single-node operation.

`lamport_timestamp` is optional in v1 because HLC covers the forward-compatible causal-order need.

## 6) `time_context_declared` event

Add lineage event type:

- `time_context_declared`

Required payload fields:

- `time_context_id`
- `declared_at_tai_iso`
- `tzdata_version`
- `bipm_tai_realization`
- `ephemeris_id`
- `ephemeris_data_hash` (nullable; see §6.1)
- `leap_second_table_version`
- `solar_age_anchor`
- `timekeeping_library`
- `timekeeping_library_version`
- `hlc_variant`
- `calculator_config_hash`
- `fallback_reason` nullable

`time_context_id` must be deterministic from a canonical (sorted-key, separator-tight JSON) serialization of the **content fields** of the `time_context_declared` payload. The hash preimage is exactly the following subset, no more and no less:

- `tzdata_version`
- `bipm_tai_realization`
- `ephemeris_id`
- `ephemeris_data_hash` (see §6.1)
- `leap_second_table_version`
- `solar_age_anchor`
- `timekeeping_library`
- `timekeeping_library_version`
- `hlc_variant`
- `calculator_config_hash`

The preimage explicitly **excludes** `time_context_id` itself (would be circular), `declared_at_tai_iso` (records *when* the declaration was emitted, not *what* the context is), and `fallback_reason` (records *why* the declaration was needed, not what the context is). Two declarations with identical content fields but different `declared_at_tai_iso` or `fallback_reason` produce identical `time_context_id` values; the second is idempotent re-declaration of the same context, not a new context.

The id is computed by the emitter and verifiable by any reader. A `time_context_id` that does not match its own content-field hash is quarantined with `nondeterministic_time_context_id`.

If a process changes any content field, it must emit a new `time_context_declared` event and reference the new id on subsequent events.

### 6.1 v1 pinned defaults

The initial v6 `time_context_declared` event must use:

- `solar_age_anchor`: `4603.0` (megayears, matching `SOLAR_AGE_AT_J2000_MYR` in `notes/solar_time/solar_timestamp.py`; sources Bonanno & Fröhlich 2015, Connelly et al. 2012).
- `ephemeris_id`: `DE440` (NASA JPL, current best as of 2026-05-13). If `DE440` is unavailable at runtime (kernel not downloaded, package missing), the implementation may declare a fallback ephemeris id with `fallback_reason = "de440_unavailable"`. Falling back changes `time_context_id` and is therefore visible to replay; events emitted under fallback are auditable as such.
- `ephemeris_data_hash`: a content hash (e.g. SHA-256) of the ephemeris kernel file(s) actually loaded, not just the kernel name. `DE440` and `DE440s` are different kernels; the same kernel name on different astropy releases may bundle different precomputed slices. Pinning the data hash protects against silent ephemeris drift across environments. If the implementation cannot compute the hash, emit `null` with `fallback_reason` reflecting why.
- `hlc_variant`: `kulkarni_2014` is the v1 default. The variant string refers to the algorithm in Kulkarni et al. 2014 (*Logical Physical Clocks*); a v1-compliant implementation uses that algorithm with TAI-from-`physical_moment` as the physical-time input. Other variants are allowed but must declare conformance contracts in their own future spec; cross-variant `hlc_timestamp` comparisons are not defined.
- `timekeeping_library` and `timekeeping_library_version`: implementation choice, declared verbatim. The lineage records what was used; the spec does not pin a specific library.

Changing any content field later is a `time_context_declared` event with the new value(s) and a new `time_context_id`.

### 6.2 Bootstrap semantics

`time_context_declared` events are themselves canonical v6 events and therefore carry a `physical_moment` block. Their `time_context_id` field is **self-referential**: it equals the id that this event declares. Self-reference is well-defined because the hash preimage excludes `time_context_id`, so the id is computable from content fields alone with no circularity.

The first `time_context_declared` event in v6 establishes the initial context for the canonical table. The genesis event (§10.1) references this id.

"Precede or accompany" in §10.1 means resolvable in lineage by the time replay reaches the referencing event. Concretely:

- A `time_context_declared` event whose `tai_iso` is ≤ the referencing event's `tai_iso` and which is findable in the canonical table by the referencing event's emission moment is "preceding."
- A `time_context_declared` event emitted in the same atomic write batch (S3 multi-object PUT, Athena transaction, or equivalent atomic-commit unit declared by the ingestion layer) as the referencing event is "accompanying." The batch boundary is itself emitted as a lineage marker (`canonical_batch_committed`) so replay can resolve "same batch" deterministically.
- A `time_context_id` that resolves to no `time_context_declared` event under either rule, by the time replay reaches the referencing event, is quarantined with `dangling_time_context_id`.
- A `time_context_id` that resolves to a `time_context_declared` event in a partition or stream the referencing event cannot legitimately see (scope violation) is quarantined with `unresolvable_time_context_id`.

## 7) Boundary conversion and quarantine

UTC/Gregorian inputs are accepted only at the boundary.

Boundary conversion rules:

- Convert incoming civil/UTC values to TAI and `physical_moment` immediately.
- Preserve source-observed civil values only as witness data (`local_civil_time_observed`), not as canonical derived fields.
- Emit deterministic conversion metadata in lineage.
- Quarantine records that cannot be converted deterministically.

Required quarantine reasons:

- `missing_physical_moment`
- `invalid_tai_iso`
- `unconvertible_event_time`
- `ambiguous_local_civil_time`
- `dangling_time_context_id`
- `sequence_regression`
- `hlc_nondeterministic`
- `invalid_tier2_null_reason`
- `invalid_tier1b_null_reason`
- `nondeterministic_time_context_id`
- `malformed_genesis`
- `unresolvable_time_context_id`

## 8) HLC determinism contract

`hlc_timestamp` may enter replay signatures only if it is deterministic from lineage-visible inputs.

Required contract:

- HLC physical-time input is the event's replayed `physical_moment.tai_iso`, not current wall-clock.
- HLC logical component is computed from `sequence_in_stream` and observed prior events available in canonical lineage.
- The HLC implementation pattern is declared in `time_context_declared.hlc_variant` (see §6.1). HLC values are only meaningfully comparable across events that share the same `(timekeeping_library, timekeeping_library_version, hlc_variant)` triple — i.e. within an implementation lineage. Cross-implementation HLC comparisons are not defined by this spec.
- Replaying identical lineage under the same implementation must produce identical `hlc_timestamp` values.
- If the HLC implementation uses current wall-clock as a floor, `hlc_timestamp` must be excluded from replay signatures and the event must carry `hlc_signature_eligible = false` with reason `wall_clock_floor`.

The v1 target is to implement deterministic HLC and include it in signatures.

## 9) Replay signature contract

Replay signatures for v6 decision-bearing events include these time fields:

- `physical_moment.tai_iso`
- `physical_moment.solar_age_myr`
- `physical_moment.ecliptic_lon_deg`
- `physical_moment.sequence_in_stream`
- `physical_moment.hlc_timestamp`, only when `hlc_signature_eligible = true`

Replay signatures exclude these unless a specific decision explicitly declares dependency on them:

- `local_civil_time_observed`
- `tz_offset_seconds`
- `ntp_state`
- Tier 2 convenience fields
- Tier 3 version pins / `time_context_declared` payload fields

Changing the signature field set requires a lineage-visible schema/version event.

## 10) Canonical table transition

Create canonical table/version:

- From: `memory_lab.memory_events_v5`
- To: `memory_lab.memory_events_v6`

Transition rules:

- v5 remains untouched as historical record.
- v6 starts at a defined genesis moment.
- Emit a v5 boundary event (`canonical_table_boundary`) in v5 describing why the canonical table changed and the final v5 `sequence_in_stream` value.
- Emit a v6 genesis event in v6 per §10.1.
- Do not migrate v5 history into v6 in v1.

This repo is a lab. Under `AGENTS.md`, destructive resets of S3/Athena/Glue state are allowed when they accelerate schema discovery. Prefer reset plus clean replay over compatibility migration during lab phase, while still recording reset boundaries as lineage.

### 10.1 v6 genesis event

The first event in `memory_lab.memory_events_v6` for each stream must be of type `canonical_table_genesis`.

Required payload fields:

- `predecessor_table`: fully qualified predecessor canonical table (v1: `memory_lab.memory_events_v5`).
- `predecessor_boundary_event_id`: the `event_id` of the matching `canonical_table_boundary` event in the predecessor table.
- `genesis_reason`: machine-readable reason string from the closed enum `{schema_evolution, reset_and_replay, recovery, lab_phase_iteration}`.
- `time_context_id`: the active `time_context_id` at genesis. The corresponding `time_context_declared` event must precede or accompany the genesis event in v6 lineage per the resolution rules in §6.2. In practice the v6 bootstrap pattern is: one `time_context_declared` event and one `canonical_table_genesis` event emitted in the same atomic batch, declared and resolved together via the `canonical_batch_committed` marker.
- `schema_version`: the v6 canonical schema version string.

`sequence_in_stream` semantics across the cutover:

- The v5 `canonical_table_boundary` event carries the final v5 `sequence_in_stream` for the stream.
- The v6 `canonical_table_genesis` event carries `sequence_in_stream = 0`.
- Subsequent v6 events increment from 0 per stream.
- v5 and v6 sequences are not joined; the boundary event id is the cross-table link.

A v6 event that is not preceded in its stream by a `canonical_table_genesis` event, or whose genesis is malformed, is quarantined with reason `malformed_genesis`.

## 11) `heliotime` byproduct

The timekeeping implementation may be factored into a small OSS Python package named `heliotime` if the name is available.

Desired surface:

- `heliotime(dt=None, scale="utc")`
- inverse conversion
- `from_heliotime()` parser

The lineage field remains `physical_moment`; it is not named after the library. The library is a producer, not the spec vocabulary.

## 12) Falsification and acceptance tests

Must pass before marking implemented:

1. **Round-trip determinism**: for any moment `m`, `TAI(UTC(TAI(m))) == TAI(m)` to nanosecond precision across J2000 +/- 50 years.
2. **Leap-second crossing**: two events one TAI second apart across a UTC leap second produce monotonically increasing `tai_iso` and `solar_age_myr`.
3. **Replay invariance under wall-clock drift**: the same workload on the same TAI-tagged input emits identical `computed_at` and identical decision payloads across runs.
4. **Ecliptic longitude continuity**: `ecliptic_lon_deg` is continuous modulo 360 degrees across the supported accuracy window.
5. **Solar age monotonicity**: `solar_age_myr` strictly increases over positive TAI intervals.
6. **HLC replay determinism**: repeated replay from identical lineage produces identical `hlc_timestamp` values; no current wall-clock input is observable in the result.
7. **Dangling time context quarantine**: an event referencing an undeclared `time_context_id` is quarantined with `dangling_time_context_id`.
8. **No silent Tier 2 defaults**: absent Tier 2 inputs produce `null` plus reason from the closed enum, not fabricated values. An unrecognized reason string triggers `invalid_tier2_null_reason` quarantine.
9. **`time_context_id` determinism and preimage discipline**: two `time_context_declared` events with identical content fields (§6 preimage list) produce identical `time_context_id` values across replays and across processes, *regardless* of differences in `declared_at_tai_iso` or `fallback_reason`. A `time_context_id` that does not match its own content-field hash is quarantined with `nondeterministic_time_context_id`.
10. **Genesis well-formedness**: a v6 event without a preceding `canonical_table_genesis` in its stream, or with a malformed genesis payload, is quarantined with `malformed_genesis`.
11. **`sequence_in_stream` cutover semantics**: the v5 `canonical_table_boundary` event carries the final v5 sequence; the v6 `canonical_table_genesis` event carries sequence 0; subsequent v6 events increment from 0.
12. **Bootstrap self-reference**: the first `time_context_declared` event in v6 self-references (its `physical_moment.time_context_id` equals the id it declares). Replay must accept self-reference at bootstrap and must reject self-reference on non-declarative events (a regular v6 event cannot point its `time_context_id` at its own envelope).
13. **Same-batch resolution**: a `time_context_id` declared in the same `canonical_batch_committed` batch as the referencing event resolves successfully on replay; a `time_context_id` referencing a future batch quarantines with `dangling_time_context_id`.
14. **Tier 1b nullability**: when `local_civil_time_observed`, `tz_offset_seconds`, or `ntp_state` is `null`, a reason from the closed enum (§5.1) is present in `tier1b_null_reasons`. An unrecognized reason quarantines with `invalid_tier1b_null_reason`.

Suites must fail loudly. Silent defaults are spec violations.

## 13) Non-negotiable alignment

- Memory behavior can change; lineage history must not be rewritten.
- S3 Tables remains canonical lineage for the active canonical version.
- S3 Vectors remains rebuildable recall index, not source of truth.
- Do not auto-resolve contradictions.
- Do not let current wall-clock influence replay outputs.
- Keep rejection, quarantine, and fallback reasons machine-readable and deterministic.

## 14) Implementation planning note

Promotion of this spec is not implementation. Implementation should proceed in small auditable phases, but the lab-phase reset policy allows destructive schema resets when reset plus replay teaches faster than migration.
