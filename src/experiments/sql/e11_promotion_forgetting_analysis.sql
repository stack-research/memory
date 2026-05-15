-- E11 Promotion-Forgetting Coupling Analysis
-- Default table: memory_lab.memory_events_v5

-- 1) Promotion gate decisions
SELECT
  pm_tai_iso,
  json_extract_scalar(payload, '$.cluster_id') AS cluster_id,
  CAST(json_extract_scalar(payload, '$.access_count') AS INTEGER) AS access_count,
  CAST(json_extract_scalar(payload, '$.context_variance') AS DOUBLE) AS context_variance,
  CAST(json_extract_scalar(payload, '$.promotion_eligible') AS BOOLEAN) AS promotion_eligible,
  CAST(json_extract_scalar(payload, '$.expected_promote') AS BOOLEAN) AS expected_promote
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e11'
  AND event_type = 'snapshotted'
  AND json_extract_scalar(payload, '$.snapshot_type') = 'promotion_gate'
ORDER BY pm_tai_iso;

-- 2) Promotion + derived linkage coverage
SELECT
  COUNT_IF(event_type = 'promoted') AS promoted_events,
  COUNT_IF(event_type = 'mutated' AND json_extract_scalar(payload, '$.relation') = 'derived_from') AS derived_link_events
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e11';

-- 3) Final coupling summary
SELECT
  pm_tai_iso,
  CAST(json_extract_scalar(payload, '$.promotion_precision') AS DOUBLE) AS promotion_precision,
  CAST(json_extract_scalar(payload, '$.episodic_drop_ratio') AS DOUBLE) AS episodic_drop_ratio,
  CAST(json_extract_scalar(payload, '$.semantic_gain') AS DOUBLE) AS semantic_gain,
  CAST(json_extract_scalar(payload, '$.pass') AS BOOLEAN) AS pass
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e11'
  AND event_type = 'snapshotted'
  AND json_extract_scalar(payload, '$.snapshot_type') = 'promotion_forgetting_coupling'
  AND json_extract_scalar(payload, '$.snapshot_stage') = 'final'
ORDER BY pm_tai_iso DESC
LIMIT 20;
