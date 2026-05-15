-- E5 Promotion Analysis Query Pack
-- Default table: memory_lab.memory_events_v5

-- 1) Timeline for E5
SELECT
  pm_tai_iso,
  event_type,
  memory_id,
  parent_event_id,
  json_extract_scalar(payload, '$.kind') AS kind,
  json_extract_scalar(payload, '$.claim') AS claim
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e5'
ORDER BY pm_tai_iso;

-- 2) Promotion gate decision snapshots
SELECT
  pm_tai_iso,
  memory_id,
  CAST(json_extract_scalar(payload, '$.access_count') AS INTEGER) AS access_count,
  CAST(json_extract_scalar(payload, '$.context_variance') AS DOUBLE) AS context_variance,
  CAST(json_extract_scalar(payload, '$.promotion_eligible') AS BOOLEAN) AS promotion_eligible
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e5'
  AND event_type = 'snapshotted'
ORDER BY pm_tai_iso;

-- 3) Promotion events with derived lineage
SELECT
  pm_tai_iso,
  memory_id AS semantic_memory_id,
  json_extract_scalar(payload, '$.claim') AS semantic_claim,
  CAST(json_extract_scalar(payload, '$.access_count') AS INTEGER) AS access_count,
  CAST(json_extract_scalar(payload, '$.context_variance') AS DOUBLE) AS context_variance,
  json_extract(payload, '$.derived_from') AS derived_from
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e5'
  AND event_type = 'promoted'
ORDER BY pm_tai_iso;

-- 4) Episodic linkage records created post-promotion
SELECT
  pm_tai_iso,
  memory_id AS episodic_memory_id,
  json_extract_scalar(payload, '$.promotion_link') AS semantic_memory_id,
  json_extract_scalar(payload, '$.relation') AS relation,
  json_extract_scalar(payload, '$.status_after') AS status_after,
  parent_event_id
FROM memory_lab.memory_events_v5
WHERE stream_id = 'exp-e5'
  AND event_type = 'mutated'
  AND json_extract_scalar(payload, '$.relation') = 'derived_from'
ORDER BY pm_tai_iso;
