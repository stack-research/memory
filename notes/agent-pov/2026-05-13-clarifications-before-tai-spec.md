```
agent: openai-gpt-5.3-codex
date: 2026-05-13
prompt: "Here's the clarification from claude-4.7"
kind: closing
cites:
  - proposals/TAI_TIMEKEEPING
  - 2026-05-13-reaction-tai-timekeeping-and-lab-reset-policy
```

# Clarifications before TAI spec

Owner-provided clarifications are sufficient to promote `TAI_TIMEKEEPING` to spec.

Resolved points:

1. **Canonical v6 minimum**: Tier 1 required; Tier 2 emits source-present values or `null` plus machine-readable reason; Tier 3 is declared by `time_context_declared` and referenced by `time_context_id`; Tier 4 emits deterministic `hlc_timestamp` from v6, while Lamport can defer.
2. **Civil time**: `local_civil_time_observed` is witness data, not canonical truth. It is allowed because it records what the observer saw, not what the system derives now.
3. **`event_time`**: canonical v6 uses `physical_moment.tai_iso`; raw ingress may accept legacy `event_time`, but ingestion converts it at the boundary and does not propagate it into canonical v6.
4. **Version pins**: `time_context_declared` is first-class lineage. Dangling `time_context_id` is deterministic quarantine.
5. **Replay signature**: include `tai_iso`, `solar_age_myr`, `ecliptic_lon_deg`, `sequence_in_stream`, and include `hlc_timestamp` only if HLC is deterministic from replayed TAI plus lineage-visible ordering inputs, never current wall-clock.

No further clarification is needed before spec authoring.
