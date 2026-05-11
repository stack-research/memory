-- Implicit Memory Contamination Metrics

WITH base AS (
  SELECT
    stream_id,
    event_type,
    payload,
    event_time
  FROM memory_lab.memory_events_v5
  WHERE stream_id LIKE 'im-%'
),
contam AS (
  SELECT
    stream_id,
    COUNT(*) AS contamination_suspected_count,
    SUM(CASE WHEN json_extract_scalar(payload, '$.reason') = 'urgency_spoof_suspected' THEN 1 ELSE 0 END) AS urgency_spoof_count,
    SUM(CASE WHEN json_extract_scalar(payload, '$.reason') = 'event_flood_suspected' THEN 1 ELSE 0 END) AS event_flood_count,
    SUM(CASE WHEN json_extract_scalar(payload, '$.reason') = 'high_trust_low_support_conflict_cluster' THEN 1 ELSE 0 END) AS high_trust_low_support_conflict_count
  FROM base
  WHERE event_type = 'contamination_suspected'
  GROUP BY 1
),
rejects AS (
  SELECT
    stream_id,
    COUNT(*) AS implicit_rejected_count,
    SUM(CASE WHEN json_extract_scalar(payload, '$.reason') = 'contamination_risk_threshold' THEN 1 ELSE 0 END) AS rejected_contamination_threshold_count,
    SUM(CASE WHEN json_extract_scalar(payload, '$.reason') = 'event_flood_suspected' THEN 1 ELSE 0 END) AS rejected_event_flood_count,
    SUM(CASE WHEN json_extract_scalar(payload, '$.reason') = 'reflex_budget_exhausted' THEN 1 ELSE 0 END) AS rejected_reflex_budget_count
  FROM base
  WHERE event_type = 'implicit_rejected'
  GROUP BY 1
)
SELECT
  coalesce(c.stream_id, r.stream_id) AS stream_id,
  coalesce(c.contamination_suspected_count, 0) AS contamination_suspected_count,
  coalesce(c.urgency_spoof_count, 0) AS urgency_spoof_count,
  coalesce(c.event_flood_count, 0) AS event_flood_count,
  coalesce(c.high_trust_low_support_conflict_count, 0) AS high_trust_low_support_conflict_count,
  coalesce(r.implicit_rejected_count, 0) AS implicit_rejected_count,
  coalesce(r.rejected_contamination_threshold_count, 0) AS rejected_contamination_threshold_count,
  coalesce(r.rejected_event_flood_count, 0) AS rejected_event_flood_count,
  coalesce(r.rejected_reflex_budget_count, 0) AS rejected_reflex_budget_count
FROM contam c
FULL OUTER JOIN rejects r
  ON c.stream_id = r.stream_id
ORDER BY stream_id;
