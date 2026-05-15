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
  pm_tai_iso,
  stream_id,
  event_type,
  memory_id,
  json_extract_scalar(payload, '$.policy_id') AS policy_id,
  json_extract_scalar(payload, '$.policy_version') AS policy_version,
  json_extract_scalar(payload, '$.policy_effective_at') AS policy_effective_at,
  json_extract_scalar(payload, '$.reason') AS reason
FROM memory_lab.memory_events_v5
WHERE event_type IN ('recalled', 'rejected', 'quarantined')
ORDER BY pm_tai_iso DESC
LIMIT 100;

-- 4) Three-axis uncertainty payload coverage on required decision families
SELECT
  event_type,
  COUNT(*) AS n,
  SUM(CASE WHEN json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_claim') IS NULL THEN 1 ELSE 0 END) AS missing_claim_axis,
  SUM(CASE WHEN json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_recall_process') IS NULL THEN 1 ELSE 0 END) AS missing_recall_axis,
  SUM(CASE WHEN json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_provenance_chain') IS NULL THEN 1 ELSE 0 END) AS missing_provenance_axis,
  SUM(CASE WHEN json_extract_scalar(payload, '$.combined_score') IS NULL THEN 1 ELSE 0 END) AS missing_combined_score,
  SUM(CASE WHEN json_extract_scalar(payload, '$.dominant_axis') IS NULL THEN 1 ELSE 0 END) AS missing_dominant_axis,
  SUM(CASE WHEN json_extract_scalar(payload, '$.provenance_signals.parent_chain_depth') IS NULL THEN 1 ELSE 0 END) AS missing_parent_chain_depth,
  SUM(CASE WHEN json_extract_scalar(payload, '$.provenance_signals.source_diversity') IS NULL THEN 1 ELSE 0 END) AS missing_source_diversity,
  SUM(CASE WHEN json_extract_scalar(payload, '$.provenance_signals.age_of_original_source') IS NULL THEN 1 ELSE 0 END) AS missing_age_of_original_source
FROM memory_lab.memory_events_v5
WHERE event_type IN ('recalled', 'rejected', 'implicit_admitted', 'implicit_rejected')
GROUP BY 1
ORDER BY 1;
