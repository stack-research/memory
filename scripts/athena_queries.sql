-- Replay checks: events per memory
SELECT memory_id, COUNT(*) AS event_count
FROM memory_events
GROUP BY memory_id
ORDER BY event_count DESC;

-- Drift proxy: confidence mutations over time
SELECT memory_id, COUNT(*) AS mutation_count
FROM memory_events
WHERE event_type = 'mutated'
GROUP BY memory_id
ORDER BY mutation_count DESC;

-- Poisoning spread proxy by source
SELECT source, COUNT(DISTINCT memory_id) AS affected_memories
FROM memory_events
WHERE event_type IN ('observed', 'mutated', 'promoted', 'quarantined')
GROUP BY source
ORDER BY affected_memories DESC;
