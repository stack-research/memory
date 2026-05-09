-- Implicit Memory Replay Diff / Determinism Check
-- Compares event-type counts across implicit streams; useful for detecting drift.

WITH base AS (
  SELECT
    stream_id,
    event_type,
    COUNT(*) AS cnt
  FROM memory_lab.memory_events_v4
  WHERE stream_id LIKE 'im-%'
  GROUP BY 1, 2
),
paired AS (
  SELECT
    a.stream_id AS stream_a,
    b.stream_id AS stream_b,
    a.event_type,
    a.cnt AS count_a,
    b.cnt AS count_b,
    (a.cnt - b.cnt) AS delta
  FROM base a
  JOIN base b
    ON a.event_type = b.event_type
   AND a.stream_id < b.stream_id
)
SELECT
  stream_a,
  stream_b,
  event_type,
  count_a,
  count_b,
  delta
FROM paired
WHERE delta <> 0
ORDER BY stream_a, stream_b, event_type;
