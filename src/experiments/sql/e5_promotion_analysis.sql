-- E5 Promotion Analysis Query Pack
-- Default table: memory_lab.memory_events

-- 1) Timeline for E5
SELECT
  event_time,
  event_type,
  memory_id,
  parent_event_id,
  json_extract_scalar(payload, '$.kind') AS kind,
  json_extract_scalar(payload, '$.claim') AS claim
FROM memory_lab.memory_events
WHERE stream_id = 'exp-e5'
ORDER BY event_time;

-- 2) Promotion gate decision snapshots
SELECT
  event_time,
  memory_id,
  CAST(json_extract_scalar(payload, '$.access_count') AS INTEGER) AS access_count,
  CAST(json_extract_scalar(payload, '$.context_variance') AS DOUBLE) AS context_variance,
  CAST(json_extract_scalar(payload, '$.promotion_eligible') AS BOOLEAN) AS promotion_eligible
FROM memory_lab.memory_events
WHERE stream_id = 'exp-e5'
  AND event_type = 'snapshotted'
ORDER BY event_time;

-- 3) Promotion events with derived lineage
SELECT
  event_time,
  memory_id AS semantic_memory_id,
  json_extract_scalar(payload, '$.claim') AS semantic_claim,
  CAST(json_extract_scalar(payload, '$.access_count') AS INTEGER) AS access_count,
  CAST(json_extract_scalar(payload, '$.context_variance') AS DOUBLE) AS context_variance,
  json_extract(payload, '$.derived_from') AS derived_from
FROM memory_lab.memory_events
WHERE stream_id = 'exp-e5'
  AND event_type = 'promoted'
ORDER BY event_time;

-- 4) Episodic linkage records created post-promotion
SELECT
  event_time,
  memory_id AS episodic_memory_id,
  json_extract_scalar(payload, '$.promotion_link') AS semantic_memory_id,
  json_extract_scalar(payload, '$.relation') AS relation,
  json_extract_scalar(payload, '$.status_after') AS status_after,
  parent_event_id
FROM memory_lab.memory_events
WHERE stream_id = 'exp-e5'
  AND event_type = 'mutated'
  AND json_extract_scalar(payload, '$.relation') = 'derived_from'
ORDER BY event_time;
