# Broad Experiment Spec (v0.1 S3-Native)

## Project Goal

Build a small agent memory lab, not a production memory system.

The lab should test whether an agent memory system can:

- form realities, not just retrieve facts
- govern memory influence
- decay and reinforce memories over time
- survive poisoned trusted inputs
- audit how memory changed
- rebuild recall indexes from immutable lineage

---

## Core Theory

Memory is not storage.

Memory is a control system that governs how past signals influence future computation.

Use biology for:

- multi-timescale learning
- consolidation
- contextual recall
- decay
- conflict tolerance
- reconsolidation

Improve on biology with:

- immutable lineage
- replayability
- source-preserving audit
- explicit trust modeling
- controlled forgetting
- poisoning detection

---

## Storage Direction

Use the fewest AWS moving parts:

- S3 Vectors for recall-facing memory
- S3 Tables for canonical queryable lineage
- Athena for analysis
- IAM for v0 access control

Defer:

- Lake Formation
- DynamoDB
- Redis
- custom Parquet ETL
- custom Glue crawlers

---

## Plane Split

### Cognitive Plane

Mutable and adaptive.

Includes:

- S3 Vector index
- eligibility scoring
- memory state
- decay
- promotion
- quarantine
- recall

Purpose:

```text
influence future outputs
```

### Lineage Plane

Immutable and replayable.

Implemented with S3 Tables.

Includes:

- memory events
- state history
- retrieval events
- conflict edges
- score changes
- snapshots

Purpose:

```text
explain why the cognitive plane changed
```

Hard rule:

```text
Vectors may influence recall.
S3 Tables lineage must explain recall.
```

---

## Core Modules

### 1. Lineage Engine

Writes append-only events into S3 Tables.

Events:

- observed
- recalled
- rejected
- mutated
- promoted
- contradicted
- quarantined
- deleted
- snapshotted

Must preserve:

- source identity
- payload hash
- agent_id
- stream_id
- timestamp
- causality link
- parent event when applicable

---

### 2. Recall Engine

Uses S3 Vectors for candidate retrieval.

Responsibilities:

- embed query
- retrieve vector candidates
- apply metadata filters
- pass candidates to eligibility engine

S3 Vectors are not canonical memory.

---

### 3. Materialized Memory State

Current reality of the agent.

May be stored as:

- S3 Tables rows
- optional S3 state objects for cheap point reads

Must be rebuildable from lineage.

---

### 4. Eligibility Engine

Decides whether a memory may influence output.

Formula:

```text
eligibility = relevance * trust * recency * reinforcement * consistency * safety
```

Output must include:

- eligible memories
- rejected memories
- rejection reasons

---

### 5. Time Engine

Models:

- decay
- reinforcement
- suppression
- stale reality pressure

Avoid TTL-only behavior.

Use continuous score change.

---

### 6. Conflict Engine

Contradictions are first-class.

Do not auto-resolve.

Relations:

- supports
- contradicts
- derived_from
- supersedes
- weakens

---

### 7. Sleep Engine

Offline cognition.

Responsibilities:

- replay lineage
- recompute scores
- dedupe traces
- promote stable patterns
- quarantine contradictions
- refresh S3 Vectors
- write snapshots

This replaces ad hoc ETL where possible.

---

### 8. Poisoning Harness

Injects trusted-but-false information.

Tracks:

- spread radius
- confidence movement
- promotion risk
- quarantine latency
- recovery path

---

### 9. Audit Engine

Uses Athena over S3 Tables.

Must answer:

```text
What did the agent believe at time T?
Why?
What changed it?
What was absent?
Which memories influenced output X?
Which memories were retrieved but rejected?
```

---

## Invariants to Prove

1. Every vector maps to a source event identity or payload hash.
2. Every lineage row is tied to an agent_id and event_id.
3. Every materialized state can be rebuilt from S3 Tables.
4. Vector indexes can be deleted and rebuilt from lineage.
5. Quarantined memories cannot influence output.
6. Deleted memories leave tombstones.
7. Conflicts are stored, not erased.
8. Audit can explain both memory presence and absence.

---

## First Experiments

### E1: Trusted False Source vs Weak True Source

Goal:

Test whether trust is treated as a prior, not truth.

Expected:

- false trusted memory may enter the system
- conflict pressure should reduce confidence
- quarantine should trigger if support remains low

---

### E2: Repeated Recall Drift

Goal:

Test reconsolidation.

Method:

- recall same memory under changing contexts
- log mutations
- measure semantic drift

Expected:

- system either stabilizes or exposes drift in lineage

---

### E3: Spaced Reinforcement vs Single Strong Write

Goal:

Test time-aware retention.

Method:

- compare repeated weak confirmations with one strong event

Expected:

- spaced reinforcement should improve survival without hard TTLs

---

### E4: Conflict Persistence Under Retrieval

Goal:

Ensure contradictions survive.

Method:

- query a conflicted claim repeatedly
- inspect eligibility, confidence, and audit trail

Expected:

- no silent collapse into one truth

---

### E5: Sleep Promotion

Goal:

Test episodic to semantic promotion.

Method:

- feed repeated similar traces
- run sleep engine
- inspect derived semantic memory

Expected:

- semantic memory links back to source traces

---

### E6: Poisoning Before Promotion

Goal:

Prevent trusted false facts from becoming semantic memory.

Method:

