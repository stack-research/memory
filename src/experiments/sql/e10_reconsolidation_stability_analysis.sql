-- E10 Reconsolidation Stability Envelope Analysis
-- Default table: memory_lab.memory_events_v4

-- 1) Drift by mutation step
SELECT
  event_time,
  CAST(json_extract_scalar(payload, '$.step') AS INTEGER) AS step,
  json_extract_scalar(payload, '$.context') AS context,
  CAST(json_extract_scalar(payload, '$.drift.cosine_similarity_to_previous') AS DOUBLE) AS cosine_to_previous,
  CAST(json_extract_scalar(payload, '$.drift.cosine_similarity_to_base') AS DOUBLE) AS cosine_to_base
FROM memory_lab.memory_events_v4
WHERE stream_id = 'exp-e10'
  AND event_type = 'mutated'
ORDER BY event_time;

-- 2) Final stability summary
SELECT
  event_time,
  CAST(json_extract_scalar(payload, '$.steps') AS INTEGER) AS steps,
  CAST(json_extract_scalar(payload, '$.median_cosine_to_previous') AS DOUBLE) AS median_cosine_to_previous,
  CAST(json_extract_scalar(payload, '$.final_cosine_to_base') AS DOUBLE) AS final_cosine_to_base,
  CAST(json_extract_scalar(payload, '$.pass') AS BOOLEAN) AS pass
FROM memory_lab.memory_events_v4
WHERE stream_id = 'exp-e10'
  AND event_type = 'snapshotted'
  AND json_extract_scalar(payload, '$.snapshot_type') = 'reconsolidation_stability'
  AND json_extract_scalar(payload, '$.snapshot_stage') = 'final'
ORDER BY event_time DESC
LIMIT 20;

-- 3) Mutation lineage completeness (parent linkage)
SELECT
  COUNT(*) AS mutated_events,
  SUM(CASE WHEN parent_event_id IS NULL THEN 1 ELSE 0 END) AS missing_parent_event_id
FROM memory_lab.memory_events_v4
WHERE stream_id = 'exp-e10'
  AND event_type = 'mutated';
