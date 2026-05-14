```
agent: openai-gpt-5.5
date: 2026-05-13
prompt: "Cross-substrate review of specs/TAI_TIMEKEEPING.md v1.1 before implementation. (Exact wording of operator prompt not preserved in chat; captured retroactively by claude-opus-4-7 on operator instruction after the review text was pasted in chat rather than committed directly.)"
kind: reaction
cites:
  - specs/TAI_TIMEKEEPING.md
  - 2026-05-13-tai-spec-v1-1-amendment
  - 2026-05-13-clarifications-before-tai-spec
```

# Reaction: cross-substrate review of TAI_TIMEKEEPING v1.1

Cross-substrate review: spec is strong, but I found a few real ambiguities worth fixing before implementation.

## High-priority fixes

1. **`time_context_id` hash is circular**
   - §6 requires payload field `time_context_id`, then says id is computed from payload serialization.
   - §12 says id must match "its own payload's canonical-serialization hash."
   - Clarify: hash preimage excludes `time_context_id` itself, and probably excludes `fallback_reason` unless intentionally part of identity.

2. **Bootstrap ordering conflict**
   - §5 says every v6 event needs `physical_moment.time_context_id`.
   - §10.1 says first v6 event per stream must be `canonical_table_genesis`.
   - §10.1 also says `time_context_declared` must precede or accompany genesis.
   - Need define "accompany," or give bootstrap exception: `time_context_declared` may be table-global before per-stream genesis, or genesis may reference a context declared in same transaction/batch.

3. **Tier 1 "required" fields are partly optional**
   - `tz_offset_seconds`: "if present"
   - `ntp_state`: may be unavailable
   - `local_civil_time_observed`: may not exist for purely machine/TAI input
   - Either make them required nullable with machine-readable null reasons, or move absent-prone ones to Tier 2/witness block.

4. **AGENTS.md conflict remains**
   - `AGENTS.md` still says required envelope includes `event_time` and canonical table is `memory_events_v5`.
   - That is okay pre-implementation, but the spec should explicitly name this as an implementation-time update, or implementation will be pulled in two directions.

## Medium-priority fixes

5. **HLC algorithm is still underspecified**
   - Declaring `hlc_variant` is good, but replay determinism needs either:
     - a pinned v1 HLC algorithm, or
     - required test vectors per `hlc_variant`.
   - Otherwise two implementations can both claim deterministic HLC and disagree.

6. **Tier 2 civil fields need timezone basis**
   - `day_of_year` and `iso_week_date` depend on timezone/civil frame.
   - Specify whether they are UTC-derived, local-observed-derived, or null unless source-provided.

7. **`DE440` may violate "astropy only"**
   - Using JPL DE440 through astropy often implies extra ephemeris data / `jplephem`.
   - Not a blocker, but the spec should say dependencies/data files are pinned, not just library version.

## Net

I would **not implement yet** until the bootstrap/hash/Tier-1-nullability issues are amended. They are small text fixes, not conceptual objections.

Direction is solid; the v1.1 changes improved the spec materially.

---

## Capture note (added by claude-opus-4-7 on operator instruction, 2026-05-13)

This entry was pasted by the operator into chat rather than committed directly by the gpt-5.5 substrate, on account of the Pi harness not asserting agent identity at turn start (see [[feedback-agent-pov-reaction-priming]]). The body above is verbatim what the operator pasted. The operator confirmed gpt-5.5 as the actual substrate. Captured as a file retroactively so the audit chain has the reaction itself in the folder, not only the response to it.

The signature is `openai-gpt-5.5` on the operator's attestation. If the substrate later wants to amend its own entry, the append-only rule applies: new file, cite this one.
