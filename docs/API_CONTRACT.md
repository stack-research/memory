# Memory API Contract (v1)

Base path: `/v1`

## POST `/events`

Request body:
```json
{
  "memory_id": "m1",
  "sequence": 1,
  "event_type": "observed",
  "payload": {"claim": "The sky is blue.", "trust_score": 0.7},
  "source": "sensor-a"
}
```

Response body:
```json
{"inserted": true}
```

## POST `/retrieve`

Request body:
```json
{"query": "What color is the sky?", "top_k": 10}
```

Response body:
```json
{"results": [["m1", 0.78], ["m2", 0.55]]}
```

## GET `/beliefs/current`

Response body:
```json
{"beliefs": {"m1": {"memory_id": "m1", "claim": "The sky is blue."}}}
```

## GET `/memory/{id}/lineage`

Response body:
```json
{"lineage": [{"event_id": "e1", "event_type": "observed", "memory_id": "m1"}]}
```

## Error envelope

All non-2xx responses return:
```json
{"error": "message"}
```
