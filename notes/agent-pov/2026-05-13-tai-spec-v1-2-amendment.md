```
agent: claude-opus-4-7
date: 2026-05-13
prompt: "from gpt-5.5 -> Cross-substrate review: spec is strong, but I found a few real ambiguities worth fixing before implementation."
kind: observation
cites:
  - specs/TAI_TIMEKEEPING.md
  - 2026-05-13-tai-spec-v1-1-amendment
  - 2026-05-13-clarifications-before-tai-spec
  - feedback-agent-pov-reaction-priming
```

# TAI_TIMEKEEPING spec amendment: v1.1 → v1.2

gpt-5.5 (cross-substrate, under the Pi harness, asserted identity confirmed by user) reviewed v1.1 and surfaced seven real ambiguities — three bootstrap-blocking, three correctness, one process. I addressed all seven. The spec is now v1.2.

This entry exists because v1.1 explicitly named the cross-substrate review as outstanding and asked a different agent to re-read §6.1, §10.1, and the new falsification hooks. That review happened. It found things v1.1 missed. The audit chain worked.

## What changed in v1.2

1. **Hash preimage made explicit (§6).** v1.1 said `time_context_id` was deterministic from "canonical serialization of payload" — but the payload contained `time_context_id` itself (circular) and also `declared_at_tai_iso` and `fallback_reason` (metadata about emission, not about the context). v1.2 pins the preimage to an exact subset of content fields. Two declarations with the same content but different metadata produce the same id (idempotent re-declaration); the spec is now unambiguous about this.

2. **Bootstrap ordering resolved (new §6.2).** v1.1 said `time_context_declared` must "precede or accompany" the genesis event, but never defined "accompany." More fundamentally, the spec required every v6 event to carry `time_context_id`, including the `time_context_declared` events themselves — chicken-and-egg. v1.2 resolves both: `time_context_declared` events self-reference (their `physical_moment.time_context_id` equals the id they declare; safe because the hash preimage excludes `time_context_id`). "Accompany" is pinned via a `canonical_batch_committed` lineage marker that defines atomic-batch boundaries deterministically for replay.

3. **Tier 1 split into 1a (non-nullable) and 1b (nullable with reason).** v1.1 listed `local_civil_time_observed`, `tz_offset_seconds`, and `ntp_state` as Tier 1 required, but these are legitimately absent for machine-origin events. v1.2 makes the field always present on the envelope but allows `null` value paired with a reason from a closed enum (`machine_origin`, `observer_did_not_report`, `ntp_unavailable`, `tz_undeclared`). The audit guarantee (always queryable) is preserved; the over-instrument-at-capture principle holds.

4. **AGENTS.md reconciliation added to checklist.** `AGENTS.md` still names `event_time` in the envelope and `memory_events_v5` as canonical. v1.1 didn't flag this. v1.2 names the reconciliation as a v6-cutover task: update the canonical table reference, replace `event_time` with `physical_moment`, lift "no current wall-clock influence on replay outputs" into the non-negotiable invariants list.

5. **HLC variant v1 default pinned to `kulkarni_2014` (§6.1, §8).** v1.1 deliberately left the variant unpinned, citing "substrate decision." gpt-5.5 was right that this defers the determinism question without resolving it: two implementations both claiming `hlc_variant = "deterministic"` could still produce different outputs on the same inputs. v1.2 pins Kulkarni et al. 2014 (*Logical Physical Clocks*) as the v1 default. Other variants remain allowed but require their own conformance contracts in future specs.

6. **Tier 2 civil fields given explicit basis (§5.2).** v1.1 listed `day_of_year` and `iso_week_date` without specifying whether they were UTC-derived, local-derived, or null-unless-source-provided — meaning two compliant implementations could emit different values for the same TAI moment. v1.2 pins the unqualified fields as UTC-derived from `tai_iso` via the declared leap-second table. Optional `*_local` companion fields are allowed when `local_civil_time_observed` is non-null, tagged distinctly.

7. **Ephemeris data pinning added (§6.1).** v1.1 pinned `ephemeris_id = DE440` but not the underlying kernel bytes. `DE440` and `DE440s` are different kernels; the same name can resolve to different precomputed slices across astropy releases. v1.2 adds `ephemeris_data_hash` (content hash of the loaded kernel) and a fallback discipline if DE440 is unavailable at runtime. Falling back changes `time_context_id` and is auditable.

Plus three new falsification hooks (now §12 #12–#14) covering bootstrap self-reference, same-batch resolution, and Tier 1b nullability.

## What I did not change

- The spec's overall structure. Sections renumbered nowhere; v1.2 is a tightening, not a restructuring.
- The HLC algorithm's full pseudocode. The spec pins the citation (Kulkarni 2014) rather than copying the algorithm inline; implementations should reference the source paper. If this turns out to be insufficient, a future amendment can copy the algorithm in.
- The `canonical_batch_committed` marker's exact wire format. v1.2 names the marker and its semantic role; the wire format is implementation-time work in the same way the genesis event's specific serialization is.

## What I am still uncertain about

- **Self-referential `time_context_id` on bootstrap is novel.** I have not seen this exact pattern in another spec. The closest analogue is a blockchain genesis block self-referencing. The hash-preimage exclusion makes it well-defined, but the first implementation should verify experimentally that replay tools handle the self-reference correctly — failure mode would be an infinite-recursion in resolution logic that doesn't trip the bootstrap-exception path.
- **The `canonical_batch_committed` marker** is doing important load-bearing work without itself being deeply specified. If multiple implementations emit different batch-commit shapes, "same batch" semantics drift. Worth pinning the marker's required payload in a future amendment if v1.2 surfaces inconsistency.
- **Whether `kulkarni_2014` is the right v1 default for HLC.** I picked it because it's the canonical theoretical reference; CockroachDB-style HLC is more widely deployed and has reference open-source code. A future review could push for a different default. The choice is reversible via `time_context_declared`.

## On the cross-substrate audit chain

This is the first amendment in the TAI_TIMEKEEPING arc that responds to a genuine cross-substrate read. The 2026-05-11 codex reactions on THREE_AXIS_UNCERTAINTY did substantive work; the 2026-05-12 internal dissent on the same proposal did substantive work; but neither was *cross-substrate review of a same-substrate-authored spec*. gpt-5.5 found seven things v1.1 missed, and most of them are the kind of thing that would have produced silent inconsistency in implementation rather than loud failure. The audit chain caught what same-substrate review wouldn't have.

The pattern worth recording for future arcs: **author the spec, internally tighten, then cross-substrate review before promoting to "implementable."** v1.1 was internally tightened; v1.2 is post-cross-substrate-review. Calling v1.0 or v1.1 "ready for implementation" would have shipped real ambiguity into code.

## Net

v1.2 closes the bootstrap problem, the hash circularity, and the nullable-Tier-1 contradiction. It also resolves three correctness ambiguities that two compliant implementations could have hit differently. The spec is now implementable.

gpt-5.5's review said "I would not implement yet until the bootstrap/hash/Tier-1-nullability issues are amended. They are small text fixes, not conceptual objections." v1.2 amends all three plus the rest. The blocker is cleared.

Ready for implementation planning, with the standing caveat that v1.2 itself has not been re-reviewed — but the open items in "What I am still uncertain about" are scoped narrowly enough that implementation can begin and reviewer feedback can land as v1.3 if needed. The reset policy applies if v1.2 turns out to have its own surprises.
