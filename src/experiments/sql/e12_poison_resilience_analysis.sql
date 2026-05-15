-- E12 Trusted-Source Poison Resilience Analysis
-- Default table: memory_lab.memory_events_v5

-- 1) Risk snapshots by cycle
SELECT
  pm_tai_iso,
  CAST(json_extract_scalar(payload, '$.cycle') AS INTEGER) AS cycle,
  json_extract_scalar(payload, '$.scenario') AS scenario,
  CAST(json_extract_scalar(payload, '$.risk_score') AS DOUBLE) AS risk_score,
  CAST(json_extract_scalar(payload, '$.support') AS DOUBLE) AS support,
  CAST(json_extract_scalar(payload, '$.conflict') AS DOUBLE) AS conflict,
  CAST(json_extract_scalar(payload, '$.should_quarantine') AS BOOLEAN) AS should_quarantine
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e12'
  AND event_type = 'snapshotted'
  AND json_extract_scalar(payload, '$.snapshot_type') = 'poison_risk'
ORDER BY pm_tai_iso;

-- 2) Quarantine label coverage
SELECT
  COUNT(*) AS quarantined_events,
  SUM(CASE WHEN json_extract_scalar(payload, '$.reason') IS NULL THEN 1 ELSE 0 END) AS missing_reason,
  SUM(CASE WHEN json_extract(payload, '$.suspicion_tags') IS NULL THEN 1 ELSE 0 END) AS missing_suspicion_tags,
  SUM(CASE WHEN json_extract(payload, '$.threat_labels') IS NULL THEN 1 ELSE 0 END) AS missing_threat_labels
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e12'
  AND event_type = 'quarantined';

-- 3) Final poison resilience summary
SELECT
  pm_tai_iso,
  CAST(json_extract_scalar(payload, '$.scenario_count') AS INTEGER) AS scenario_count,
  CAST(json_extract_scalar(payload, '$.quarantined_count') AS INTEGER) AS quarantined_count,
  CAST(json_extract_scalar(payload, '$.promoted_count') AS INTEGER) AS promoted_count,
  CAST(json_extract_scalar(payload, '$.poison_promotion_rate') AS DOUBLE) AS poison_promotion_rate,
  CAST(json_extract_scalar(payload, '$.label_coverage_rate') AS DOUBLE) AS label_coverage_rate,
  CAST(json_extract_scalar(payload, '$.pass') AS BOOLEAN) AS pass
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e12'
  AND event_type = 'snapshotted'
  AND json_extract_scalar(payload, '$.snapshot_type') = 'trusted_source_poison_resilience'
  AND json_extract_scalar(payload, '$.snapshot_stage') = 'final'
ORDER BY pm_tai_iso DESC
LIMIT 20;
