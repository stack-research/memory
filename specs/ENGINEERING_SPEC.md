# Engineering Spec (v0)

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

Execution split:

- Hot path: S3 Vectors + S3 objects (event log and materialized memory state)
- Cold / analytic path: Athena + Glue Data Catalog + Parquet compacted history

Storage boundary rule:
- S3 Vectors bucket/index is retrieval-plane only.
- Parquet for analytics lives in separate standard S3 analytics storage (bucket or strictly isolated analytics prefix).
- Raw event objects remain source-of-truth storage.
- Vectors may influence recall; event/parquet lineage must explain recall.

---

## Core Components

### 1. Event Log (Append-Only)
Storage: S3 objects

Key namespace guidance:
- Use a replay-friendly path scheme that supports ordered stream replay and coarse time partitioning.
- Keep naming conventions stable for append-only ingestion, but defer exact prefix grammar until the namespace-design sprint.

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

Object namespace guidance:
- Separate active, quarantined, and deleted/tombstoned state at the prefix level.
- Keep state layout rebuild-friendly and auditable, but finalize exact object key templates during the namespace-design sprint.

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
vector_bucket: experimental-memory
index: memories-v1
```

Vector metadata:
- memory_id
- claim_hash
- source_event_id
- source_payload_hash
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

Lineage invariants (must hold):
1. Every vector maps to a source event object identity or source payload hash.
2. Every Parquet row is traceable to raw event identity.
3. Vector indexes can be dropped and rebuilt from durable event/parquet data.

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
- compact raw JSON events/state deltas into partitioned Parquet

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
- Athena for replay checks, drift analysis, poisoning spread, and decay curves
- Glue Data Catalog for schema and table metadata
- Parquet tables (partitioned by date/hour) generated from compaction jobs
- DynamoDB only if point lookup/query pain appears
- Python service (API + workers)

Compaction flow:
`events/raw/.../*.json` -> `events/parquet/dt=YYYY-MM-DD/hour=HH/*.parquet` -> Athena

Cold-path rule:
- raw event objects are the source of truth
- Athena reads compacted Parquet, not tiny raw JSON event objects

Biology mapping (design intuition, not literal mimicry):
- sensory trace / hippocampal recall surface -> S3 Vectors
- sleep consolidation -> compaction workers
- cortical long-term memory -> Parquet + Athena

Machine improvement:
- long-term memory remains auditable and replayable

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
