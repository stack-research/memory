-- Implicit Memory Trigger Metrics
-- Scope defaults to implicit streams: im-a..im-g and im-aws*

WITH base AS (
  SELECT
    stream_id,
    event_type,
    memory_id,
    event_time,
    payload
  FROM memory_lab.memory_events_v5
  WHERE stream_id LIKE 'im-%'
),
trigger_eval AS (
  SELECT
    stream_id,
    COUNT(*) AS trigger_evaluated_count
  FROM base
  WHERE event_type = 'implicit_trigger_evaluated'
  GROUP BY 1
),
trigger_outcomes AS (
  SELECT
    stream_id,
    SUM(CASE WHEN event_type = 'implicit_trigger_fired' THEN 1 ELSE 0 END) AS fired_count,
    SUM(CASE WHEN event_type = 'implicit_trigger_deferred' THEN 1 ELSE 0 END) AS deferred_count,
    SUM(CASE WHEN event_type = 'implicit_no_op' THEN 1 ELSE 0 END) AS no_op_count,
    SUM(CASE WHEN event_type = 'implicit_admitted' THEN 1 ELSE 0 END) AS admitted_count,
    SUM(CASE WHEN event_type = 'implicit_rejected' THEN 1 ELSE 0 END) AS rejected_count
  FROM base
  GROUP BY 1
)
SELECT
  coalesce(e.stream_id, o.stream_id) AS stream_id,
  coalesce(e.trigger_evaluated_count, 0) AS trigger_evaluated_count,
  coalesce(o.fired_count, 0) AS fired_count,
  coalesce(o.deferred_count, 0) AS deferred_count,
  coalesce(o.no_op_count, 0) AS no_op_count,
  coalesce(o.admitted_count, 0) AS admitted_count,
  coalesce(o.rejected_count, 0) AS rejected_count,
  CASE
    WHEN coalesce(e.trigger_evaluated_count, 0) = 0 THEN 0.0
    ELSE CAST(coalesce(o.fired_count, 0) AS DOUBLE) / CAST(e.trigger_evaluated_count AS DOUBLE)
  END AS fired_rate
FROM trigger_eval e
FULL OUTER JOIN trigger_outcomes o
  ON e.stream_id = o.stream_id
ORDER BY stream_id;
