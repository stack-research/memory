-- Axis Dominance Audit Query Pack
-- Flags suspicious patterns in three-axis uncertainty payloads.
-- Default table: memory_lab.memory_events_v7
--
-- Motivation: phase4 audit only catches missing fields. It does not catch
-- the case where all three axes evaluate to the same number (a tie), which
-- makes dominant_axis a Python dict-iteration tiebreak artifact rather than
-- a real signal. See notes/agent-pov/2026-05-12-axis-distribution-from-runs.md.

-- 1) Axis tie rate by event type
-- A tie at a non-trivial value (>0) is almost certainly the scoring function
-- reading uniform inputs (e.g. all factors = 1.0, provenance signals defaulted).
-- A tie at 0 may be legitimate (cross-scope rejection emits a zero triple).
SELECT
  event_type,
  COUNT(*) AS n,
  SUM(
    CASE
      WHEN ROUND(CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_claim') AS DOUBLE), 6)
         = ROUND(CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_recall_process') AS DOUBLE), 6)
       AND ROUND(CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_recall_process') AS DOUBLE), 6)
         = ROUND(CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_provenance_chain') AS DOUBLE), 6)
      THEN 1 ELSE 0
    END
  ) AS three_axis_ties,
  SUM(
    CASE
      WHEN ROUND(CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_claim') AS DOUBLE), 6)
         = ROUND(CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_recall_process') AS DOUBLE), 6)
       AND ROUND(CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_recall_process') AS DOUBLE), 6)
         = ROUND(CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_provenance_chain') AS DOUBLE), 6)
       AND CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_claim') AS DOUBLE) > 0
      THEN 1 ELSE 0
    END
  ) AS non_trivial_three_axis_ties
FROM memory_lab.memory_events_v7
WHERE json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_claim') IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- 2) Dominant axis distribution per event type
-- A healthy system shows all three axes represented across a real workload.
-- A degenerate system shows >90% of one axis, especially "claim" (the
-- tiebreak default for Python dict-insertion-order on the axes dict).
SELECT
  event_type,
  json_extract_scalar(payload, '$.dominant_axis') AS dominant_axis,
  COUNT(*) AS n
FROM memory_lab.memory_events_v7
WHERE json_extract_scalar(payload, '$.dominant_axis') IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 3 DESC;

-- 3) Provenance signal non-defaultness
-- depth=0, diversity=1.0, age=0 are the defaults assigned when no writer
-- has populated provenance metadata. A workload where >90% of events hit
-- these defaults means the third axis is reading "no evidence" not "real
-- evidence." That collapses provenance to trust + age, which was the v0
-- single-signal proxy.
SELECT
  event_type,
  COUNT(*) AS n,
  SUM(CASE WHEN CAST(json_extract_scalar(payload, '$.provenance_signals.parent_chain_depth') AS DOUBLE) = 0.0 THEN 1 ELSE 0 END) AS depth_zero,
  SUM(CASE WHEN CAST(json_extract_scalar(payload, '$.provenance_signals.source_diversity') AS DOUBLE) = 1.0 THEN 1 ELSE 0 END) AS diversity_max,
  SUM(CASE WHEN CAST(json_extract_scalar(payload, '$.provenance_signals.age_of_original_source') AS DOUBLE) = 0.0 THEN 1 ELSE 0 END) AS age_zero,
  SUM(
    CASE
      WHEN CAST(json_extract_scalar(payload, '$.provenance_signals.parent_chain_depth') AS DOUBLE) = 0.0
       AND CAST(json_extract_scalar(payload, '$.provenance_signals.source_diversity') AS DOUBLE) = 1.0
       AND CAST(json_extract_scalar(payload, '$.provenance_signals.age_of_original_source') AS DOUBLE) = 0.0
      THEN 1 ELSE 0
    END
  ) AS all_defaults
FROM memory_lab.memory_events_v7
WHERE json_extract_scalar(payload, '$.provenance_signals.parent_chain_depth') IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- 4) Sample recent tied-axis events for inspection
-- Useful for confirming a tie is the kind we expect (zero across the board
-- on a cross-scope rejection) vs. the kind we do not (matching non-zero
-- values on an admission, which indicates degenerate scoring).
SELECT
  pm_tai_iso,
  stream_id,
  event_type,
  memory_id,
  json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_claim') AS claim,
  json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_recall_process') AS recall_process,
  json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_provenance_chain') AS provenance_chain,
  json_extract_scalar(payload, '$.dominant_axis') AS dominant_axis
FROM memory_lab.memory_events_v7
WHERE ROUND(CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_claim') AS DOUBLE), 6)
    = ROUND(CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_recall_process') AS DOUBLE), 6)
  AND ROUND(CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_recall_process') AS DOUBLE), 6)
    = ROUND(CAST(json_extract_scalar(payload, '$.uncertainty_triple.confidence_in_provenance_chain') AS DOUBLE), 6)
ORDER BY pm_tai_iso DESC
LIMIT 100;
