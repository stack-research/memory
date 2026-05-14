```
agent: openai-gpt-5.3-codex
date: 2026-05-13
prompt: "write that and your previous opinions on @notes/solar_time/project_tai_timekeeping_proposal.md as a reaction"
kind: reaction
cites:
  - notes/solar_time/project_tai_timekeeping_proposal.md
  - proposals/TAI_TIMEKEEPING
  - AGENTS.md
```

# Reaction: TAI timekeeping + lab reset posture

I support the proposal direction and the stronger lab posture.

## Position

- The core issue is real: wall-clock defaults (`computed_at`) break replay determinism and leak representation drift into lineage payloads.
- The proposed direction is right for this lab: TAI as canonical mechanism, with `physical_moment` as first-class in events.
- If we are optimizing for discovery, the schema bump should be treated as a live experiment surface, not a migration burden.

## What changed now

`AGENTS.md` now explicitly states lab-phase reset policy:
- destructive resets are allowed,
- prefer reset + replay over compatibility migration,
- record resets as lineage boundary events,
- cut new epochs/versions instead of rewriting surviving history.

That policy matches the TAI proposal's spirit and prevents "migration theater" from slowing epistemic progress.

## Execution bias (discovery over caution)

- Ship v6 quickly with `physical_moment` first-class.
- Keep legacy `event_time` only for compatibility at boundaries.
- Run hard falsification tests early (leap-second crossings, replay invariance, monotonicity checks).
- Accept resets as signal when schema assumptions fail.

## Net

For this repo, now is the correct time to be aggressive: break schema, replay, and learn. Save migration-heavy discipline for external-user v1.