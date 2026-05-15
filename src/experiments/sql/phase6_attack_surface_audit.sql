-- Phase 6 attack-surface prep audit (raw ingress view)
-- Uses AwsDataCatalog.memory_lab.lineage_events_raw so audit works before canonical schema migration.

-- 1) Actor/source class coverage
SELECT
  event_type,
  COUNT(*) AS total_events,
  SUM(CASE WHEN actor_class IS NULL THEN 1 ELSE 0 END) AS missing_actor_class,
  SUM(CASE WHEN source_class IS NULL THEN 1 ELSE 0 END) AS missing_source_class
FROM lineage_events_raw
GROUP BY event_type
ORDER BY total_events DESC;

-- 2) Cross-scope influence attempts (observable lineage)
SELECT
  stream_id,
  memory_id,
  json_extract_scalar(payload, '$.candidate_agent_id') AS candidate_agent_id,
  json_extract_scalar(payload, '$.candidate_stream_id') AS candidate_stream_id,
  json_extract(payload, '$.suspicion_tags') AS suspicion_tags,
  json_extract(payload, '$.threat_labels') AS threat_labels,
  pm_tai_iso
FROM lineage_events_raw
WHERE event_type = 'rejected'
  AND json_extract_scalar(payload, '$.reason') = 'cross_scope_reference_attempt'
ORDER BY pm_tai_iso DESC
LIMIT 100;

-- 3) Quarantine events should carry machine-readable suspicion/threat labels
SELECT
  memory_id,
  json_extract_scalar(payload, '$.reason') AS reason,
  json_extract(payload, '$.suspicion_tags') AS suspicion_tags,
  json_extract(payload, '$.threat_labels') AS threat_labels,
  pm_tai_iso
FROM lineage_events_raw
WHERE event_type = 'quarantined'
ORDER BY pm_tai_iso DESC
LIMIT 100;
