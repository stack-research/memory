# Core Thesis
Memory is not storage.
Memory is a control system that governs how past signals influence future computation.

---

## Two-Plane Architecture

### 1. Cognitive Memory Plane (Adaptive)
Mutable, lossy, reconstructive.

Functions:
- encode
- retrieve
- reconsolidate (rewrite on read)
- decay
- promote (episodic → semantic)
- suppress
- generalize

### 2. Audit Lineage Plane (Immutable)
Append-only, source-preserving, replayable.

Rules:
- never mutate
- never overwrite
- never silently delete (tombstones required)
- preserve provenance
- support full replay

Key invariant: memory may mutate, lineage must not

---

## Memory Model

A memory is not just content. It is:

- claim
- source
- assertion_time
- event_time
- confidence
- trust
- support (confirmations)
- conflicts (contradictions)
- decay_state
- last_recalled
- mutation_history

---

## Memory Lifecycle

1. Encoding
2. Consolidation
3. Retrieval
4. Reconsolidation
5. Decay / suppression
6. Promotion
7. Quarantine (if needed)

---

## Eligibility Function

Memory influence must be gated.

eligibility = relevance * trust * recency * reinforcement * consistency * safety

Memory is not used unless eligible.

---

## Time Behavior

Time transforms memory:

raw traces → summaries → schemas → beliefs

Do not use TTL-based expiration.
Use continuous decay with reinforcement.

---

## Sleep (Offline Processing)

Sleep is a required subsystem.

Functions:
- replay important traces
- deduplicate
- compress
- promote stable patterns
- decay unused traces
- quarantine contradictions

---

## Conflict Model

Conflicts are first-class objects.

Do NOT auto-resolve contradictions.

Store:
- supports
- contradicts
- derived_from
- supersedes

Reason over disagreement.

---

## Poisoning Model

Assume memory is adversarial.

Key distinction:
- damaged memory = missing or inaccessible
- poisoned memory = coherent but false

Track:
- source_trust
- claim_confidence
- cross_source_support
- conflict_pressure

Trusted sources may be wrong.

---

## Biological Parallels

Use:
- multi-timescale learning
- consolidation
- decay
- reconsolidation
- contextual recall

Avoid:
- source confusion
- confabulation
- silent mutation
- unverifiable recall
- social poisoning effects

---

## System Architecture (Minimal)

- Hot path:
  - S3 Vectors as the sensory / working / recall-facing memory surface
  - S3 objects for memory state + append-only raw event payloads
- Cold / analytic path:
  - Athena for replay checks, drift analysis, poisoning spread, and decay curves
  - Glue Data Catalog for table schemas
  - Parquet tables as consolidated / analytic / long-term lineage memory
- Compaction flow:
  - `events/raw/.../*.json` -> `events/parquet/dt=YYYY-MM-DD/hour=HH/*.parquet` -> Athena
- background workers (sleep + decay + promotion + compaction)

Backend rule:

- raw event objects are the source of truth
- memory-state objects are rebuildable
- vector records are influence indexes, not truth
- Athena reads compacted Parquet, not tiny raw JSON event objects
- snapshots and manifests exist to make replay auditable
- vectors may influence recall; event/parquet lineage must explain recall

Proof invariants:

1. Every vector maps to a source event object identity or source payload hash.
2. Every Parquet row is traceable to raw event identity.
3. Vector indexes can be deleted and rebuilt from durable event/parquet data.

Biology mapping:
- sensory trace / hippocampal recall surface -> S3 Vectors
- sleep consolidation -> compaction job
- cortical long-term memory -> Parquet + Athena

Machine improvement:
- unlike biology, long-term memory remains auditable and replayable

---

## Experiments

### E1: Trust vs Truth
Inject conflicting memories with different trust scores.

### E2: Reconsolidation Drift
Repeated recall under varying contexts.

### E3: Time Reinforcement
Spacing vs single strong write.

### E4: Conflict Persistence
Maintain contradictory beliefs without collapse.

### E5: Promotion
Observe episodic → semantic transition.

### E6: Poisoning
Inject trusted false memory and track spread.

### E7: Audit Replay
Rebuild state from event log exactly.

---

## Evaluation Criteria

The system must answer:

- What does it believe now?
- Why?
- What did it believe before?
- What changed it?
- What was absent?

Primary invariant:

The system must change belief based on experience, not just retrieval order.

---

## Guiding Principle

Use biology for adaptive behavior.
Use machines for auditability.
Never confuse the two.
