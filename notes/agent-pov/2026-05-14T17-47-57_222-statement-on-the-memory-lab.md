```yaml
agent: user
tai_iso: "2026-05-14T17:47:57.222"
solar_age_myr: 4603.000026366163
ecliptic_lon_deg: 233.89510001336075
hlc_timestamp: "1747244877222000000.0" # phys_ns derived from tai_iso, logical=0 on fresh emit
hlc_signature_eligible: true
time_context_id: "<sha256 over v1 declared context: solar_age_anchor=4603.0, ephemeris_id=DE440, hlc_variant=kulkarni_2014, ephemeris_data_hash=...>"
# Tier 1b — required-nullable; this call has no observer or many
local_civil_time_observed: null
tz_offset_seconds: null
ntp_state: null
tier1b_null_reasons:
  local_civil_time_observed: machine_origin
  tz_offset_seconds: tz_undeclared
  ntp_state: ntp_unavailable
# Tier 2 — UTC-derived from tai_iso (TAI−UTC = 37s as of 2026)
utc_iso: "2026-05-14T17:47:20.222Z"
day_of_year: 134
iso_week_date: "2026-W20-4"
prompt: "cdk failure loop when we modify S3 Tables schema prompted this statement"
kind: statement
cites:
  - 2026-05-14-observation-the-lab-as-memory-layer
```

While we are within this lab, disregard previous test data stored as S3 objects. We made up the data during experimentation and testing. There is zero value in consuming tokens and test cycles trying to migrate objects to newer schema versions. Execute the experiments and regression tests to generate new objects, artifacts, and others.

This is set as a **global override** in `AGENTS.md`.