- inject plausible falsehood from trusted source
- add weak contradiction signals
- run sleep engine

Expected:

- memory quarantined or prevented from promotion

---

### E7: Replay Rebuild

Goal:

Test canonical lineage.

Method:

- delete materialized state
- rebuild from S3 Tables
- compare outputs

Expected:

- rebuilt state equals prior state

---

### E8: Vector Rebuild

Goal:

Test that S3 Vectors are disposable.

Method:

- delete vector index
- rebuild from S3 Tables
- compare recall results

Expected:

- recall equivalence within accepted tolerance

### E9: Eligibility Under Contradiction Pressure

Goal:

Prove that eligibility gating (not retrieval rank alone) governs influence when conflicting memories compete.

Hypothesis:

- Under controlled conflicts, the selected memory should track the configured eligibility function.
- Trust should remain a prior, not override consistency/safety pressure.

Method:

- Seed paired contradictions (`A`, `¬A`) with tunable metadata.
- Run query sweeps where one axis changes at a time:
  - trust-only shift
  - recency-only shift
  - reinforcement-only shift
  - consistency/safety penalty shift
- Record accepted/rejected events with eligibility scores and reasons.

Pass metrics:

- Agreement rate between expected winner (from formula) and recalled winner >= 0.90.
- Every rejected candidate has controlled reason taxonomy (`eligibility_below_threshold` or `cross_scope_reference_attempt`) = 100%.
- No recall accepted below configured threshold = 100%.

Fail conditions:

- Winner tracks nearest-neighbor rank while violating eligibility score order.
- Any uncontrolled rejection reason appears.
- Any below-threshold memory is accepted.

### E10: Reconsolidation Stability Envelope (Write-on-Read)

Goal:

Measure whether repeated recall+mutation converges to stable abstraction or diverges into noise.

Hypothesis:

- Context shifts should cause bounded drift with preserved semantic core under normal pressure.
- Drift should be observable and auditable in lineage.

Method:

- Repeatedly recall the same memory under structured context perturbations.
- Mutate and re-store on each recall (write-on-read).
- Track per-step drift:
  - cosine similarity to base
  - cosine similarity to previous
  - claim token-level delta ratio (or equivalent string delta)

Pass metrics:

- Median cosine similarity to previous step >= 0.85.
- Final cosine similarity to base >= 0.60 (bounded long-run drift).
- 100% of mutation events include parent linkage and drift payload fields.

Fail conditions:

- Unbounded semantic collapse (final cosine to base < 0.60 without quarantine/suppression).
- Missing mutation lineage links or drift fields.

### E11: Promotion-Forgetting Coupling

Goal:

Test whether semantic promotion and episodic decay are coupled as one lifecycle, not independent heuristics.

Hypothesis:

- Frequently reinforced low-variance episodes should promote to semantic memory.
- After promotion, low-value episodic traces should decay/suppress influence while preserving lineage.

Method:

- Seed episodic clusters with controlled support density and context variance.
- Run reinforcement schedule + sleep/promotion pass.
- Apply decay/suppression pass to episodic members.
- Query before/after to compare semantic vs episodic influence.

Pass metrics:

- Promotion precision >= 0.80 against labeled promotable clusters.
- Post-promotion episodic influence share decreases by >= 30% while semantic recall share increases.
- 100% promoted memories retain `derived_from` lineage links to episodic sources.

Fail conditions:

- Promotion occurs for high-variance/low-support clusters above tolerance.
- Episodic traces remain dominant after successful promotion with no decay/suppression evidence.
- Missing lineage links from semantic memory to source episodes.

### E12: Trusted-Source Poison Resilience

Goal:

Stress-test trust-aware gating where high-trust false memories compete with weaker true support.

Hypothesis:

- High-trust false memories should be blocked from promotion/influence when support is low and conflicts are high.
- Quarantine should activate deterministically with machine-readable threat/suspicion labels.

Method:

- Inject trusted-but-false claims plus weak true contradictory evidence.
- Vary support density and trust gaps.
- Measure recall acceptance, quarantine decisions, and promotion outcomes over repeated cycles.

Pass metrics:

- Poison promotion rate <= 5% in high-conflict/low-support regimes.
- Quarantine trigger latency <= 1 cycle after risk threshold breach.
- 100% quarantined events include controlled `reason`, `suspicion_tags`, `threat_labels`.

Fail conditions:

- High-trust false claims consistently promote despite conflict + low support.
- Non-deterministic quarantine tags/reasons.
- Poison memories continue to influence output after quarantine without explicit release event.

---

## Metrics

- reality accuracy under conflict
- drift rate
- poison spread radius
- quarantine latency
- promotion precision
- replay determinism
- vector rebuild fidelity
- audit completeness
- rejected retrieval count
- eligible influence count

---

## Review Questions for Dev Agents

1. Where is canonical lineage stored?
2. Can every reality be traced to events?
3. Can every vector be rebuilt?
4. Can a vector influence output without lineage?
5. Are contradictions stored or overwritten?
6. Is trust treated as truth?
7. Can absence of memory be audited?
8. What happens when the sleep engine is wrong?
9. What IAM boundary prevents agent memory drift?
10. What would force us to introduce Lake Formation?

---

## Acceptance Test

The system must show whether it changes reality, not merely retrieval order.

Final constraint:

```text
storage-simple
policy-rich
lineage-first
retrieval-rebuildable
```
