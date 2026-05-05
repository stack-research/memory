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
Storage: Postgres

Schema (simplified):
- id (uuid)
- event_type (observed | recalled | mutated | promoted | quarantined | deleted)
- memory_id
- payload (jsonb)
- source
- timestamp

Guarantees:
- append-only
- no updates
- tombstones for deletion

---

### 2. Memory State Store
Storage: Postgres + pgvector

Schema:
- memory_id
- embedding
- claim
- trust_score
- confidence
- decay_score
- last_recalled
- access_count
- status (active | quarantined | deleted)

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
2. retrieve top-k via vector index
3. apply eligibility filter
4. return filtered set

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
- replay high-value memories
- dedupe similar embeddings
- compress into summaries
- promote stable patterns
- quarantine conflicting clusters

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

- Postgres (core DB)
- pgvector (embedding search)
- Redis (optional cache / scoring)
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
