```
agent: claude-opus-4-7
date: 2026-05-13
prompt: "OK, I'm calling it. I need you to fix/improve the spec as step 1. Then we can review before dev plans."
kind: observation
cites:
  - proposals/TAI_TIMEKEEPING
  - 2026-05-13-clarifications-before-tai-spec
  - 2026-05-13-reaction-tai-timekeeping-and-lab-reset-policy
  - specs/TAI_TIMEKEEPING.md
```

# TAI_TIMEKEEPING spec amendment: v1.0 → v1.1

The user called for an amendment pass on the spec before implementation rather than letting reset policy absorb the gaps later. I closed eight items.

## What was amended, why

The v1.0 spec faithfully captured the proposal and gpt-5.5's five clarifications. The author also added three structural improvements I hadn't proposed: the `hlc_signature_eligible` flag with `wall_clock_floor` reason (graceful degradation path that holds the determinism line), a closed quarantine enum in §7, and promotion of "no wall-clock in replay outputs" to a non-negotiable invariant in §13. Those stay.

The eight amendments below close gaps I surfaced reading the v1.0 spec. None are blockers; all are cheaper to pin now than to fix after v6 data lands.

1. **`time_context_id` determinism, escape hatch removed (§6).** v1.0 said "deterministic from canonical serialization … or otherwise lineage-visible and stable across replay." The OR weakened the contract because "stable" is fuzzy in a way that's load-bearing — an implementation could use UUIDs and claim "stable because stored." v1.1 requires deterministic derivation from a canonical (sorted-key, separator-tight JSON) serialization. Two identical payloads must produce identical ids across replays and across processes. The id is computed by the emitter, not assigned externally.

2. **Tier 2 null-reason enum closed (§5.2).** v1.0 said "implementations may add reasons, but reasons must be deterministic strings." That's an open enum and creates audit drift. v1.1 closes the v1 enum. Adding a reason becomes a spec amendment recorded as a lineage-visible amendment event. Unrecognized reason strings now trigger `invalid_tier2_null_reason` quarantine.

3. **`solar_age_anchor` v1 default pinned (§6.1).** v1.0 listed `solar_age_anchor` in `time_context_declared` but didn't say which value v1 should use. Two implementations picking different anchors would produce different `solar_age_myr` values for the same `tai_iso`. v1.1 pins `4603.0` matching `notes/solar_time/solar_timestamp.py`. Future revisions move via `time_context_declared`.

4. **`ephemeris_id` v1 default pinned (§6.1).** v1.0 listed `ephemeris_id` but didn't pin v1's value. astropy's default ephemeris changes across releases, which affects `ecliptic_lon_deg`. v1.1 pins `DE440`. Same future-revision mechanism as #3.

5. **HLC variant declaration formalized (§6.1, §8).** v1.0 specified the determinism contract but not which HLC variant. Different variants produce different `hlc_timestamp` values for the same inputs, so the contract alone doesn't pin replay equivalence across implementations. Two paths were available: pin a specific variant for v1, or require the variant be declared and scope HLC values to the implementation lineage. I chose the second because the variant is a substrate-level choice the spec shouldn't lock in unilaterally. v1.1 adds `hlc_variant` to `time_context_declared` and explicitly scopes HLC comparability to `(timekeeping_library, timekeeping_library_version, hlc_variant)` triples. Cross-implementation HLC comparisons are not defined.

6. **`sequence_in_stream` cutover semantics specified (§10).** v1.0 didn't say what happens to sequence numbers at v5→v6 cutover. v1.1 pins: the v5 `canonical_table_boundary` event carries the final v5 sequence, the v6 `canonical_table_genesis` event carries sequence 0, subsequent v6 events increment from 0. v5 and v6 sequences are not joined; the boundary event id is the cross-table link.

7. **Genesis event subsection added (§10.1).** v1.0 mentioned the v6 genesis event in one sentence. Genesis is first-class lineage and deserves the same level of pinning as `time_context_declared`. v1.1 adds §10.1 with event type name (`canonical_table_genesis`), required payload fields, the closed `genesis_reason` enum (`schema_evolution | reset_and_replay | recovery | lab_phase_iteration`), and a quarantine rule (`malformed_genesis`) for events that lack a well-formed genesis predecessor in their stream.

8. **Falsification hooks added (§12).** Three new hooks: #9 `time_context_id` determinism (same payload → same id across replays/processes), #10 genesis well-formedness, #11 `sequence_in_stream` cutover semantics. v1.0 had eight hooks; v1.1 has eleven. Hook #8 also sharpened to test the closed-enum quarantine behavior, not just absence of fabrication.

## What I did not pin, on purpose

- **Specific HLC variant for v1.** Substrate decision; spec records the choice via `hlc_variant` rather than legislating it.
- **`timekeeping_library` and `timekeeping_library_version` default values.** v6 may or may not use `heliotime`; the field is mandatory but its v1 value is an implementation choice.
- **v5 cutover date or specific genesis trigger.** That's a deployment decision, not a spec decision.

## What v1.1 does not address

These remain open for v2 or later:

- Migration of v5 history into v6. Out of scope by the spec; reset policy absorbs.
- Cross-implementation HLC comparison semantics. Explicitly undefined; would need a separate mapping spec.
- Stellar/galactic coordinate frames, relativistic corrections beyond astropy's path, Lamport as a required field. All explicitly out of scope in v1.0; v1.1 doesn't change scope.

## Same-substrate caveat, still open

This amendment was written by me (Opus 4.7 under Claude Code) after I authored the proposal that became v1.0. The cross-substrate review point on this proposal's lifecycle was gpt-5.5 (under the Pi harness, self-labeled as codex 5.3 — see `feedback-agent-pov-reaction-priming`) producing the clarifications that informed v1.0. v1.1 has not been cross-substrate reviewed.

The 2026-05-12 dissent caveat therefore still applies to this amendment: a same-substrate read of a same-substrate amendment is the weakest form of review. Before implementation, a different agent should at minimum re-read §6.1, §10.1, and the new falsification hooks for shapes I might have missed. I am not the right agent to declare v1.1 sufficient.

## Net

v1.1 tightens v1.0 without rewriting it. No fields were removed. Implementations targeting v1.0 migrate to v1.1 by closing enums and pinning defaults, not by changing data shapes. The reset policy still applies if v1.1 turns out to have its own gaps — v7 is allowed, the spec is not load-bearing on being perfect, it is load-bearing on being explicit.

Ready for cross-substrate review before implementation planning begins.
