-- E10 Reconsolidation Stability Envelope Analysis
-- Default table: memory_lab.memory_events_v5

-- 1) Drift by mutation step
SELECT
  pm_tai_iso,
  CAST(json_extract_scalar(payload, '$.step') AS INTEGER) AS step,
  json_extract_scalar(payload, '$.context') AS context,
  CAST(json_extract_scalar(payload, '$.drift.cosine_similarity_to_previous') AS DOUBLE) AS cosine_to_previous,
  CAST(json_extract_scalar(payload, '$.drift.cosine_similarity_to_base') AS DOUBLE) AS cosine_to_base
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e10'
  AND event_type = 'mutated'
ORDER BY pm_tai_iso;

-- 2) Final stability summary
SELECT
  pm_tai_iso,
  CAST(json_extract_scalar(payload, '$.steps') AS INTEGER) AS steps,
  CAST(json_extract_scalar(payload, '$.median_cosine_to_previous') AS DOUBLE) AS median_cosine_to_previous,
  CAST(json_extract_scalar(payload, '$.final_cosine_to_base') AS DOUBLE) AS final_cosine_to_base,
  CAST(json_extract_scalar(payload, '$.pass') AS BOOLEAN) AS pass
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e10'
  AND event_type = 'snapshotted'
  AND json_extract_scalar(payload, '$.snapshot_type') = 'reconsolidation_stability'
  AND json_extract_scalar(payload, '$.snapshot_stage') = 'final'
ORDER BY pm_tai_iso DESC
LIMIT 20;

-- 3) Mutation lineage completeness (parent linkage)
SELECT
  COUNT(*) AS mutated_events,
  SUM(CASE WHEN parent_event_id IS NULL THEN 1 ELSE 0 END) AS missing_parent_event_id
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e10'
  AND event_type = 'mutated';
