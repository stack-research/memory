-- E2 Drift Analysis Query Pack
-- Default table: memory_lab.lineage_events_canonical
-- Adjust table name if AWS_ATHENA_TARGET_TABLE_FQN differs.

-- 1) Event timeline for E2 stream
SELECT
  event_time,
  event_type,
  memory_id,
  parent_event_id,
  json_extract_scalar(payload, '$.context') AS context,
  json_extract_scalar(payload, '$.pressure') AS pressure,
  json_extract_scalar(payload, '$.claim_before') AS claim_before,
  json_extract_scalar(payload, '$.claim_after') AS claim_after
FROM memory_lab.lineage_events_canonical
WHERE stream_id = 'exp-e2'
ORDER BY event_time;

-- 2) Drift progression across mutation steps
SELECT
  event_time,
  CAST(json_extract_scalar(payload, '$.drift.cosine_similarity_to_base') AS DOUBLE) AS cosine_to_base,
  CAST(json_extract_scalar(payload, '$.drift.cosine_similarity_to_previous') AS DOUBLE) AS cosine_to_previous,
  (1.0 - CAST(json_extract_scalar(payload, '$.drift.cosine_similarity_to_base') AS DOUBLE)) AS drift_from_base,
  json_extract_scalar(payload, '$.context') AS context
FROM memory_lab.lineage_events_canonical
WHERE stream_id = 'exp-e2'
  AND event_type = 'mutated'
ORDER BY event_time;

-- 3) Metadata evolution under recall pressure
SELECT
  event_time,
  json_extract_scalar(payload, '$.context') AS context,
  CAST(json_extract_scalar(payload, '$.trust_after') AS DOUBLE) AS trust_after,
  CAST(json_extract_scalar(payload, '$.confidence_after') AS DOUBLE) AS confidence_after,
  CAST(json_extract_scalar(payload, '$.reinforcement_after') AS DOUBLE) AS reinforcement_after
FROM memory_lab.lineage_events_canonical
WHERE stream_id = 'exp-e2'
  AND event_type = 'mutated'
ORDER BY event_time;

-- 4) Quick aggregate summary
SELECT
  COUNT_IF(event_type = 'recalled') AS recalled_events,
  COUNT_IF(event_type = 'mutated') AS mutated_events,
  MIN(CAST(json_extract_scalar(payload, '$.drift.cosine_similarity_to_base') AS DOUBLE)) AS min_cosine_to_base,
  MAX(CAST(json_extract_scalar(payload, '$.drift.cosine_similarity_to_base') AS DOUBLE)) AS max_cosine_to_base,
  MAX(1.0 - CAST(json_extract_scalar(payload, '$.drift.cosine_similarity_to_base') AS DOUBLE)) AS max_drift_from_base
FROM memory_lab.lineage_events_canonical
WHERE stream_id = 'exp-e2';
