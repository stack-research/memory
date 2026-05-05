# Agentic Memory – Engineering Spec (v0)

## Goal
Build a minimal experimental memory system to test:
- belief formation vs retrieval
- trust-aware memory
- time-aware decay and promotion
- poisoning resistance
- auditability via lineage

---

## System Overview

Two-plane system:

1. Cognitive Plane (mutable)
2. Lineage Plane (immutable event log)

---

## Core Components

### 1. Event Log (Append-Only)
Storage: S3 objects

Key shape:
```
s3://agent-memory/events/
  dt=YYYY-MM-DD/
    agent={agent_id}/
      stream={stream_id}/
        {sequence}.{event_type}.json
```

Event body (simplified):
- event_id
- sequence
- event_type (observed | recalled | mutated | promoted | quarantined | deleted)
- memory_id
- payload
- source
- timestamp

Guarantees:
- append-only
- no updates
- tombstones for deletion
- prefix-order replay within a stream

---

### 2. Memory State Store
Storage: S3 memory-state objects + S3 Vectors

Object shape:
```
s3://agent-memory/memories/
  active/memory_id={memory_id}/state.json
  quarantined/memory_id={memory_id}/state.json
  deleted/memory_id={memory_id}/tombstone.json
```

State body:
- memory_id
- claim
- trust_score
- confidence
- decay_score
- last_recalled
- access_count
- status (active | quarantined | deleted)
- conflict links
- lineage pointers

Vector index:
```
vector_bucket: agent-memory-vectors
index: memories-v1
```

Vector metadata:
- memory_id
- claim_hash
- agent_id
- status
- kind
- source_trust
- confidence
- decay_score
- last_recalled_ts
- assertion_ts
- has_conflicts

S3 event objects are the source of truth. S3 memory-state objects and S3 Vectors records are rebuildable materializations.

Use S3 object metadata only for small routing fields. Put real state in JSON bodies. Object keys are the coarse index; S3 Vectors metadata filters are the retrieval-side filter.

---

### 3. Eligibility Engine

Function:
eligibility = relevance * trust * recency * reinforcement * consistency * safety

Inputs:
- query embedding
- memory metadata
- conflict set

Output:
- ranked eligible memories

---

### 4. Retrieval Engine

Steps:
1. embed query
2. retrieve top-k via S3 Vectors
3. apply eligibility filter
4. load needed memory-state objects from S3
5. return filtered set

---

### 5. Conflict Engine

Data model:
- memory_id_a
- memory_id_b
- relation (contradicts | supports)

Rules:
- never auto-resolve
- conflicts reduce eligibility score

---

### 6. Time Engine

Background worker:

- decay:
  decay_score = exp(-λ * time_since_last_reinforced)

- reinforcement:
  increment on recall

- pruning:
  mark low-score memories inactive (not deleted)

---

### 7. Promotion Engine

Rule:
if access_count > K and context_variance < ε:
    promote(memory)

Promotion:
- create new semantic memory
- link via derived_from
- keep original episodic traces

---

### 8. Sleep Worker (Batch Job)

Runs periodically.

Tasks:
- scan event prefixes
- replay high-value memories
- dedupe similar embeddings
- compress into summaries
- promote stable patterns
- quarantine conflicting clusters
- rewrite materialized memory-state objects
- upsert vectors
- write snapshots and manifests

---

### 9. Poisoning Detection

Signals:
- high trust + low support
- sudden influence spike
- conflict density increase

Action:
- quarantine memory
- reduce eligibility to zero

---

### 10. Audit API

Endpoints:

GET /beliefs/current
GET /beliefs/{time}
GET /memory/{id}/lineage
GET /diff/{t1}/{t2}

Must answer:
- what changed?
- why?
- source of change?

---

## Infrastructure

- S3 bucket for append-only event lineage
- S3 bucket/prefixes for materialized memory state, claims, snapshots, and manifests
- S3 Vectors for similarity search with metadata filters
- DynamoDB only if point lookup/query pain appears
- Python service (API + workers)

---

## Experiments

### E1: Trust vs Truth
- inject true low-trust vs false high-trust
- observe selection

### E2: Drift via Reconsolidation
- repeated recall under context shift

### E3: Time Reinforcement
- spaced vs single exposure

### E4: Conflict Handling
- persistent contradictions

### E5: Promotion
- episodic → semantic emergence

### E6: Poisoning
- trusted adversarial input

### E7: Replay Integrity
- rebuild state from log
- verify equality

---

## Metrics

- belief accuracy under conflict
- drift rate over repeated recall
- poisoning spread radius
- replay determinism
- promotion precision

---

## Non-Goals (v0)

- distributed system
- real-time scaling
- perfect truth inference
- full ontology reasoning

---

## Acceptance Criteria

1. System distinguishes belief vs retrieval
2. Conflicts persist without collapse
3. Poisoned memory can be quarantined
4. Replay reconstructs state exactly
5. Promotion produces stable abstractions

---

## Guiding Constraint

Cognitive plane may mutate.  
Lineage plane must not.
