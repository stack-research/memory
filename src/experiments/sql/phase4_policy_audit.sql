-- Phase 4 Policy Audit Query Pack
-- Verifies policy metadata and reason taxonomy for recalled/rejected/quarantined events.
-- Default table: memory_lab.memory_events_v5

-- 1) Coverage check: policy audit fields present by event type
SELECT
  event_type,
  COUNT(*) AS n,
  SUM(CASE WHEN json_extract_scalar(payload, '$.policy_id') IS NULL THEN 1 ELSE 0 END) AS missing_policy_id,
  SUM(CASE WHEN json_extract_scalar(payload, '$.policy_version') IS NULL THEN 1 ELSE 0 END) AS missing_policy_version,
  SUM(CASE WHEN json_extract_scalar(payload, '$.policy_effective_at') IS NULL THEN 1 ELSE 0 END) AS missing_policy_effective_at
FROM memory_lab.memory_events_v5
WHERE event_type IN ('recalled', 'rejected', 'quarantined')
GROUP BY 1
ORDER BY 1;

-- 2) Reason taxonomy check for rejected/quarantined
SELECT
  event_type,
  json_extract_scalar(payload, '$.reason') AS reason,
  COUNT(*) AS n
FROM memory_lab.memory_events_v5
WHERE event_type IN ('rejected', 'quarantined')
GROUP BY 1, 2
ORDER BY 1, 2;

-- 3) Spot-audit recent policy-tagged events
SELECT
  event_time,
  stream_id,
  event_type,
  memory_id,
  json_extract_scalar(payload, '$.policy_id') AS policy_id,
  json_extract_scalar(payload, '$.policy_version') AS policy_version,
  json_extract_scalar(payload, '$.policy_effective_at') AS policy_effective_at,
  json_extract_scalar(payload, '$.reason') AS reason
FROM memory_lab.memory_events_v5
WHERE event_type IN ('recalled', 'rejected', 'quarantined')
ORDER BY event_time DESC
LIMIT 100;
