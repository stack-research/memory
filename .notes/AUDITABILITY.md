Athena fits well as the OLAP / audit / experiment analysis layer.

Split the system like this:
```
Hot path:
  S3 Vectors → similarity search
  S3 objects → memory state + event log
Cold / analytic path:
  Athena → replay checks, drift analysis, poisoning spread, decay curves
  Glue Data Catalog → schemas
  Parquet tables → compacted event/state history
```

Do not point Athena at millions of tiny JSON event files for serious use. Keep raw JSON append-only events as the source of truth, then run a compaction job:
```
events/raw/.../*.json
        ↓
events/parquet/dt=YYYY-MM-DD/hour=HH/*.parquet
        ↓
Athena
```

Athena is designed to query data in S3 with SQL, and partitioning by time is the normal way to reduce scan cost. Partition projection can avoid Glue partition churn for highly partitioned tables.  ￼

Suggested tables:

- memory_events
- memory_states
- memory_conflicts
- memory_lineage_edges
- memory_retrievals
- memory_scores
- memory_snapshots

Useful Athena queries:
```SQL
-- Which memories changed belief state most often?
SELECT memory_id, count(*) AS mutations
FROM memory_events
WHERE event_type = 'mutated'
GROUP BY memory_id
ORDER BY mutations DESC;
```
```SQL
-- Poisoning spread radius
SELECT source, count(DISTINCT memory_id) AS affected_memories
FROM memory_events
WHERE event_type IN ('observed', 'mutated', 'promoted')
  AND source = 'trusted_false_source'
GROUP BY source;
```
```SQL
-- Drift after repeated recall
SELECT memory_id, count(*) AS recalls, max(confidence) - min(confidence) AS confidence_delta
FROM memory_events
WHERE event_type = 'recalled'
GROUP BY memory_id;
```

Revised stack:
```
S3 event log        = source of truth
S3 Vectors          = recall index
S3 state objects    = materialized belief state
Athena              = audit + science bench
Glue                = schema/catalog
Lambda/Batch        = sleep + compaction workers
```

This makes the project more S3-native and should not force S3 Vectors to be a database.
