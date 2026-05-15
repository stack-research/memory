-- E9 Eligibility Under Contradiction Pressure Analysis
-- Default table: memory_lab.memory_events_v5

-- 1) Scenario snapshots and winner agreement
SELECT
  pm_tai_iso,
  json_extract_scalar(payload, '$.scenario') AS scenario,
  json_extract_scalar(payload, '$.axis') AS axis,
  json_extract_scalar(payload, '$.expected_winner') AS expected_winner,
  json_extract_scalar(payload, '$.observed_winner') AS observed_winner,
  CAST(json_extract_scalar(payload, '$.agreement') AS BOOLEAN) AS agreement,
  CAST(json_extract_scalar(payload, '$.expected_score_a') AS DOUBLE) AS expected_score_a,
  CAST(json_extract_scalar(payload, '$.expected_score_b') AS DOUBLE) AS expected_score_b
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e9'
  AND event_type = 'snapshotted'
  AND json_extract_scalar(payload, '$.snapshot_type') = 'eligibility_contradiction_pressure'
  AND json_extract_scalar(payload, '$.snapshot_stage') = 'per_scenario'
ORDER BY pm_tai_iso;

-- 2) Final agreement summary
SELECT
  pm_tai_iso,
  CAST(json_extract_scalar(payload, '$.agreement_rate') AS DOUBLE) AS agreement_rate,
  CAST(json_extract_scalar(payload, '$.scenario_count') AS INTEGER) AS scenario_count,
  CAST(json_extract_scalar(payload, '$.pass') AS BOOLEAN) AS pass
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e9'
  AND event_type = 'snapshotted'
  AND json_extract_scalar(payload, '$.snapshot_type') = 'eligibility_contradiction_pressure'
  AND json_extract_scalar(payload, '$.snapshot_stage') = 'final'
ORDER BY pm_tai_iso DESC
LIMIT 20;

-- 3) Rejection reason taxonomy in E9
SELECT
  json_extract_scalar(payload, '$.reason') AS reason,
  COUNT(*) AS n
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e9'
  AND event_type = 'rejected'
GROUP BY 1
ORDER BY n DESC;
