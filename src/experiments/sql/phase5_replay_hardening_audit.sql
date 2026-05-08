-- Phase 5 Replay/Rebuild Hardening Audit
-- Default table: memory_lab.memory_events_v4

-- 1) E7 replay determinism by run_id: signatures should be stable
SELECT
  json_extract_scalar(payload, '$.run_id') AS run_id,
  COUNT(*) AS snapshot_count,
  COUNT(DISTINCT json_extract_scalar(payload, '$.state_signature')) AS distinct_state_signatures,
  MIN(CAST(json_extract_scalar(payload, '$.replay_equal') AS BOOLEAN)) AS all_replay_equal
FROM memory_lab.memory_events_v4
WHERE stream_id = 'exp-e7'
  AND event_type = 'snapshotted'
  AND json_extract_scalar(payload, '$.snapshot_type') = 'replay_rebuild'
GROUP BY 1
ORDER BY 1 DESC;

-- 2) E8 rebuild equivalence per run_id and tolerance
SELECT
  json_extract_scalar(payload, '$.run_id') AS run_id,
  COUNT(*) AS snapshot_count,
  MIN(CAST(json_extract_scalar(payload, '$.equivalent_within_tolerance') AS BOOLEAN)) AS all_equivalent,
  MAX(CAST(json_extract_scalar(payload, '$.top3_overlap') AS INTEGER)) AS max_top3_overlap,
  MAX(CAST(json_extract_scalar(payload, '$.tolerance') AS INTEGER)) AS tolerance
FROM memory_lab.memory_events_v4
WHERE stream_id = 'exp-e8'
  AND event_type = 'snapshotted'
  AND json_extract_scalar(payload, '$.snapshot_type') = 'vector_rebuild_equivalence'
GROUP BY 1
ORDER BY 1 DESC;

-- 3) Snapshot reproducibility metadata coverage
SELECT
  stream_id,
  COUNT(*) AS n,
  SUM(CASE WHEN json_extract_scalar(payload, '$.lineage_reader_backend') IS NULL THEN 1 ELSE 0 END) AS missing_reader,
  SUM(CASE WHEN json_extract_scalar(payload, '$.policy_id') IS NULL THEN 1 ELSE 0 END) AS missing_policy_id,
  SUM(CASE WHEN json_extract_scalar(payload, '$.policy_version') IS NULL THEN 1 ELSE 0 END) AS missing_policy_version,
  SUM(CASE WHEN json_extract_scalar(payload, '$.policy_effective_at') IS NULL THEN 1 ELSE 0 END) AS missing_policy_effective_at,
  SUM(CASE WHEN json_extract_scalar(payload, '$.event_schema_version') IS NULL THEN 1 ELSE 0 END) AS missing_schema_version,
  SUM(CASE WHEN json_extract_scalar(payload, '$.run_id') IS NULL THEN 1 ELSE 0 END) AS missing_run_id
FROM memory_lab.memory_events_v4
WHERE event_type = 'snapshotted'
  AND stream_id IN ('exp-e7', 'exp-e8')
  AND json_extract_scalar(payload, '$.snapshot_type') IN ('replay_rebuild', 'vector_rebuild_equivalence')
GROUP BY 1
ORDER BY 1;
